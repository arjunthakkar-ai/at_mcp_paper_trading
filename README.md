# Stock Market Paper Trading — MCP Server

An MCP (Model Context Protocol) server that connects AI assistants like Claude to Alpaca's paper trading API. Fetch quotes, analyse stocks, manage a portfolio, and place simulated trades — all from your chat.

## What is MCP?

MCP is a standard protocol that lets AI assistants call external tools. Think of it like a USB port — this server "plugs in" to Claude and gives it stock trading capabilities.

```
You (chat) → Claude → MCP Protocol → This Server → Alpaca Paper Trading API
```

## Tools Provided

| Tool | Description |
|------|-------------|
| `get_stock_quote` | Get latest bid/ask price for any stock |
| `get_historical_data` | Fetch OHLCV candles (Day/Hour/Minute) |
| `search_ticker` | Look up stock tickers by company name |
| `get_portfolio` | View account balance and open positions |
| `place_paper_trade` | Buy or sell stocks (paper money only) |
| `get_trade_history` | View recent order history |

## Setup

### 1. Get Alpaca API Keys (free)

1. Sign up at [https://app.alpaca.markets/signup](https://app.alpaca.markets/signup)
2. Go to **Dashboard → Paper Trading → API Keys → Generate**
3. Copy your API Key and Secret Key

### 2. Install Dependencies

```bash
cd stock-mcp-server

# Option A: using pip
pip install -e .

# Option B: using uv (recommended)
uv pip install -e .
```

### 3. Configure API Keys

```bash
cp .env.example .env
# Edit .env and paste your Alpaca paper trading keys
```

### 4. Test the Server

```bash
# Run directly to check for import errors
python server.py
```

### 5. Connect to Claude Desktop

Add this to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "stock-trading": {
      "command": "python",
      "args": ["/full/path/to/stock-mcp-server/server.py"],
      "env": {
        "ALPACA_API_KEY": "your_key_here",
        "ALPACA_SECRET_KEY": "your_secret_here"
      }
    }
  }
}
```

Then restart Claude Desktop. You should see the tools icon appear.

## Example Prompts to Try

- "What's the current price of AAPL?"
- "Show me TSLA's price history for the last 60 days"
- "Buy 5 shares of NVDA"
- "What's in my portfolio?"
- "Show my recent trades"
- "Search for semiconductor companies"

## Project Structure

```
stock-mcp-server/
├── server.py          ← The MCP server (all tools defined here)
├── pyproject.toml     ← Python project config and dependencies
├── .env.example       ← Template for API keys
├── .env               ← Your actual API keys (not committed)
└── README.md          ← This file
```

## Key Concepts Explained

### FastMCP
A helper class that handles all MCP protocol details. You write normal Python functions with type hints, and FastMCP auto-generates the tool schemas.

### @mcp.tool() Decorator
Registers a function as a tool the AI can call. The function name, docstring, and parameter types are all exposed to the AI.

### Paper Trading
Alpaca's paper trading is a real-time simulation. Orders are matched against live market data but no real money changes hands. Perfect for learning.

## Safety

- This server ONLY connects to Alpaca's **paper trading** environment
- The `paper=True` flag is hardcoded — no real trades can happen
- No real money is ever at risk
