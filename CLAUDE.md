# Polymarket AutoTrader - AI Assistant Context

**Last Updated:** 2026-01-13
**Bot Version:** v12.1
**Status:** Production - Trading Live on VPS

---

## Project Overview

**Polymarket AutoTrader** is an automated trading bot that trades 15-minute Up/Down binary outcome markets for cryptocurrencies (BTC, ETH, SOL, XRP) on Polymarket.

### Core Strategy

The bot uses a **contrarian fade + momentum confirmation** approach:

1. **Contrarian Fade** - Identifies overpriced sides (>70%) and takes cheap entries on the opposite side (<$0.20)
2. **Momentum Confirmation** - Confirms price movements across 3 exchanges (Binance, Kraken, Coinbase)
3. **Risk Management** - Position sizing, correlation limits, drawdown protection

### Current Performance

- **Live Balance:** $7.21 (as of Jan 14, 2026)
- **Peak Balance:** $161.99 (Jan 13, 2026)
- **Recent Event:** -95% drawdown from trend filter bias (fixed Jan 14)
- **Current Status:** Live trading with fixed trend filter
- **Trading Since:** January 2026
- **Deployment:** Vultr VPS (Mexico City) - 24/7 operation

---

## Architecture

### Directory Structure

```
polymarket-autotrader/
├── bot/                          # Core trading logic
│   ├── momentum_bot_v12.py       # Main production bot (1600+ lines)
│   ├── timeframe_tracker.py      # Multi-timeframe analysis
│   └── ralph_regime_adapter.py   # Regime detection (bull/bear/choppy)
├── dashboard/
│   └── live_dashboard.py         # Real-time terminal monitoring
├── utils/                        # Helper scripts
│   ├── redeem_winners.py         # Manual redemption of winning positions
│   ├── cleanup_losers.py         # Remove worthless positions
│   └── check_15min_markets.py    # Market discovery
├── state/                        # Bot state (gitignored)
│   ├── trading_state.json        # Current balance, mode, streaks
│   └── timeframe_trades.json     # Historical trade data
├── scripts/
│   └── deploy.sh                 # VPS deployment script
├── config/
│   └── .env.example              # Environment template
├── docs/
│   ├── SETUP.md                  # Local development setup
│   └── DEPLOYMENT.md             # VPS deployment guide
├── .claude/                      # AI assistant commands
│   └── commands/                 # Slash commands for common tasks
└── CLAUDE.md                     # This file
```

---

## Key Technical Concepts

### 1. Binary Outcome Markets

Polymarket's 15-minute markets are **binary options**:
- Pay **$1.00** if your prediction is correct
- Pay **$0.00** if your prediction is wrong
- Mid-epoch prices represent **probability estimates**, not actual value

**Example:**
- BTC Down trading at $0.08 means market thinks Down has 8% probability
- If BTC goes down, you get $1.00 per share (12.5x return)
- If BTC goes up, you get $0.00 (total loss)

### 2. Epoch System

Markets run on **15-minute epochs**:
- New epoch every 15 minutes (on the quarter-hour)
- Market opens at epoch start (e.g., 1:00 PM)
- Resolution at epoch end (e.g., 1:15 PM)
- Price at end compared to price at start determines winner

### 3. Trading Strategies

#### Early Momentum (15-300 seconds)
- Entry when price is **$0.12-$0.30**
- Requires **2+ exchanges agreeing** on direction
- Catches early trend formation
- Higher risk, higher reward

#### Contrarian Fade (30-700 seconds)
- Entry when opposite side is **>70%** (overpriced)
- Takes cheap entry **<$0.20** on underpriced side
- Leverages mean reversion
- **Best performer** - many $0.06-$0.13 winners

#### Late Confirmation (720+ seconds)
- Entry when price is **>85%** (high probability)
- Direction must be stable for 3 minutes
- Lower risk, lower reward (but consistent)

### 4. Risk Management

