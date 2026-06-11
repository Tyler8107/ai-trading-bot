"""Manages running bot instances per user in background threads."""
import logging
import threading
import time
from datetime import datetime, time as dtime, date
from zoneinfo import ZoneInfo
from typing import Optional

from analyzer import get_trade_decisions
from broker import get_alpaca_portfolio, execute_alpaca_trade, get_rh_portfolio, execute_rh_trade, execute_rh_price_target_sell

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)

# user_id -> {"thread": Thread, "stop": Event, "status": str, "last_run": str, "log": []}
_bots: dict = {}

# Global price-target monitor (single thread watches all users)
_pt_thread: Optional[threading.Thread] = None
_pt_stop = threading.Event()


def _check_price_targets():
    """Check all pending price targets and execute live sells when hit."""
    from app import app
    with app.app_context():
        from models import db, PriceTarget, BotSettings, Trade
        today = date.today()
        targets = PriceTarget.query.filter_by(triggered=False).filter(
            db.or_(PriceTarget.expires_date.is_(None), PriceTarget.expires_date >= today)
        ).all()

        if not targets:
            return

        from collections import defaultdict
        by_user: dict = defaultdict(list)
        for t in targets:
            by_user[t.user_id].append(t)

        for user_id, user_targets in by_user.items():
            settings = BotSettings.query.filter_by(user_id=user_id).first()
            if not settings or not settings.rh_username or not settings.rh_password:
                continue

            import robin_stocks.robinhood as rh
            try:
                login_result = rh.login(username=settings.rh_username, password=settings.rh_password, store_session=True)
                if not login_result or not login_result.get("access_token"):
                    logger.warning(f"[user:{user_id}] Robinhood login failed for price target check")
                    continue

                for target in user_targets:
                    try:
                        prices = rh.stocks.get_latest_price(target.symbol)
                        if not prices or not prices[0]:
                            continue
                        current_price = float(prices[0])

                        if current_price >= target.target_price:
                            order_result, amount_usd = execute_rh_price_target_sell(
                                settings.rh_username, settings.rh_password,
                                target.symbol, target.sell_percent,
                            )
                            target.triggered = True
                            db.session.add(Trade(
                                user_id=user_id,
                                symbol=target.symbol,
                                action="sell",
                                amount_usd=amount_usd,
                                reason=f"Price target: ${current_price:.2f} >= ${target.target_price:.2f} ({target.sell_percent:.0f}% of position)",
                                result=str(order_result),
                                dry_run=False,
                            ))
                            db.session.commit()
                            logger.info(f"[user:{user_id}] Price target hit — SELL {target.sell_percent:.0f}% {target.symbol} @ ${current_price:.2f} (${amount_usd:.2f})")
                    except Exception as e:
                        logger.error(f"[user:{user_id}] Price target error ({target.symbol}): {e}")
            except Exception as e:
                logger.error(f"[user:{user_id}] Login error in price target monitor: {e}")


def start_price_target_monitor():
    global _pt_thread, _pt_stop
    if _pt_thread and _pt_thread.is_alive():
        return
    _pt_stop = threading.Event()

    def run():
        while not _pt_stop.is_set():
            if market_is_open():
                try:
                    _check_price_targets()
                except Exception as e:
                    logger.error(f"Price target monitor error: {e}")
            _pt_stop.wait(60)

    _pt_thread = threading.Thread(target=run, daemon=True)
    _pt_thread.start()
    logger.info("Price target monitor started")


def market_is_open() -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def get_status(user_id: int) -> dict:
    if user_id not in _bots:
        return {"running": False, "status": "stopped", "last_run": None, "log": [], "market_commentary": ""}
    bot = _bots[user_id]
    return {
        "running": bot["thread"].is_alive(),
        "status": bot["status"],
        "last_run": bot["last_run"],
        "log": bot["log"][-20:],
        "market_commentary": bot.get("market_commentary", ""),
    }


