"""Claude AI trade decision engine."""
import json
import anthropic

SYSTEM_PROMPT = """You are an expert AI trading assistant. Analyze the portfolio and market data provided, then recommend specific trades to maximize returns while managing risk.

Rules:
- Only trade liquid, well-known stocks and ETFs
- Never put more than 20% of portfolio in a single position
- Consider current market conditions and sector trends
- Prioritize capital preservation alongside growth
- Be specific: give exact symbols and dollar amounts"""

TRADE_TOOL = {
    "name": "execute_trades",
    "description": "Submit a list of trade recommendations to execute",
    "input_schema": {
        "type": "object",
        "properties": {
            "trades": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "action": {"type": "string", "enum": ["buy", "sell"]},
                        "amount_usd": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["symbol", "action", "amount_usd", "reason"],
                },
            },
            "market_commentary": {"type": "string"},
        },
        "required": ["trades"],
    },
}


def get_trade_decisions(portfolio: dict, max_position_usd: float, api_key: str = None) -> dict:
    import os
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""Current portfolio state:
{json.dumps(portfolio, indent=2)}

Max position size: ${max_position_usd}
Available buying power: ${portfolio.get('buying_power', 0):.2f}
Total portfolio value: ${portfolio.get('portfolio_value', 0):.2f}

Analyze this portfolio and current market conditions. Recommend specific trades (buy/sell) or hold.
Consider the watchlist stocks as potential new positions. Be selective — only trade when there's clear opportunity."""

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[TRADE_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    for block in message.content:
        if block.type == "tool_use" and block.name == "execute_trades":
            return block.input

    return {"trades": [], "market_commentary": "No clear opportunities identified."}
