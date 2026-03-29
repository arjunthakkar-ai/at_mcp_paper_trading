"""
Stock Paper Trading MCP Client
================================
A conversational CLI client powered by Claude that connects to the
stock-mcp-server and lets you trade, analyze, and query your paper
portfolio in plain English.

Usage:
    python client.py
"""

import sys
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage, TextBlock

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
MCP_SERVER = {
    "stock-trader": {
        "command": "python",
        "args": ["server.py"],
    }
}

SYSTEM_PROMPT = """\
You are a helpful stock paper trading assistant. You have access to tools
that connect to Alpaca's paper trading API (no real money involved).

Available tools:
- get_stock_quote     — live bid/ask quote for any ticker
- get_historical_data — OHLCV bar history (Day / Hour / Minute)
- search_ticker       — look up tickers by company name
- get_portfolio       — account balance and open positions with P&L
- place_paper_trade   — buy or sell shares (paper / simulated only)
- get_trade_history   — recent order history

Always remind the user when placing trades that this is paper trading
and no real money is involved. Be concise and format numbers clearly.
"""


# ──────────────────────────────────────────────
# CLIENT LOOP
# ──────────────────────────────────────────────
async def chat(user_input: str) -> str:
    """Send one message to Claude (with MCP tools) and return the reply."""
    full_response = []

    async for message in query(
        prompt=user_input,
        options=ClaudeAgentOptions(
            model="claude-opus-4-6",
            system_prompt=SYSTEM_PROMPT,
            mcp_servers=MCP_SERVER,
            max_turns=10,
        ),
    ):
        if isinstance(message, ResultMessage):
            return message.result
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    full_response.append(block.text)

    return "\n".join(full_response) if full_response else "(no response)"


async def main() -> None:
    print("=" * 60)
    print("  Stock Paper Trading Assistant")
    print("  Powered by Claude + Alpaca Paper Trading")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        print()
        try:
            response = await chat(user_input)
            print(f"Assistant: {response}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

        print()


if __name__ == "__main__":
    anyio.run(main)
