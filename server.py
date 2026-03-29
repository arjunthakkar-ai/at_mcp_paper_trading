"""
Stock Market Paper Trading MCP Server
======================================
An MCP server that connects to Alpaca's paper trading API,
allowing AI assistants to fetch quotes, analyse stocks,
and place simulated trades.

Architecture:
    Claude (AI) → MCP Protocol → This Server → Alpaca Paper Trading API

Key concepts used:
    - FastMCP: A helper class from the MCP SDK that auto-generates
      tool definitions from Python type hints and docstrings.
    - @mcp.tool(): Decorator that registers a function as a callable
      tool. The AI sees the function name, docstring, and parameters.
    - Type hints: FastMCP reads these to build the JSON schema that
      tells the AI what inputs each tool expects.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- MCP SDK ---
# FastMCP is the high-level helper that handles all the protocol
# plumbing (JSON-RPC, stdin/stdout transport, schema generation).
# You just write normal Python functions and decorate them.
from mcp.server.fastmcp import FastMCP

# --- Alpaca SDK ---
# TradingClient: place orders, get account/portfolio info
# StockHistoricalDataClient: fetch OHLCV candles, quotes
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

# ──────────────────────────────────────────────
# 1. LOAD CONFIG
# ──────────────────────────────────────────────
# load_dotenv() reads your .env file so we don't hardcode secrets.
load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
    print("⚠️  Warning: ALPACA_API_KEY and ALPACA_SECRET_KEY not set.")
    print("   Copy .env.example to .env and add your paper trading keys.")
    print("   Get free keys at: https://app.alpaca.markets/signup")

# ──────────────────────────────────────────────
# 2. INITIALISE CLIENTS
# ──────────────────────────────────────────────
# paper=True → connects to Alpaca's sandbox (no real money)
trading_client = TradingClient(
    api_key=ALPACA_API_KEY,
    secret_key=ALPACA_SECRET_KEY,
    paper=True,
)

# Data client for historical prices and live quotes
# (no keys needed for free tier stock data)
data_client = StockHistoricalDataClient(
    api_key=ALPACA_API_KEY,
    secret_key=ALPACA_SECRET_KEY,
)

# ──────────────────────────────────────────────
# 3. CREATE THE MCP SERVER
# ──────────────────────────────────────────────
# This single line sets up:
#   - A JSON-RPC server that speaks the MCP protocol
#   - Automatic tool registration via @mcp.tool()
#   - stdin/stdout transport (how Claude talks to this server)
mcp = FastMCP(
    "Stock Paper Trading",
    dependencies=["alpaca-py", "python-dotenv"],
)


# ──────────────────────────────────────────────
# 4. DEFINE TOOLS
# ──────────────────────────────────────────────
# Each @mcp.tool() function becomes a tool the AI can call.
# The docstring becomes the tool description.
# The type hints become the input schema.
# The return value is what the AI sees as output.


@mcp.tool()
def get_stock_quote(symbol: str) -> str:
    """
    Get the latest price quote for a stock.

    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'TSLA', 'MSFT')

    Returns:
        Current bid/ask prices and spread for the given stock.
    """
    try:
        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = data_client.get_stock_latest_quote(request)

        q = quote[symbol]
        spread = round(q.ask_price - q.bid_price, 4)

        return (
            f"📈 {symbol} Latest Quote\n"
            f"  Bid:    ${q.bid_price:.2f} (size: {q.bid_size})\n"
            f"  Ask:    ${q.ask_price:.2f} (size: {q.ask_size})\n"
            f"  Spread: ${spread:.4f}\n"
            f"  Time:   {q.timestamp}"
        )
    except Exception as e:
        return f"❌ Error fetching quote for {symbol}: {str(e)}"


@mcp.tool()
def get_historical_data(
    symbol: str,
    days: int = 30,
    timeframe: str = "Day",
) -> str:
    """
    Get historical OHLCV (Open/High/Low/Close/Volume) bar data for a stock.

    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL')
        days: Number of days of history to fetch (default 30, max 365)
        timeframe: Bar size - 'Day', 'Hour', or 'Minute' (default 'Day')

    Returns:
        Historical price bars with OHLCV data, plus a summary.
    """
    try:
        days = min(days, 365)

        tf_map = {
            "Day": TimeFrame.Day,
            "Hour": TimeFrame.Hour,
            "Minute": TimeFrame.Minute,
        }
        tf = tf_map.get(timeframe, TimeFrame.Day)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=datetime.now() - timedelta(days=days),
        )
        bars = data_client.get_stock_bars(request)
        bar_list = bars[symbol]

        if not bar_list:
            return f"No data found for {symbol} over the last {days} days."

        # Summary stats
        closes = [b.close for b in bar_list]
        volumes = [b.volume for b in bar_list]
        high = max(b.high for b in bar_list)
        low = min(b.low for b in bar_list)
        avg_volume = sum(volumes) / len(volumes)
        change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100

        # Format recent bars (last 10)
        lines = [f"📊 {symbol} — Last {days} days ({timeframe} bars)\n"]
        lines.append(f"{'Date':<12} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Volume':>12}")
        lines.append("-" * 68)

        for bar in bar_list[-10:]:
            date_str = bar.timestamp.strftime("%Y-%m-%d")
            lines.append(
                f"{date_str:<12} {bar.open:>8.2f} {bar.high:>8.2f} "
                f"{bar.low:>8.2f} {bar.close:>8.2f} {bar.volume:>12,}"
            )

        lines.append(f"\n📋 Summary ({len(bar_list)} bars total)")
        lines.append(f"  Period High:  ${high:.2f}")
        lines.append(f"  Period Low:   ${low:.2f}")
        lines.append(f"  Change:       {change_pct:+.2f}%")
        lines.append(f"  Avg Volume:   {avg_volume:,.0f}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching history for {symbol}: {str(e)}"


@mcp.tool()
def search_ticker(query: str) -> str:
    """
    Search for stock tickers by company name or partial symbol.
    Uses a curated list of popular US stocks for quick lookup.

    Args:
        query: Company name or ticker to search (e.g. 'apple', 'TSLA', 'micro')

    Returns:
        Matching stock tickers and company names.
    """
    # A practical lookup table for common stocks.
    # In production, you'd call a proper search API.
    popular_stocks = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "GOOGL": "Alphabet Inc. (Google)",
        "AMZN": "Amazon.com Inc.",
        "NVDA": "NVIDIA Corporation",
        "META": "Meta Platforms Inc.",
        "TSLA": "Tesla Inc.",
        "BRK.B": "Berkshire Hathaway Inc.",
        "JPM": "JPMorgan Chase & Co.",
        "V": "Visa Inc.",
        "JNJ": "Johnson & Johnson",
        "WMT": "Walmart Inc.",
        "PG": "Procter & Gamble Co.",
        "MA": "Mastercard Inc.",
        "UNH": "UnitedHealth Group Inc.",
        "HD": "Home Depot Inc.",
        "DIS": "Walt Disney Co.",
        "BAC": "Bank of America Corp.",
        "ADBE": "Adobe Inc.",
        "CRM": "Salesforce Inc.",
        "NFLX": "Netflix Inc.",
        "AMD": "Advanced Micro Devices Inc.",
        "INTC": "Intel Corporation",
        "CSCO": "Cisco Systems Inc.",
        "PEP": "PepsiCo Inc.",
        "KO": "Coca-Cola Co.",
        "COST": "Costco Wholesale Corp.",
        "PYPL": "PayPal Holdings Inc.",
        "UBER": "Uber Technologies Inc.",
        "SQ": "Block Inc. (Square)",
        "SHOP": "Shopify Inc.",
        "SPOT": "Spotify Technology SA",
        "SNAP": "Snap Inc.",
        "COIN": "Coinbase Global Inc.",
        "PLTR": "Palantir Technologies Inc.",
        "RIVN": "Rivian Automotive Inc.",
        "SOFI": "SoFi Technologies Inc.",
    }

    query_lower = query.lower()
    matches = []

    for ticker, name in popular_stocks.items():
        if (
            query_lower in ticker.lower()
            or query_lower in name.lower()
        ):
            matches.append(f"  {ticker:<8} {name}")

    if not matches:
        return (
            f"No matches found for '{query}'.\n"
            f"Try a broader term, or use the exact ticker symbol "
            f"directly with get_stock_quote."
        )

    header = f"🔍 Search results for '{query}':\n"
    return header + "\n".join(matches)


@mcp.tool()
def get_portfolio() -> str:
    """
    Get the current paper trading account summary and all open positions.
    Shows cash balance, portfolio value, buying power, and each stock held.

    Returns:
        Account overview and list of current positions with P&L.
    """
    try:
        # Account summary
        account = trading_client.get_account()
        lines = [
            "💼 Paper Trading Portfolio\n",
            f"  Cash:           ${float(account.cash):>12,.2f}",
            f"  Portfolio Value: ${float(account.portfolio_value):>12,.2f}",
            f"  Buying Power:   ${float(account.buying_power):>12,.2f}",
            f"  Equity:         ${float(account.equity):>12,.2f}",
        ]

        # Positions
        positions = trading_client.get_all_positions()

        if not positions:
            lines.append("\n📭 No open positions.")
        else:
            lines.append(f"\n📊 Open Positions ({len(positions)}):")
            lines.append(
                f"  {'Symbol':<8} {'Qty':>6} {'Entry':>10} "
                f"{'Current':>10} {'P&L':>12} {'P&L %':>8}"
            )
            lines.append("  " + "-" * 60)

            for pos in positions:
                pnl = float(pos.unrealized_pl)
                pnl_pct = float(pos.unrealized_plpc) * 100
                emoji = "🟢" if pnl >= 0 else "🔴"
                lines.append(
                    f"  {pos.symbol:<8} {pos.qty:>6} "
                    f"${float(pos.avg_entry_price):>9.2f} "
                    f"${float(pos.current_price):>9.2f} "
                    f"{emoji} ${pnl:>10.2f} {pnl_pct:>+7.2f}%"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching portfolio: {str(e)}"


@mcp.tool()
def place_paper_trade(
    symbol: str,
    quantity: float,
    side: str = "buy",
) -> str:
    """
    Place a paper (simulated) market order to buy or sell a stock.
    This uses Alpaca's paper trading — no real money is involved.

    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL')
        quantity: Number of shares (supports fractional, e.g. 0.5)
        side: 'buy' or 'sell'

    Returns:
        Order confirmation with order ID and details.
    """
    try:
        side_lower = side.lower().strip()
        if side_lower not in ("buy", "sell"):
            return f"❌ Invalid side '{side}'. Must be 'buy' or 'sell'."

        if quantity <= 0:
            return "❌ Quantity must be greater than 0."

        order_side = OrderSide.BUY if side_lower == "buy" else OrderSide.SELL

        order_data = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=quantity,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )

        order = trading_client.submit_order(order_data=order_data)

        emoji = "🟢 BUY" if side_lower == "buy" else "🔴 SELL"

        return (
            f"✅ Order Placed Successfully!\n\n"
            f"  Action:   {emoji}\n"
            f"  Symbol:   {order.symbol}\n"
            f"  Quantity: {order.qty}\n"
            f"  Type:     Market Order\n"
            f"  Status:   {order.status}\n"
            f"  Order ID: {order.id}\n"
            f"  Time:     {order.submitted_at}\n\n"
            f"  ⚠️  This is a PAPER trade — no real money was used."
        )
    except Exception as e:
        return f"❌ Error placing order: {str(e)}"


@mcp.tool()
def get_trade_history(limit: int = 10) -> str:
    """
    Get recent order history from the paper trading account.

    Args:
        limit: Number of recent orders to show (default 10, max 50)

    Returns:
        List of recent orders with status, side, symbol, and fill details.
    """
    try:
        limit = min(limit, 50)

        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=limit,
        )
        orders = trading_client.get_orders(request)

        if not orders:
            return "📭 No orders found. Place your first paper trade!"

        lines = [f"📜 Recent Orders (last {len(orders)}):\n"]

        for order in orders:
            status_emoji = {
                "filled": "✅",
                "partially_filled": "🟡",
                "new": "🔵",
                "canceled": "⚪",
                "rejected": "🔴",
            }.get(str(order.status), "❓")

            side_str = "BUY " if str(order.side) == "buy" else "SELL"
            filled_price = (
                f"@ ${float(order.filled_avg_price):.2f}"
                if order.filled_avg_price
                else ""
            )

            lines.append(
                f"  {status_emoji} {side_str} {order.qty} x {order.symbol} "
                f"{filled_price} [{order.status}] "
                f"— {order.submitted_at.strftime('%Y-%m-%d %H:%M') if order.submitted_at else 'N/A'}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching trade history: {str(e)}"


# ──────────────────────────────────────────────
# 5. RUN THE SERVER
# ──────────────────────────────────────────────
# This starts the MCP server using stdin/stdout transport.
# When Claude Desktop (or any MCP client) launches this script,
# it communicates over stdin/stdout using JSON-RPC messages.

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