#### Position Sizing (Tiered)
```python
POSITION_TIERS = [
    (30, 0.15),     # Balance < $30: max 15% per trade
    (75, 0.10),     # Balance $30-75: max 10%
    (150, 0.07),    # Balance $75-150: max 7%
    (inf, 0.05),    # Balance > $150: max 5%
]
```

#### Correlation Protection
- Max **4 positions** total (1 per crypto)
- Max **8% exposure** in one direction (all Up or all Down)
- Prevents overexposure to same market conditions

#### Drawdown Protection
- **30% drawdown** = automatic halt
- Tracks **realized cash** only (not unrealized position values)
- Daily loss limit: **$30 or 20%** of balance

#### Trading Modes
Bot automatically adjusts between modes:
- **normal** (default) - Standard sizing
- **conservative** - 80% sizing after 8% loss
- **defensive** - 65% sizing after 15% loss
- **recovery** - 50% sizing after 25% loss
- **halted** - Stopped (drawdown exceeded)

### 5. Fee Economics

Polymarket charges **taker fees** based on probability:

| Probability | Taker Fee |
|-------------|-----------|
| 50% (fair)  | ~3.15%    |
| Near 0%/100%| ~0%       |

**Round-trip fees at 50% = 6.3%** → Need to trade cheap entries (<$0.30) to overcome fees.

### 6. State Management

Bot maintains persistent state in `state/trading_state.json`:

```json
{
  "day_start_balance": 35.23,
  "current_balance": 161.99,
  "peak_balance": 161.99,
  "daily_pnl": 126.76,
  "mode": "normal",
  "consecutive_wins": 0,
  "consecutive_losses": 0,
  "total_trades": 40,
  "total_wins": 27
}
```

**Critical:** State persists across restarts. Reset state file if peak_balance gets too high.

---

## Common Issues & Solutions

### Issue: Bot HALTED with Drawdown Error

**Symptom:**
```
HALTED: Drawdown 40.0% exceeds 30.0% (peak $314.98 -> $189.00)
```

**Cause:** Peak balance includes old unredeemed position values. After redemption, cash increases but peak stays high.

**Solution:**
```bash
# Reset peak_balance to current balance
ssh root@VPS_IP
cd /opt/polymarket-autotrader
python3 << 'EOF'
import json
with open('state/trading_state.json', 'r+') as f:
    state = json.load(f)
    state['peak_balance'] = state['current_balance']
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
EOF
systemctl restart polymarket-bot
```

### Issue: No Trades Being Placed

**Check logs for:**
- `BLOCKED: Already have position` → Bot limits 1 position per crypto
- `SKIP: Price too high` → Entry exceeds max configured price
- `SKIP: Signal strength too low` → Not enough confidence
- `Choppy market` → Trend filter blocking trades

**Debug:**
```bash
tail -f bot.log | grep -E "SIGNAL|BLOCKED|SKIP"
```

### Issue: Position Stuck at 0% Probability

**These are losers** - market went against you:
```bash
# Clean up worthless positions
cd /opt/polymarket-autotrader
python3 utils/cleanup_losers.py
```

### Issue: Winners Not Auto-Redeeming

**Finding Redeemable Positions:**

The Polymarket API returns positions with these key fields:
- `redeemable: true` - Position is ready to be redeemed
- `curPrice: 0.99+` - Position value is near $1.00 (winning)
- `size > 0` - You have shares
- `value = size * curPrice` - Current redemption value

**To check for redeemable positions:**
```python
resp = requests.get(
    "https://data-api.polymarket.com/positions",
    params={"user": WALLET, "limit": 50},
    timeout=10
)

for pos in resp.json():
    size = float(pos.get("size", 0))
    cur_price = float(pos.get("curPrice", 0))
    redeemable = pos.get("redeemable", False)
    value = size * cur_price

    # Ready to redeem if:
    if (redeemable or cur_price >= 0.99) and value >= 1.0:
        print(f"REDEEM: {pos['title']} = ${value:.2f}")
```

**Note:** If the API shows no redeemable positions but the dashboard shows pending redemptions, the positions may have been auto-redeemed already or are still settling on-chain.

---

## Development Workflow

### Making Changes

