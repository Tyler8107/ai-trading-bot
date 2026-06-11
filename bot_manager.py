"""Manages running bot instances per user in background threads."""
import logging
import threading
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from typing import Optional

from analyzer import get_trade_decisions
from broker import get_alpaca_portfolio, execute_alpaca_trade, get_rh_portfolio, execute_rh_trade

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)

# user_id -> {"thread": Thread, "stop": Event, "status": str, "last_run": str, "log": []}
_bots: dict = {}


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