def start_bot(user_id: int, settings) -> bool:
    if user_id in _bots and _bots[user_id]["thread"].is_alive():
        return False

    stop_event = threading.Event()
    log_buffer = []

    def run():
        daily_loss = 0.0
        _bots[user_id]["status"] = "running"

        def log(msg):
            ts = datetime.now(ET).strftime("%H:%M:%S")
            entry = f"[{ts}] {msg}"
            log_buffer.append(entry)
            logger.info(f"[user:{user_id}] {msg}")

        while not stop_event.is_set():
            try:
                if not market_is_open() and not settings.dry_run:
                    log("Market closed — sleeping")
                    stop_event.wait(300)
                    continue

                log("Starting trading cycle")
                _bots[user_id]["status"] = "running cycle"

                if settings.broker == "alpaca":
                    portfolio = get_alpaca_portfolio(
                        settings.alpaca_api_key, settings.alpaca_secret_key, settings.alpaca_paper
                    )
                else:
                    portfolio = get_rh_portfolio(settings.rh_username, settings.rh_password)

                log(f"Portfolio: ${portfolio['portfolio_value']:.2f} | Cash: ${portfolio['buying_power']:.2f}")

                if daily_loss <= -settings.max_daily_loss_usd:
                    log(f"Daily loss limit hit (${daily_loss:.2f}). Skipping.")
                    stop_event.wait(settings.run_interval_minutes * 60)
                    continue

                decisions = get_trade_decisions(portfolio, settings.max_position_usd, settings.anthropic_api_key or None)
                trades = decisions.get("trades", [])
                commentary = decisions.get("market_commentary", "")
                if commentary:
                    _bots[user_id]["market_commentary"] = commentary
                    log(f"Market analysis: {commentary[:80]}")

                if not trades:
                    log("Claude recommends holding. No trades.")
                else:
                    from models import db, Trade
                    from app import app
                    with app.app_context():
                        for trade in trades:
                            amount = min(float(trade["amount_usd"]), settings.max_position_usd)
                            log(f"{trade['action'].upper()} ${amount:.2f} {trade['symbol']} — {trade['reason'][:60]}")

                            if settings.broker == "alpaca":
                                result = execute_alpaca_trade(
                                    settings.alpaca_api_key, settings.alpaca_secret_key,
                                    settings.alpaca_paper, trade["symbol"], trade["action"],
                                    amount, settings.dry_run,
                                )
                            else:
                                # Robinhood trading disabled — all RH orders run as dry_run
                                result = execute_rh_trade(
                                    settings.rh_username, settings.rh_password,
                                    trade["symbol"], trade["action"], amount, dry_run=True,
                                )

                            db.session.add(Trade(
                                user_id=user_id,
                                symbol=trade["symbol"],
                                action=trade["action"],
                                amount_usd=amount,
                                reason=trade["reason"],
                                result=str(result),
                                dry_run=settings.dry_run,
                            ))
                            db.session.commit()

                            if trade["action"] == "sell":
                                daily_loss -= amount

                _bots[user_id]["last_run"] = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")
                _bots[user_id]["status"] = "idle — waiting for next cycle"
                log(f"Cycle complete. Next run in {settings.run_interval_minutes} min.")
                stop_event.wait(settings.run_interval_minutes * 60)

            except Exception as e:
                log(f"ERROR: {e}")
                _bots[user_id]["status"] = f"error: {e}"
                stop_event.wait(60)

        _bots[user_id]["status"] = "stopped"
        log("Bot stopped.")

    t = threading.Thread(target=run, daemon=True)
    _bots[user_id] = {"thread": t, "stop": stop_event, "status": "starting", "last_run": None, "log": log_buffer, "market_commentary": ""}
    t.start()
    return True


def stop_bot(user_id: int) -> bool:
    if user_id not in _bots:
        return False
    _bots[user_id]["stop"].set()
    return True
