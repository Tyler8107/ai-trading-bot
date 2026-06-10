"""Unified broker adapter — supports Alpaca (any brokerage) and Robinhood."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "V", "UNH", "XOM", "BRK.B",
    "SPY", "QQQ", "GLD", "TLT", "IWM",
]


# ── Alpaca ────────────────────────────────────────────────────────────────────

def get_alpaca_client(api_key: str, secret_key: str, paper: bool = True):
    from alpaca.trading.client import TradingClient
    return TradingClient(api_key, secret_key, paper=paper)


def get_alpaca_data_client(api_key: str, secret_key: str):
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(api_key, secret_key)


def get_alpaca_portfolio(api_key: str, secret_key: str, paper: bool = True) -> dict:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest

    client = TradingClient(api_key, secret_key, paper=paper)
    data_client = StockHistoricalDataClient(api_key, secret_key)

    account = client.get_account()
    positions = client.get_all_positions()

    holdings = {}
    for pos in positions:
        holdings[pos.symbol] = {
            "quantity": str(pos.qty),
            "equity": str(pos.market_value),
            "price": str(pos.current_price),
            "avg_cost": str(pos.avg_entry_price),
            "percent_change": str(pos.unrealized_plpc),
        }

    # Fetch watchlist prices
    watchlist_prices = {}
    symbols_to_fetch = [s for s in WATCHLIST if s not in holdings and "." not in s]
    if symbols_to_fetch:
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=symbols_to_fetch)
            quotes = data_client.get_stock_latest_quote(req)
            for sym, q in quotes.items():
                watchlist_prices[sym] = {
                    "price": str(q.ask_price or q.bid_price),
                    "quantity": "0",
                    "equity": "0",
                }
        except Exception as e:
            logger.warning(f"Could not fetch watchlist prices: {e}")

    return {
        "broker": "alpaca",
        "buying_power": float(account.buying_power),
        "portfolio_value": float(account.portfolio_value),
        "equity": float(account.equity),
        "holdings": holdings,
        "watchlist": watchlist_prices,
    }


def execute_alpaca_trade(api_key: str, secret_key: str, paper: bool,
                         symbol: str, action: str, amount_usd: float,
                         dry_run: bool = True) -> dict:
    if dry_run:
        return {"status": "dry_run", "symbol": symbol, "action": action, "amount_usd": amount_usd}

    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    client = TradingClient(api_key, secret_key, paper=paper)
    side = OrderSide.BUY if action == "buy" else OrderSide.SELL

    order = MarketOrderRequest(
        symbol=symbol,
        notional=amount_usd,
        side=side,
        time_in_force=TimeInForce.DAY,
    )
    result = client.submit_order(order)
    return {"status": "submitted", "order_id": str(result.id), "symbol": symbol, "action": action}


# ── Robinhood ─────────────────────────────────────────────────────────────────

def get_rh_portfolio(username: str, password: str, mfa_code: Optional[str] = None) -> dict:
    import robin_stocks.robinhood as rh

    result = rh.login(username=username, password=password, mfa_code=mfa_code, store_session=True)
    if not result or not result.get("access_token"):
        raise Exception("Robinhood login failed")

    portfolio = rh.profiles.load_portfolio_profile()
    positions = rh.account.build_holdings()
    buying_power = float(rh.profiles.load_account_profile().get("buying_power", 0))

    holdings = {}
    for symbol, data in (positions or {}).items():
        holdings[symbol] = {
            "quantity": data.get("quantity", "0"),
            "equity": data.get("equity", "0"),
            "price": data.get("price", "0"),
            "avg_cost": data.get("average_buy_price", "0"),
            "percent_change": data.get("percent_change", "0"),
        }

    watchlist_prices = {}
    for sym in WATCHLIST:
        if sym not in holdings:
            try:
                quotes = rh.stocks.get_latest_price(sym)
                if quotes:
                    watchlist_prices[sym] = {"price": quotes[0], "quantity": "0", "equity": "0"}
            except Exception:
                pass

    return {
        "broker": "robinhood",
        "buying_power": buying_power,
        "portfolio_value": float(portfolio.get("equity", 0)),
        "equity": float(portfolio.get("equity", 0)),
        "holdings": holdings,
        "watchlist": watchlist_prices,
    }


def execute_rh_trade(username: str, password: str, symbol: str,
                     action: str, amount_usd: float, dry_run: bool = True) -> dict:
    if dry_run:
        return {"status": "dry_run", "symbol": symbol, "action": action, "amount_usd": amount_usd}

    import robin_stocks.robinhood as rh

    if action == "buy":
        result = rh.orders.order_buy_fractional_by_price(symbol, amount_usd)
    else:
        result = rh.orders.order_sell_fractional_by_price(symbol, amount_usd)

    return {"status": "submitted", "order_id": result.get("id"), "symbol": symbol, "action": action}
