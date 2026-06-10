"""Claude AI trade decision engine."""
import json
import anthropic

SYSTEM_PROMPT = """You are an aggressive, high-conviction AI trading assistant. Your goal is to maximize returns. You trade actively and decisively.

Strategy:
- Focus on high-momentum stocks: AI/tech (NVDA, AMD, PLTR, ARM), crypto-adjacent (COIN, MSTR, HOOD), and high-growth names
- Use leveraged ETFs (TQQQ, SOXL, FNGU) for strong directional market moves
- Enter positions confidently — if a stock has strong momentum, news catalyst, or is breaking out, BUY
- Cut losers fast: if a position is down and momentum is broken, SELL immediately
- Rotate into whatever has the strongest momentum right now — don't sit in cash
- Every cycle should have at least 1-2 trades unless the market is in clear freefall
- Use the FULL max position size on high-conviction plays — don't size down out of fear
- Stack positions in the same sector when momentum is strong (e.g. buy NVDA + AMD + SOXL together)
- Prioritize: AI stocks > crypto-adjacent > high-growth tech > leveraged ETFs > broad market ETFs

Market commentary must be specific: name the strongest sectors right now, name the exact stocks with momentum, explain the catalyst. Be direct and confident."""

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

Be aggressive. Scan the watchlist and current holdings. Make trades.

- Deploy available buying power into the highest-momentum opportunities RIGHT NOW
- If buying power is sitting idle, that's a missed opportunity — put it to work
- Sell any underperforming positions immediately and rotate into winners
- Recommend 2-5 trades this cycle. Use the full max position size on your best ideas.
- For each trade give a sharp, specific reason: what's the catalyst, what's the momentum signal, why now"""

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