1. **Edit locally:**
   ```bash
   cd /Volumes/TerraTitan/Development/polymarket-autotrader
   # Edit files
   ```

2. **Test locally:**
   ```bash
   source venv/bin/activate
   python3 bot/momentum_bot_v12.py
   ```

3. **Commit and push:**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

4. **Deploy to VPS:**
   ```bash
   ssh root@216.238.85.11
   cd /opt/polymarket-autotrader
   ./scripts/deploy.sh
   ```

### Testing Changes

**IMPORTANT:** Always test locally before deploying to VPS with real money.

**Safe testing:**
- Use a small test wallet with minimal funds
- Set `MAX_POSITION_USD = 1.10` (minimum bet)
- Monitor for 1-2 epochs before deploying

**Never test on production VPS** - it's trading with real money 24/7.

---

## Code Structure

### Main Bot (`bot/momentum_bot_v12.py`)

**Key Classes:**

1. **`Guardian`** - Risk management
   - `check_kill_switch()` - Drawdown protection
   - `calculate_position_size()` - Tiered sizing
   - `check_correlation_limits()` - Position limits
   - `can_open_position()` - Entry checks

2. **`RecoveryController`** - Mode management
   - `update_mode_from_performance()` - Auto mode adjustment
   - `get_mode_params()` - Mode-specific settings

3. **`RSICalculator`** - Technical indicators
   - Tracks RSI across all cryptos
   - 14-period RSI with 50-period history

4. **`MultiExchangePriceFeed`** - Price aggregation
   - Fetches from Binance, Kraken, Coinbase
   - Detects confluence signals (2+ exchanges agreeing)

5. **`SignalAnalyzer`** - Signal scoring
   - Combines exchange agreement, RSI, magnitude, price value
   - Returns 0-1 confidence score

6. **`FutureWindowTrader`** - Future window analysis (v12.1)
   - Looks ahead 2-3 windows for anomalies
   - Detects momentum lag opportunities

7. **`AutoRedeemer`** - Position redemption
   - Auto-redeems winning positions after epoch resolution
   - Uses Web3 to call CTF contract

### Configuration Constants

All tunable parameters at top of `momentum_bot_v12.py`:

```python
# Position Sizing
MAX_POSITION_USD = 15
MIN_BET_USD = 1.10

# Risk Limits
MAX_DRAWDOWN_PCT = 0.30
DAILY_LOSS_LIMIT_USD = 30
MAX_SAME_DIRECTION_POSITIONS = 4

# Strategy Thresholds
EARLY_MAX_ENTRY = 0.30
CONTRARIAN_MAX_ENTRY = 0.20
MIN_SIGNAL_STRENGTH = 0.72

# Scan Settings
SCAN_INTERVAL = 2.0  # seconds
```

---

## VPS Environment

### Server Details

- **Provider:** Vultr
- **Location:** Mexico City, Mexico (non-US IP)
- **IP:** 216.238.85.11
- **OS:** Ubuntu 24.04 LTS
- **SSH Key:** `~/.ssh/polymarket_vultr`

### Services Running

```bash
# Main trading bot
systemctl status polymarket-bot

# Auto-redemption (if configured)
systemctl status auto-redeem

# Ralph regime adapter (if running)
screen -r ralph
```

### File Locations

- **Bot:** `/opt/polymarket-autotrader/`
- **Logs:** `/opt/polymarket-autotrader/bot.log`
- **State:** `/opt/polymarket-autotrader/state/trading_state.json`
- **Environment:** `/opt/polymarket-autotrader/.env`
- **Service:** `/etc/systemd/system/polymarket-bot.service`

### Monitoring

```bash
# Live logs
tail -f /opt/polymarket-autotrader/bot.log

# Dashboard
python3 /opt/polymarket-autotrader/dashboard/live_dashboard.py

# Service status
systemctl status polymarket-bot

# Recent trades
tail -50 /opt/polymarket-autotrader/bot.log | grep -E "ORDER PLACED|WIN|LOSS"
```

---

## API Integrations

### Polymarket APIs

