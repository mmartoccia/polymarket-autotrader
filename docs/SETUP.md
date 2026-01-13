# Polymarket AutoTrader - Setup Guide

Complete installation and configuration instructions.

## Prerequisites

- Python 3.11+
- Polygon wallet with USDC
- Private key access to your wallet

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/mmartoccia/polymarket-autotrader.git
cd polymarket-autotrader
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy template
cp config/.env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

Add your wallet details:
```env
POLYMARKET_WALLET=0xYourWalletAddressHere
POLYMARKET_PRIVATE_KEY=0xYourPrivateKeyHere
```

⚠️ **Security Note:**
- Never commit `.env` to git
- Keep your private key secure
- Use a dedicated trading wallet

### 5. Test Configuration

```bash
# Check wallet balance
python3 utils/check_balance.py

# Check available markets
python3 utils/check_15min_markets.py
```

### 6. Run Bot

```bash
# Start trading bot
python3 bot/momentum_bot_v12.py

# In separate terminal, monitor with dashboard
python3 dashboard/live_dashboard.py
```

## Understanding Bot Behavior

### First Run

On first run, the bot will:
1. Create `state/trading_state.json`
2. Set `day_start_balance` to current USDC balance
3. Initialize all counters to 0
4. Start in "normal" mode

### State Files

Bot maintains state in `state/` directory:
- `trading_state.json` - Current state (balance, mode, streaks)
- `timeframe_trades.json` - Trade history for analysis

These files persist across restarts.

### Trading Modes

Bot automatically adjusts between modes based on performance:

- **normal** (default) - Standard position sizing
- **conservative** - Reduced sizing after small losses
- **defensive** - Further reduced after larger losses
- **recovery** - Minimal sizing after significant losses
- **halted** - Stopped trading (drawdown exceeded)

## Configuration Tuning

Edit constants in `bot/momentum_bot_v12.py`:

### Position Sizing
```python
POSITION_TIERS = [
    (30, 0.15),     # Balance < $30: max 15%
    (75, 0.10),     # Balance $30-75: max 10%
    (150, 0.07),    # Balance $75-150: max 7%
    (float('inf'), 0.05),  # Balance > $150: max 5%
]
```

### Risk Limits
```python
MAX_DRAWDOWN_PCT = 0.30          # 30% drawdown = halt
DAILY_LOSS_LIMIT_USD = 30        # Stop at $30 loss
MAX_SAME_DIRECTION_POSITIONS = 4 # Max positions in one direction
```

### Strategy Thresholds
```python
EARLY_MAX_ENTRY = 0.30           # Max entry price for early trades
MIN_SIGNAL_STRENGTH = 0.72       # Minimum signal confidence
CONTRARIAN_MAX_ENTRY = 0.20      # Max entry for contrarian trades
```

## Monitoring

### Live Dashboard

Run in separate terminal:
```bash
python3 dashboard/live_dashboard.py
```

Shows real-time:
- Current balance & P&L
- Open positions
- Win/loss streaks
- Recent trades

### Log Files

Bot writes to `bot.log`:
```bash
# Follow live logs
tail -f bot.log

# View recent activity
tail -50 bot.log
```

## Utilities

### Manual Redemption

```bash
# Redeem all winning positions
python3 utils/redeem_winners.py

# Clean up worthless losing positions
python3 utils/cleanup_losers.py
```

### Market Discovery

```bash
# Check what markets are currently active
python3 utils/check_15min_markets.py
```

## Troubleshooting

### Bot Not Trading

Check logs for common issues:
- **HALTED: Drawdown exceeds 30%** - Peak balance too high, see state reset below
- **BLOCKED: Already have position** - Bot limits to 1 position per crypto
- **SKIP: Price too high** - Entry price exceeds configured max

### Reset State

If state becomes corrupted:
```bash
# Backup first
cp state/trading_state.json state/backup.json

# Delete state (bot will recreate)
rm state/trading_state.json

# Restart bot
python3 bot/momentum_bot_v12.py
```

### Connection Issues

If API calls fail:
- Check internet connection
- Verify Polygon RPC is accessible
- Try alternative RPC in `.env`:
  ```env
  RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
  ```

## Next Steps

- Review [DEPLOYMENT.md](DEPLOYMENT.md) for VPS setup
- Monitor bot performance for 24 hours
- Adjust position sizing based on risk tolerance
- Set up alerts for halt conditions

## Support

- Issues: https://github.com/mmartoccia/polymarket-autotrader/issues
- Review code before trading with real funds
- Start with small amounts to test
