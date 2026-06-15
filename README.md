# Day Trading Agent

An autonomous day trading agent that scans markets, generates signals, manages risk, and executes trades via Alpaca (paper trading by default).

## Get the Full Starter Kit

Want the packaged zip with setup scripts, trade journal, live dashboard, and buyer guides?

**[Paper Trading Bot Starter Kit on Gumroad](https://br83214.gumroad.com)** — $97 (use code `LAUNCH20` for 20% off)

This repo is the open-source core. The kit adds Windows setup wizards, SQLite journal + CSV export, FastAPI dashboard, configuration guides, and email support.

*Educational software only. Not financial advice. Paper trade first.*

## Features

- **Momentum + RSI strategy** — EMA crossover with RSI confirmation and volume filter
- **Risk management** — position sizing, stop loss, take profit, daily loss limit
- **Market hours aware** — only trades during NYSE hours, flattens before close
- **Paper trading default** — practice with simulated money before going live
- **Trade journal** — SQLite blotter + daily CSV export (full kit)
- **Live dashboard** — monitor at `http://127.0.0.1:8765` (full kit)

## Quick Start

### 1. Get Alpaca API Keys (Free)

1. Sign up at [alpaca.markets](https://alpaca.markets/)
2. Go to Paper Trading dashboard
3. Generate API key and secret

### 2. Setup (one-click)

```powershell
cd day-trading-agent
.\setup.ps1
```

Or manually:

```bash
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your paper trading keys:

```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
TRADING_MODE=paper
```

### 3. Run

```powershell
.\run.ps1 -Simulate    # Offline test (no API keys)
.\run.ps1 -DryRun      # Test broker connection
.\run.ps1 -Status      # Account snapshot
.\run.ps1              # Start trading
```

Or via Python directly:

```bash
python -m src.main --simulate
python -m src.main --dry-run
python -m src.main --status
python -m src.main
```

## Configuration

Edit `config/settings.yaml` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `watchlist` | SPY, QQQ, AAPL... | Symbols to scan |
| `scan_interval_seconds` | 60 | How often to scan |
| `max_position_pct` | 10% | Max equity per trade |
| `stop_loss_pct` | 1.5% | Auto-exit on loss |
| `take_profit_pct` | 3% | Auto-exit on gain |
| `max_daily_loss_pct` | 3% | Halt trading if hit |

## Architecture

```
src/
├── agent.py          # Main orchestrator loop
├── broker/alpaca.py  # Order execution & data
├── strategy/         # Signal generation
├── risk/             # Trade approval & exits
├── journal/          # SQLite trade blotter (full kit)
├── dashboard/        # Local web UI (full kit)
└── utils/            # Logging, market hours
```

## Going Live

Only after extensive paper trading:

1. Set `TRADING_MODE=live` in `.env`
2. Use live API keys from Alpaca
3. Start with small position sizes

**Warning:** Day trading involves substantial risk. Past performance does not guarantee future results.