1. **Gamma API** - Market discovery
   - Endpoint: `https://gamma-api.polymarket.com`
   - Used to find active 15-min markets
   - Rate limit: Generous (no key required)

2. **CLOB API** - Order placement
   - Endpoint: `https://clob.polymarket.com`
   - Requires authentication (derived from wallet key)
   - Rate limit: ~100 req/min

3. **Data API** - Position tracking
   - Endpoint: `https://data-api.polymarket.com/positions`
   - Query by wallet address
   - Used for redemption checks

### Exchange APIs (Price Feeds)

1. **Binance** - `https://api.binance.com/api/v3/ticker/price`
2. **Kraken** - `https://api.kraken.com/0/public/Ticker`
3. **Coinbase** - `https://api.coinbase.com/v2/prices/*/spot`

All are **public APIs** (no keys needed).

### Polygon RPC

- **Default:** `https://polygon-rpc.com`
- Used for: Balance checks, transaction signing, position redemption
- Fallback: Alchemy, Infura (if configured in `.env`)

---

## Dependencies

From `requirements.txt`:

```
py-clob-client>=0.23.0    # Polymarket CLOB SDK
web3>=6.0.0               # Ethereum/Polygon interaction
eth-account>=0.10.0       # Wallet signing
requests>=2.31.0          # HTTP requests
aiohttp>=3.9.0            # Async HTTP (future use)
python-dotenv>=1.0.0      # Environment loading
```

**Python Version:** 3.11+ (uses modern type hints)

---

## Safety & Security

### Credentials

- **NEVER** commit `.env` to git
- **NEVER** expose private keys in logs
- Use dedicated trading wallet (not your main wallet)
- Keep SSH keys secure (`~/.ssh/polymarket_vultr`)

### File Permissions

```bash
chmod 600 .env              # Only owner can read
chmod 700 state/            # Only owner can access
chmod 600 ~/.ssh/*          # SSH key security
```

### Monitoring Alerts

**Watch for:**
- Repeated halt messages
- Consecutive losses (>3)
- Drawdown approaching 30%
- Balance dropping rapidly

**Set alerts on:**
- Service failures (`systemctl status`)
- Log errors (`grep ERROR bot.log`)
- Unusual gas costs (>$1 per trade)

---

## Performance Metrics

### Win Rate Targets

- **Overall:** 60%+ (accounting for fees)
- **Contrarian:** 70%+ (cheap entries = better odds)
- **Late Confirmation:** 85%+ (high probability = high win rate)

### Profitability Breakeven

With 6.3% round-trip fees at 50% probability:
- Need **~53% win rate** to break even
- Target **60%+ win rate** for profitability
- Cheap entries (<$0.30) have lower fees → easier to profit

### Historical Performance

- **Jan 13, 2026:** +437% ($35 → $189) - Peak day
- **Jan 14, 2026:** -95% ($157 → $7) - Trend filter bias caused directional imbalance
  - Issue: 96.5% UP bias due to asymmetric filtering in weak positive trends
  - Root cause: Trend filter blocked 319 DOWN bets, 0 UP bets
  - Fix: Added STRONG_TREND_THRESHOLD = 1.0 to allow both directions in weak trends
  - Status: Fixed and deployed
- **Best trades:** Contrarian fades at $0.06-$0.13 entries

---

## Future Enhancements

### Planned Features

1. **Multi-timeframe confirmation** - Use 1h/4h trends to filter trades
2. **Volatility adjustment** - Reduce sizing during high volatility
3. **Better redemption** - Auto-redeem immediately after resolution
4. **Trade journaling** - Detailed trade analytics
5. **Backtesting framework** - Test strategies on historical data

### Known Limitations

1. **No orderbook analysis** - Could improve entry timing
2. **Single exchange per crypto** - Could aggregate more sources
3. **No position hedging** - Once in, committed to outcome
4. **Manual state resets** - Peak balance tracking needs improvement
5. **No mobile alerts** - Would be useful for halts/big wins

---

## Troubleshooting Commands

