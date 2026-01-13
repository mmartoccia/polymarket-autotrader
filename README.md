# Polymarket AutoTrader

**Automated trading bot for Polymarket 15-minute Up/Down crypto markets.**

## Features

- **Momentum Trading** - Detects price momentum across BTC, ETH, SOL, XRP
- **Multi-Exchange Signals** - Aggregates data from Binance, Kraken, Coinbase
- **Regime Detection** - Ralph Wiggum adaptive strategy selection
- **Risk Management** - Position sizing, drawdown protection, correlation limits
- **Auto-Redemption** - Automatic winner redemption after epoch resolution
- **Live Dashboard** - Real-time terminal monitoring

## Performance

- **Current Balance:** $189.00
- **Starting Balance:** $35.23 (Jan 13, 2026)
- **Daily Return:** +437% (+$154)
- **Strategy:** Contrarian fade + momentum confirmation

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/mmartoccia/polymarket-autotrader.git
cd polymarket-autotrader

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp config/.env.example .env

# Edit with your wallet details
nano .env
```

Required in `.env`:
- `POLYMARKET_WALLET` - Your Polygon wallet address
- `POLYMARKET_PRIVATE_KEY` - Your wallet private key

### 3. Run Bot

```bash
# Activate virtual environment
source venv/bin/activate

# Run trading bot
python3 bot/momentum_bot_v12.py

# Or run dashboard (separate terminal)
python3 dashboard/live_dashboard.py
```

## Directory Structure

```
polymarket-autotrader/
├── bot/                    # Core trading logic
│   ├── momentum_bot_v12.py           # Main production bot
│   ├── timeframe_tracker.py          # Multi-timeframe analysis
│   └── ralph_regime_adapter.py       # Regime detection
├── dashboard/              # Monitoring tools
│   └── live_dashboard.py             # Real-time terminal display
├── utils/                  # Helper scripts
│   ├── redeem_winners.py             # Manual redemption
│   ├── cleanup_losers.py             # Clean worthless positions
│   └── check_15min_markets.py        # Market discovery
├── state/                  # Bot state (gitignored)
├── scripts/               # Deployment scripts
├── config/                # Configuration templates
├── docs/                  # Documentation
└── requirements.txt       # Python dependencies
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [Deployment Guide](docs/DEPLOYMENT.md) - VPS deployment & systemd service

## Strategy Overview

### Contrarian Fade
- Identifies when one side is overpriced (>70%)
- Takes cheap entry on opposite side (<$0.20)
- Leverages mean reversion in binary markets

### Momentum Confirmation
- Confirms price movements across 3 exchanges
- Early entry when momentum starts (15-300s into epoch)
- Late confirmation for high-probability trades (>85%)

### Risk Management
- Max 4 positions (1 per crypto)
- Position sizing: 5-15% of balance (tiered)
- 30% drawdown protection
- Correlation limits (max 8% in one direction)

## Production Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for VPS setup with systemd service.

## Safety & Disclaimers

⚠️ **Trading involves risk. Use at your own risk.**

- Start with small amounts to test
- Monitor bot performance regularly
- Review code before running with real funds
- Never commit `.env` or private keys to git

## Support

- **Issues:** [GitHub Issues](https://github.com/mmartoccia/polymarket-autotrader/issues)
- **Docs:** See `/docs` directory

## License

MIT License - See LICENSE file for details

---

**Note:** This bot trades 15-minute binary outcome markets. Profits come from correctly predicting short-term crypto price movements, not from arbitrage or market manipulation.