```bash
# Check bot status
systemctl status polymarket-bot

# View recent logs
tail -50 bot.log

# Follow live logs
tail -f bot.log

# Check for errors
grep -i error bot.log | tail -20

# Check balance
python3 << 'EOF'
import requests, os
from dotenv import load_dotenv
load_dotenv()
wallet = os.getenv('POLYMARKET_WALLET')
rpc = 'https://polygon-rpc.com'
usdc = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
resp = requests.post(rpc, json={
    'jsonrpc': '2.0',
    'method': 'eth_call',
    'params': [{'to': usdc, 'data': f'0x70a08231000000000000000000000000{wallet[2:]}'}, 'latest'],
    'id': 1
})
print(f"Balance: ${int(resp.json()['result'], 16) / 1e6:.2f}")
EOF

# Restart bot
systemctl restart polymarket-bot

# Stop bot
systemctl stop polymarket-bot

# View state
cat state/trading_state.json | python3 -m json.tool
```

---

## Git Workflow

### Branches

- **main** - Production (deployed to VPS)
- **dev** - Development (test locally before merging)

### Commit Guidelines

Use descriptive commit messages:
```bash
# Good
git commit -m "Fix drawdown calculation to use realized cash only"
git commit -m "Add filter to exclude 0% positions from dashboard"

# Bad
git commit -m "fix bug"
git commit -m "update"
```

### Deployment

```bash
# After pushing to main
ssh root@216.238.85.11 "cd /opt/polymarket-autotrader && ./scripts/deploy.sh"
```

---

## Support & Resources

- **GitHub:** https://github.com/mmartoccia/polymarket-autotrader
- **Issues:** Report bugs/features via GitHub Issues
- **Polymarket Docs:** https://docs.polymarket.com
- **CLOB Client:** https://github.com/Polymarket/py-clob-client

---

## Version History

- **v12.1** (Jan 13, 2026) - Current production
  - Future window trading
  - Drawdown fix (cash-only tracking)
  - Dashboard 0% filter
  - Separated into clean repo

- **v12** (Jan 12, 2026)
  - Lower entry max ($0.30)
  - Fixed contrarian logic
  - Stronger signals (0.72 min)
  - Disabled fallback bets

- **v11** (Jan 11, 2026)
  - Epoch boundary strategy
  - Bot exit detection

- **v10 and earlier** - Historical iterations

---

## Known Issues and Fixes

### Jan 14, 2026: Trend Filter Directional Bias

**Issue:** Trend filter created 96.5% UP bias in weak positive trends
- Blocked 319 DOWN bets, 0 UP bets during Jan 13-14 session
- Crypto had weak upward trend (scores 0.70-1.00)
- Markets were choppy within slight uptrend → UP trades lost to mean reversion
- Result: Lost $149.54 (-95.4%) in ~12 hours

**Root Cause:** Asymmetric filtering in `TREND_FILTER_ENABLED` logic
```python
# Old behavior (asymmetric):
if direction == "Down" and trend_score > -MIN_TREND_SCORE:
    # Always blocked DOWN when trend slightly positive
    continue
```

**Fix Applied:** Added `STRONG_TREND_THRESHOLD = 1.0`
```python
# New behavior (symmetric):
if abs(trend_score) >= STRONG_TREND_THRESHOLD:
    # Only filter on STRONG trends
    if direction == "Down" and trend_score > -MIN_TREND_SCORE:
        continue
else:
    # Weak trends: allow BOTH directions
    pass
```

**Strategy:**
- **Choppy markets** (trend < 0.15): Skip entirely
- **Weak trends** (0.15-1.0): Allow BOTH directions (prevents bias)
- **Strong trends** (> 1.0): Apply directional filter

**Monitoring:**
- Directional balance should be 40-60% over 50+ trades
- If >70% same direction → further tuning needed
- Win rate should improve from ~5% to 50-60%

**Status:** Fixed and deployed Jan 14, 2026 14:00 UTC

---

**Remember:** This bot trades with real money. Always test changes locally, monitor performance, and never deploy untested code to the VPS.
