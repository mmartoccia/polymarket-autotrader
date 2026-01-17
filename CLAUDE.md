# Polymarket AutoTrader - AI Assistant Context

**Last Updated:** 2026-01-15 18:30 UTC
**Bot Version:** v12.1 (ML Random Forest + Shadow Trading System)
**Status:** Production - Trading Live on VPS with ML Model

---

## Project Overview

**Polymarket AutoTrader** is an automated trading bot that trades 15-minute Up/Down binary outcome markets for cryptocurrencies (BTC, ETH, SOL, XRP) on Polymarket.

### Core Strategy

The bot now uses **ML Random Forest** model (as of Jan 15, 2026):

1. **Machine Learning** - Random Forest trained on 711 samples, 67.3% test accuracy
2. **High Confidence Filtering** - Only trades when ML confidence >55%
3. **Risk Management** - Position sizing, conflict detection, drawdown protection

### Current Performance

- **Live Balance:** $200.97 (as of Jan 16, 2026 02:00 UTC)
- **True Peak Balance:** $300.00 (historical high)
- **Current Drawdown:** 33% ($99 loss from peak)
- **Status:** ⚠️ **ACTIVE** - Trading, but exceeded 30% drawdown threshold
- **Recent Events:**
  - Jan 16 01:56: Discovered state file balance desync ($186 error)
  - Jan 16 01:56: Corrected state file to match on-chain balance ($200.97)
  - Jan 15: Recovered from $6.81 to $200.97 (+$194 profit)
  - **CRITICAL:** Drawdown protection failed due to state tracking desync
- **Critical Fixes Applied:**
  - ✅ Position conflict detection (live API checking)
  - ✅ Auto-redemption fixed (checks every cycle)
  - ✅ Trade logging working (direct SQLite writes)
  - ✅ Pure ML mode (no agent fallback)
- **Shadow Trading:** Enabled with 23 strategies but not logging decisions (needs debugging)
- **Trading Since:** January 2026
- **Deployment:** Vultr VPS (Mexico City) - 24/7 operation

**Current Focus:** Performance optimization (Jan 15, 2026)
- Goal: Improve win rate from 56% to 60-65%
- Approach: Per-agent tracking, selective trading, Kelly sizing, automated promotion
- Timeline: 4-week optimization roadmap (see `PRD-strategic.md`)
- Current work: Week 1 implementation (see `PRD.md` for user stories)

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
├── simulation/                   # Shadow trading system (NEW!)
│   ├── strategy_configs.py       # Strategy library & configurations
│   ├── shadow_strategy.py        # Virtual trading engine
│   ├── orchestrator.py           # Multi-strategy coordinator
│   ├── trade_journal.py          # SQLite database for logging
│   ├── dashboard.py              # Live comparison dashboard
│   ├── analyze.py                # CLI analysis tool
│   ├── export.py                 # CSV export utility
│   └── trade_journal.db          # SQLite database (gitignored)
├── sentinel/                     # Autonomous monitoring system (NEW!)
│   ├── sentinel_monitor.sh       # Background polling daemon
│   ├── sentinel.sh               # Main orchestrator
│   ├── sentinel_diagnose.md      # Claude prompt template
│   ├── sentinel_config.json      # Configuration
│   ├── test_sentinel.sh          # Integration tests
│   ├── events/                   # Event queue
│   ├── history/                  # Audit trail
│   └── state/                    # Runtime state (gitignored)
├── optimizer/                    # Hourly auto-tuning system (NEW!)
│   ├── optimizer.py              # Main cron entry point
│   ├── optimizer_config.json     # Configuration and bounds
│   ├── data_collector.py         # Collects trades/skips from DB
│   ├── analyzer.py               # Performance analysis
│   ├── tuning_rules.py           # Parameter adjustment logic
│   ├── executor.py               # Applies changes to config files
│   ├── reporter.py               # Telegram reporting
│   ├── history/                  # Adjustment audit trail
│   └── state/                    # Runtime state (gitignored)
└── CLAUDE.md                     # This file
```

---

## Shadow Trading System

**NEW in Jan 14, 2026**: The bot now includes a **shadow trading system** that runs alternative strategies in parallel with the live bot for performance comparison and strategy optimization.

### What is Shadow Trading?

Shadow trading runs **hypothetical strategies** alongside the live bot:
- All strategies receive the same market data at the same time
- Shadow strategies make virtual trades (no real money at risk)
- Track virtual positions, balance, and performance metrics
- Compare strategies side-by-side to find optimal parameters

**Benefits:**
- **Zero Risk** - Shadow trades are virtual (no real money)
- **Real-time Testing** - Against live market conditions (not historical)
- **Apples-to-apples Comparison** - All strategies tested on identical data
- **Continuous Learning** - Accumulate performance data organically

### How It Works

```
Live Bot (current strategy)
       ↓
Market Data Broadcast
       ↓
Shadow Strategies (conservative, aggressive, contrarian_focused, etc.)
       ↓
Virtual Trades Executed
       ↓
Outcomes Resolved After Epoch
       ↓
SQLite Database Logging
       ↓
Comparison Reports & Analysis
```

### Configuration

Shadow trading is controlled via `config/agent_config.py`:

```python
# Master enable/disable
ENABLE_SHADOW_TRADING = True  # Set False to disable

# Which strategies to run
SHADOW_STRATEGIES = [
    'conservative',           # High thresholds (0.75/0.60)
    'aggressive',             # Lower thresholds (0.55/0.45)
    'contrarian_focused',     # Boost SentimentAgent
    'momentum_focused',       # Boost TechAgent
    'no_regime_adjustment',   # Disable regime adjustments
]

# Virtual starting balance per strategy
SHADOW_STARTING_BALANCE = 100.0

# Database path
SHADOW_DB_PATH = 'simulation/trade_journal.db'
```

### Available Strategies

The `STRATEGY_LIBRARY` in `simulation/strategy_configs.py` includes:

1. **default** - Current production strategy (0.40/0.40/0.30)
2. **conservative** - High thresholds (0.75/0.60), fewer trades
3. **aggressive** - Lower thresholds (0.55/0.45), more trades
4. **contrarian_focused** - 1.5x SentimentAgent weight, fade overpriced
5. **momentum_focused** - 1.5x TechAgent weight, follow confluence
6. **no_regime_adjustment** - Disable regime-based weight adjustments
7. **equal_weights_static** - No adaptive/regime adjustments
8. **high_confidence_only** - Extreme filter (0.80/0.70/0.50)
9. **low_barrier** - Permissive (0.30/0.30/0.20)

### Usage

#### 1. Live Dashboard (Auto-refresh)

Watch real-time performance comparison:

```bash
python3 simulation/dashboard.py
# Refreshes every 5 seconds

# Custom interval:
python3 simulation/dashboard.py --interval 10
```

**Sample Output:**
```
================================================================================
                        🎯 SHADOW TRADING DASHBOARD 🎯
================================================================================

Rank   Strategy                  Trades   W/L      Win Rate   Total P&L    Avg P&L   ROI
------------------------------------------------------------------------------------------------
🟢 1   contrarian_focused        12       8W/4L    66.7%      $+8.45       $+0.70    🟢 +8.5%
🟢 2   aggressive                18       11W/7L   61.1%      $+5.20       $+0.29    +5.2%
⚪ 3   default (LIVE)            10       6W/4L    60.0%      $+3.80       $+0.38    +3.8%
🔴 4   momentum_focused          15       8W/7L    53.3%      $-2.70       $-0.18    🔴 -2.7%

================================================================================
🏆 Best P&L: contrarian_focused ($+8.45)
🎯 Best Win Rate: contrarian_focused (66.7%)
📊 Overall: 55 resolved trades, 60.0% win rate
================================================================================
```

#### 2. CLI Analysis

Query performance data:

```bash
# Compare all strategies
python3 simulation/analyze.py compare

# View specific strategy details
python3 simulation/analyze.py details --strategy contrarian_focused

# Recent decisions
python3 simulation/analyze.py decisions --limit 50
```

#### 3. Export to CSV

Export data for external analysis:

```bash
# Export performance summary
python3 simulation/export.py performance -o results.csv

# Export all trades
python3 simulation/export.py trades -o trades.csv

# Export outcomes
python3 simulation/export.py outcomes -o outcomes.csv

# Export specific strategy
python3 simulation/export.py trades --strategy conservative -o conservative_trades.csv
```

### Database Schema

SQLite database at `simulation/trade_journal.db`:

**Tables:**
- `strategies` - Strategy configurations and metadata
- `decisions` - Every decision made (trade or skip)
- `trades` - Executed trades (real + shadow)
- `outcomes` - Resolved outcomes (win/loss)
- `agent_votes` - Individual agent votes per decision
- `performance` - Aggregated metrics snapshots

Query directly with:
```bash
sqlite3 simulation/trade_journal.db
sqlite> SELECT * FROM strategies;
sqlite> SELECT strategy, win_rate, total_pnl FROM performance ORDER BY total_pnl DESC;
```

### Adding Custom Strategies

Create new strategies in `simulation/strategy_configs.py`:

```python
STRATEGY_LIBRARY['my_custom'] = StrategyConfig(
    name='my_custom',
    description='Test extreme thresholds',
    consensus_threshold=0.80,  # Very high bar
    min_confidence=0.70,
    adaptive_weights=False,
    agent_weights={
        'TechAgent': 2.0,      # Double weight
        'SentimentAgent': 0.5,
        'RegimeAgent': 0.5,
        'RiskAgent': 1.0
    }
)
```

Then add to `config/agent_config.py`:
```python
SHADOW_STRATEGIES = [
    'default',
    'my_custom'
]
```

### Performance Snapshots

Shadow trading logs performance after every resolved trade:
- Balance updates
- Win/loss tracking
- P&L calculations
- ROI metrics

This provides granular historical data for analyzing strategy evolution over time.

### Integration with Live Bot

Shadow trading is **non-invasive**:
- Runs alongside live bot without modifying core logic
- Minimal CPU overhead (< 5% for 5 strategies)
- No impact on live trading speed
- Can be disabled anytime via config flag

Live bot broadcasts market data to orchestrator on each scan cycle. Shadow strategies make independent decisions and track virtual positions. Outcomes are resolved after epoch ends (when live bot redeems positions).

---

## Sentinel Monitoring System

**NEW in Jan 17, 2026**: Sentinel is an event-driven autonomous monitoring system that watches the trading bot for halt events, performance degradation, and configurable alerts.

### Overview

Sentinel runs **locally on the Mac**, polling the VPS state every 30 seconds:
- Detects bot halts within 30 seconds of occurrence
- Notifies user via Telegram with diagnostic summary
- Auto-fixes safe issues if user doesn't respond within 15 minutes
- Prevents fix loops by escalating after 2 consecutive auto-fixes
- Supports configurable alert rules (balance, win rate, drawdown, etc.)

### Architecture

```
┌─────────────────┐     SSH (every 30s)     ┌─────────────────┐
│   Mac (Local)   │ ──────────────────────▶ │   VPS (Remote)  │
│                 │                          │                 │
│ sentinel_       │ ◀────── State JSON ───── │ Bot State Files │
│ monitor.sh      │                          │ Bot Logs        │
│                 │                          │                 │
└────────┬────────┘                          └─────────────────┘
         │
         │ On halt detected
         ▼
┌─────────────────┐
│ sentinel.sh     │ ──────▶ Claude Code (diagnostic analysis)
│ (orchestrator)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Telegram     │ ◀────── Notification ──── User Response
│   (notify user) │ ────────────────────────▶ /approve, /deny
└─────────────────┘
```

### Directory Structure

```
sentinel/
├── sentinel_monitor.sh     # Background polling daemon
├── sentinel.sh             # Main orchestrator script
├── sentinel_diagnose.md    # Claude prompt template
├── sentinel_config.json    # Configuration file
├── test_sentinel.sh        # Integration test suite
├── events/
│   └── queue.json          # Pending events queue
├── history/
│   └── actions.log         # Audit trail of all actions
└── state/                  # Runtime state (gitignored)
    ├── monitor.pid         # Daemon process ID
    ├── monitor.log         # Daemon logs
    ├── last_state.json     # Last polled VPS state
    ├── heartbeat           # Health check timestamp
    ├── recent_fixes.json   # Fix loop tracking
    ├── rate_limit.json     # Hourly rate tracking
    ├── alert_cooldowns.json # Alert spam prevention
    └── error.log           # Error details with stack traces
```

### Starting and Stopping the Monitor

```bash
# Start the background monitor
./sentinel/sentinel_monitor.sh start

# Check if monitor is running
./sentinel/sentinel_monitor.sh status

# Stop the monitor
./sentinel/sentinel_monitor.sh stop

# Check monitor health (heartbeat, SSH failures, PID)
./sentinel/sentinel_monitor.sh health
```

**Sample Status Output:**
```
Sentinel Monitor Status
=======================
Status: RUNNING (PID 12345)
Started: 2026-01-17 10:30:00
Last poll: 2026-01-17 10:31:30
Uptime: 1 minute
```

### Using the /auto-manage Skill

The `/auto-manage` skill provides manual interaction with Sentinel from Claude Code.

**Default (no args) - Run manual diagnostic:**
```
/auto-manage
```
Gathers VPS state, recent logs, and on-chain balance, then runs Claude analysis.

**Subcommands:**
```bash
/auto-manage status    # Monitor status, pending events, rate limits
/auto-manage start     # Start the monitor daemon
/auto-manage stop      # Stop the monitor daemon
/auto-manage history   # Show last 20 actions from audit log
/auto-manage config    # Display current configuration
```

**Example `/auto-manage status` Output:**
```
📊 Sentinel Status
==================
Monitor: RUNNING (PID 12345)
Last Poll: 2026-01-17 10:31:30 UTC

Last VPS State:
- Mode: normal
- Balance: $185.50
- Peak: $200.00
- Drawdown: 7.3%

Pending Events: 0
Rate Limit: 1/3 fixes used this hour
```

### Configuration Options

All settings in `sentinel/sentinel_config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `polling.interval_seconds` | 30 | How often to check VPS state |
| `polling.ssh_timeout_seconds` | 10 | SSH connection timeout |
| `rate_limits.max_auto_fixes_per_hour` | 3 | Max auto-fixes before pause |
| `rate_limits.consecutive_fix_limit` | 2 | Max same-issue fixes before escalate |
| `safety.balance_floor` | 50.0 | Never auto-fix if balance < $50 |
| `safety.min_confidence_for_auto_fix` | 70 | Require 70%+ confidence to auto-fix |
| `escalation.telegram_timeout_seconds` | 900 | Wait 15 min for user response |

**Configurable Alert Rules:**

```json
"alerts": [
  {"name": "low_balance", "condition": "balance < 75", "severity": "warning", "cooldown_minutes": 60},
  {"name": "critical_balance", "condition": "balance < 30", "severity": "critical", "cooldown_minutes": 30},
  {"name": "high_drawdown", "condition": "drawdown_pct > 25", "severity": "warning", "cooldown_minutes": 60},
  {"name": "losing_streak", "condition": "consecutive_losses >= 3", "severity": "warning", "cooldown_minutes": 30}
]
```

### Safety Guardrails

Sentinel has multiple layers of protection:

1. **Kill Switch** - Create `sentinel/state/KILL_SWITCH` file to stop all processing
   ```bash
   touch sentinel/state/KILL_SWITCH   # Enable kill switch
   rm sentinel/state/KILL_SWITCH      # Disable kill switch
   ```

2. **Balance Floor** - Never auto-fix if balance < $50 (always escalate to user)

3. **Rate Limiting** - Max 3 auto-fixes per hour

4. **Fix Loop Detection** - Escalate after 2 consecutive fixes for same issue type

5. **Confidence Threshold** - Only auto-fix if Claude confidence >= 70%

6. **Manual Override** - User can always /deny or /halt to stop actions

### Available Auto-Fix Actions

| Action | What It Does |
|--------|--------------|
| `reset_peak_balance` | Sets peak_balance = current_balance, mode = "normal" |
| `resume_trading` | Sets mode = "normal", clears halt_reason |
| `reset_loss_streak` | Sets consecutive_losses = 0, mode = "normal" |
| `restart_bot` | Runs `systemctl restart polymarket-bot` |

### Example Telegram Messages

**Halt Alert:**
```
🚨 SENTINEL ALERT

Bot Status: HALTED
Reason: Drawdown 35.0% exceeds 30.0%
Detected: 2026-01-17 10:30:15 UTC

📊 Financial Status:
• Balance: $130.00
• Peak: $200.00
• Drawdown: 35.0%

🔍 Analysis:
Peak balance appears stale from unredeemed positions.
Current drawdown is due to tracking issue, not actual losses.

💡 Recommendation:
Action: reset_peak_balance
Confidence: 85%

⏰ Respond within 15 minutes or auto-fix will execute.

Commands:
• /approve - Execute recommended action
• /deny - Leave bot halted
• /custom <action> - Specify different action
```

**Auto-Fix Notification (after timeout):**
```
✅ SENTINEL AUTO-FIX

Action Executed: reset_peak_balance
Time: 2026-01-17 10:45:15 UTC

📋 Details:
• Reason: Peak balance stale from unredeemed positions
• Confidence: 85%
• Peak: $200.00 → $130.00
• Mode: halted → normal

Reply /halt to stop if needed.
```

**Alert Notification:**
```
⚠️ SENTINEL WARNING

Alert: losing_streak
Condition: consecutive_losses >= 3

📊 Current State:
• Balance: $145.00
• Consecutive Losses: 3
• Mode: normal

This is an informational alert. No action required.
```

### Troubleshooting

**Monitor not starting:**
```bash
# Check if already running
./sentinel/sentinel_monitor.sh status

# Check for stale PID file
cat sentinel/state/monitor.pid
ps aux | grep sentinel

# Remove stale PID and restart
rm sentinel/state/monitor.pid
./sentinel/sentinel_monitor.sh start
```

**Not receiving Telegram notifications:**
```bash
# Test Telegram connection
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cd /opt/polymarket-autotrader && python3 -c \"
from bot.telegram_handler import TelegramBot
bot = TelegramBot()
print('Enabled:', bot.enabled)
bot.send_message_sync('Test from Sentinel')
\""
```

**SSH failures:**
```bash
# Check SSH connection
ssh -i ~/.ssh/polymarket_vultr -o ConnectTimeout=10 root@216.238.85.11 "echo OK"

# Check error log for details
tail -20 sentinel/state/error.log
```

**Events not processing:**
```bash
# Check pending events
cat sentinel/events/queue.json | python3 -m json.tool

# Check if orchestrator is locked
ls -la sentinel/state/sentinel.lock

# Manual process pending events
./sentinel/sentinel.sh
```

**Health check failed:**
```bash
# Run health check
./sentinel/sentinel_monitor.sh health

# Check heartbeat age
cat sentinel/state/heartbeat

# Force restart
./sentinel/sentinel_monitor.sh stop
./sentinel/sentinel_monitor.sh start
```

### Running Integration Tests

```bash
./sentinel/test_sentinel.sh

# Sample output:
# =============================================
#        SENTINEL INTEGRATION TESTS
# =============================================
#
# [PASS] jq is installed
# [PASS] Directory structure exists
# [PASS] Config file is valid JSON
# ...
#
# =============================================
#              TEST SUMMARY
# =============================================
# Passed: 20/20
# Failed: 0/20
#
# All tests passed!
```

---

## Optimizer System

**NEW in Jan 17, 2026**: Optimizer is an automated hourly performance review and auto-tuning system that runs on the VPS via cron. It analyzes trading activity, identifies issues (inactivity or poor performance), and auto-adjusts parameters within safe bounds.

### Overview

Optimizer runs **hourly on the VPS** via cron:
- Analyzes last 2 hours of trading data
- Detects zero trades (inactivity) or poor win rate (<50%)
- Identifies which filters are blocking trades
- Auto-tunes parameters to optimize trade flow
- Sends Telegram reports (silent when healthy, alerts on issues)
- Maintains full audit trail of all adjustments

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPS (Cron Hourly)                       │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │    Data      │───▶│   Analyzer   │───▶│   Tuning     │      │
│  │  Collector   │    │              │    │   Rules      │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│         │                                        │              │
│         │ Reads                                  │ Selects      │
│         ▼                                        ▼              │
│  ┌──────────────┐                        ┌──────────────┐      │
│  │ trade_journal│                        │   Executor   │      │
│  │  .db + logs  │                        │ (apply adj.) │      │
│  └──────────────┘                        └──────┬───────┘      │
│                                                  │              │
│                                                  │ Modifies     │
│                                                  ▼              │
│                                          ┌──────────────┐      │
│                                          │  Bot Config  │      │
│                                          │    Files     │      │
│                                          └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Reports
                              ▼
                       ┌──────────────┐
                       │   Telegram   │
                       │  (hourly)    │
                       └──────────────┘
```

### Directory Structure

```
optimizer/
├── optimizer.py            # Main orchestrator (cron entry point)
├── optimizer_config.json   # Configuration and bounds
├── data_collector.py       # Collects trades, skips, vetoes from DB/logs
├── analyzer.py             # Analyzes performance and skip patterns
├── tuning_rules.py         # Decision logic for parameter adjustments
├── executor.py             # Applies adjustments to config files
├── reporter.py             # Telegram reporting
├── test_optimizer.py       # Integration tests
├── install_cron.sh         # Install cron job on VPS
├── uninstall_cron.sh       # Remove cron job
├── history/
│   └── adjustments.txt     # Audit trail of all adjustments
└── state/                  # Runtime state (gitignored)
    ├── last_review.json    # Results of last review
    ├── rate_limit.json     # Rate limiting state
    └── parameter_history.json  # Per-parameter change history
```

### Tunable Parameters

| Parameter | File | Current | Min | Max | Step |
|-----------|------|---------|-----|-----|------|
| MAX_ENTRY_PRICE_CAP | bot/intra_epoch_bot.py | 0.50 | 0.35 | 0.65 | 0.05 |
| MIN_PATTERN_ACCURACY | bot/intra_epoch_bot.py | 0.735 | 0.65 | 0.80 | 0.01 |
| CONSENSUS_THRESHOLD | config/agent_config.py | 0.40 | 0.30 | 0.55 | 0.05 |
| MIN_CONFIDENCE | config/agent_config.py | 0.50 | 0.35 | 0.65 | 0.05 |
| EDGE_BUFFER | bot/intra_epoch_bot.py | 0.05 | 0.02 | 0.10 | 0.01 |

### Protected Parameters (Never Auto-Adjusted)

These safety-critical parameters are never modified by Optimizer:
- RISK_MAX_DRAWDOWN
- RISK_DAILY_LOSS_LIMIT
- RISK_POSITION_TIERS
- Agent enable/disable flags

### Tuning Rules

Optimizer applies these rules based on analysis:

**When too few trades (0 in 2 hours):**
| Rule | Trigger | Action |
|------|---------|--------|
| too_few_trades_entry_price | >40% SKIP_ENTRY_PRICE | Increase MAX_ENTRY_PRICE_CAP |
| too_few_trades_weak_pattern | >40% SKIP_WEAK | Decrease MIN_PATTERN_ACCURACY |
| too_few_trades_consensus | >40% consensus-related | Decrease CONSENSUS_THRESHOLD |

**When poor performance (win rate < 50%):**
| Rule | Trigger | Action |
|------|---------|--------|
| poor_win_rate_tighten | Win rate < 50% | Increase MIN_PATTERN_ACCURACY, CONSENSUS_THRESHOLD |

### Using /optimizer-status

The `/optimizer-status` skill checks optimizer status and history:

```bash
/optimizer-status           # Show last review and current params
/optimizer-status history   # Show last 20 adjustments
/optimizer-status bounds    # Display tuning bounds
/optimizer-status run       # Manual dry-run
/optimizer-status run --apply  # Manual run with changes applied
```

### Viewing Adjustment History

```bash
# From local (via SSH)
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cat /opt/polymarket-autotrader/optimizer/history/adjustments.txt | tail -20"

# On VPS directly
cat /opt/polymarket-autotrader/optimizer/history/adjustments.txt
```

### Manually Triggering Optimizer

```bash
# Dry-run (see what would happen without applying)
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cd /opt/polymarket-autotrader && venv/bin/python3 optimizer/optimizer.py --dry-run"

# Apply changes
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cd /opt/polymarket-autotrader && venv/bin/python3 optimizer/optimizer.py"
```

### Cron Schedule

Optimizer runs at minute 0 of every hour:
```
0 * * * * cd /opt/polymarket-autotrader && /opt/polymarket-autotrader/venv/bin/python3 optimizer/optimizer.py >> optimizer/cron.log 2>&1
```

Install/uninstall:
```bash
# Install (on VPS)
./optimizer/install_cron.sh

# Uninstall (on VPS)
./optimizer/uninstall_cron.sh

# Verify
crontab -l | grep optimizer
```

### Example Telegram Report

**Healthy report (silent):**
```
✅ OPTIMIZER REPORT (14:00 UTC)
Period: Last 1h | Status: HEALTHY

📊 Trades
  Count: 8 (5 resolved)
  Record: 3W / 2L (60.0%)
  P&L: +$4.50

💰 Balance
  Current: $185.50
  Peak: $200.00 (DD: 7.3%)
  Daily P&L: +$12.30

🚫 Skips
  Total: 45
  • SKIP_ENTRY_PRICE: 18 (40.0%)
  • SKIP_WEAK: 12 (26.7%)
  • SKIP_CONFLUENCE: 8 (17.8%)

👍 No adjustments needed
```

**Alert report (with sound):**
```
🚨 OPTIMIZER REPORT (14:00 UTC)
Period: Last 2h | Status: ALERT

📊 Trades
  No trades in period

🚫 Skips
  Total: 120
  • SKIP_ENTRY_PRICE: 72 (60.0%)
  • SKIP_WEAK: 30 (25.0%)
  • SKIP_CONFLUENCE: 12 (10.0%)

⚠️ Issues
  • No trades in last 2 hours
  • 60.0% of skips due to SKIP_ENTRY_PRICE

🔧 Adjustments
  • MAX_ENTRY_PRICE_CAP: 0.50 → 0.55
    (60% skips due to entry price filter)

🔍 Diagnosis: skip_dominated
```

### Example Adjustment Log Entry

```
[2026-01-17 14:00:15 UTC] MAX_ENTRY_PRICE_CAP: 0.50 -> 0.55 (bot/intra_epoch_bot.py) - 60% skips due to entry price filter
```

### Safety Features

1. **Rate Limiting** - Max 1 adjustment per parameter per hour
2. **Bounds Enforcement** - Parameters never exceed min/max from config
3. **Protected Parameters** - Safety-critical params never modified
4. **Backup Files** - Creates .bak before any modification
5. **Audit Trail** - All changes logged to history/adjustments.txt
6. **Dry-Run Mode** - Test without applying changes

### Troubleshooting

**Cron not running:**
```bash
# Check cron service
systemctl status cron

# Check cron log
tail -50 /opt/polymarket-autotrader/optimizer/cron.log

# Test manually
cd /opt/polymarket-autotrader && venv/bin/python3 optimizer/optimizer.py --dry-run
```

**No adjustments when expected:**
```bash
# Check rate limiting state
cat /opt/polymarket-autotrader/optimizer/state/rate_limit.json

# Check last review results
cat /opt/polymarket-autotrader/optimizer/state/last_review.json | python3 -m json.tool
```

**Telegram not sending:**
```bash
# Test Telegram
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cd /opt/polymarket-autotrader && python3 -c \"
from bot.telegram_handler import TelegramBot
bot = TelegramBot()
print('Enabled:', bot.enabled)
bot.send_message_sync('Test from Optimizer')
\""
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

### 7. Optimization Roadmap (Jan 15, 2026)

**Current Performance:**
- Win Rate: 56-60% (above 53% breakeven)
- Balance: $254.61 (recovered from $7.09 this morning)
- Shadow Trading: 27 strategies running in parallel

**4-Week Optimization Plan:**
1. **Week 1:** Per-agent performance tracking
   - Identify which agents help vs hurt
   - Disable underperformers (<50% win rate)
   - Expected: +2-3% win rate improvement

2. **Week 2:** Selective trading enhancement
   - Shadow test higher thresholds (0.80/0.70)
   - Target: 5-10 trades/day at 65%+ win rate
   - Expected: Better risk-adjusted returns

3. **Week 3:** Kelly Criterion position sizing
   - Mathematically optimal sizing based on edge
   - Expected: +10-20% ROI improvement

4. **Week 4:** Automated optimization infrastructure
   - Auto-promotion of outperforming shadow strategies
   - Alert system for performance degradation
   - Expected: Continuous optimization without manual work

**Target Metrics:**
- Win Rate: 60-65% (from 56%)
- Monthly ROI: +20-30% (from +10-20%)
- Automated: Yes (continuous optimization)

**See `PRD-strategic.md` for full 4-week plan and `PRD.md` for current week's user stories.**

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

### VPS Access for Claude

**IMPORTANT:** Claude has full SSH access to the VPS and can run commands remotely:

**SSH Key Location:** `~/.ssh/polymarket_vultr`

```bash
# Direct SSH commands (preferred method) - MUST use SSH key
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "command here"

# Examples:
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "tail -100 /opt/polymarket-autotrader/bot.log"
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "systemctl status polymarket-bot"
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "python3 /opt/polymarket-autotrader/scripts/analyze.py"
```

**Key capabilities:**
- Read bot logs directly from VPS
- Check systemd service status
- Run analysis scripts on live data
- Monitor real-time trading activity
- Debug issues without manual intervention

**Note:** Always use full paths when running scripts on VPS (e.g., `/opt/polymarket-autotrader/bot.log`)

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
4. **Manual state resets** - Peak balance tracking needs improvement (Sentinel can auto-fix)
5. **Sentinel requires Mac online** - Runs locally, not on VPS

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

- **Entry Price Cap $0.50** (Jan 17, 2026 18:30 UTC) - Current production
  - Added MAX_ENTRY_PRICE_CAP = $0.50 to intra_epoch_bot.py
  - Backtest of 9 trades showed all 3 losses were at high entries ($0.55-$0.72)
  - High entries have unfavorable risk/reward: risk $0.60 to win $0.40
  - With cap at $0.50: risk $0.50 to win $0.50 (1:1 at worst)
  - Expected: Fewer trades but better risk-adjusted returns
  - See "Jan 17, 2026: Entry Price Cap Adjustment" in Known Issues for full analysis

- **Contrarian Re-enabled** (Jan 16, 2026 15:19 UTC)
  - Re-enabled ENABLE_CONTRARIAN_TRADES after market analysis showed choppy regime
  - SentimentAgent now active (90% confidence votes observed)
  - Rationale: Agents showing conflicting signals, neutral funding rates, no clear trend
  - Expected: 5-10 trades/day at 65-70% win rate with cheap entries (<$0.20)
  - Risk: Low (contrarian only triggers on >70% overpriced markets)
  - Monitoring: Will disable if regime changes to strong BULL/BEAR

- **Optimization Focus** (Jan 15, 2026) - Strategic direction
  - 4-week roadmap: Per-agent tracking, selective trading, Kelly sizing, automation
  - Shadow trading system fixed (now broadcasting in both ML and agent modes)
  - PRD restructured: Focus on optimization over complexity
  - User-approved priorities: Quality over quantity, data-driven decisions

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

**Post-Fix Testing Results (Jan 14, 2026 14:00-14:30 UTC):**
- Two DOWN positions placed before restart resolved as losses (BTC Down, ETH Down)
- Both positions showed mean reversion (improved from 3.5% → 14% probability mid-epoch)
- But BULL momentum continued through epoch end → both finished at $0.00
- Loss: $10.69 on $32.21 balance (33.2% drawdown → auto-halt)
- **Key Learning:** In strong BULL markets, contrarian DOWN bets are high-risk even with mean reversion signals

**Important Insights:**

1. **Directional Bias in Trending Markets is Expected**
   - After fix: Bot still showing UP-heavy decisions (not 50/50)
   - This is CORRECT behavior in BULL regime - agents should vote UP more often
   - Expecting 40-60% split only makes sense in NEUTRAL markets
   - In strong trends: 60-75% bias toward trend direction is normal and healthy

2. **Contrarian Strategy Risk**
   - Contrarian fade works best in CHOPPY markets (mean reversion completes)
   - In strong trends (BULL/BEAR), contrarian bets fight the momentum
   - The two DOWN bets showed this: mean reversion started but incomplete
   - **Recommendation:** Increase consensus threshold for contrarian trades in strong regime

3. **Binary Market Resolution is Unforgiving**
   - Position can improve from 3.5% → 14% (4x better) but still lose completely
   - "Close" doesn't count - price must finish on correct side of start price
   - This makes timing and epoch boundary analysis critical

4. **Peak Balance Tracking Still Needs Improvement**
   - After deposit: peak set to $32.21
   - Open positions lost → balance dropped to $21.52
   - Bot halted again (33.2% drawdown)
   - **Issue:** Peak doesn't account for open position risk
   - **Workaround:** Reset peak manually after losses or use realized-only tracking

**Monitoring Checklist:**
- [ ] Directional balance: Should match regime (60-75% in BULL, 40-60% in NEUTRAL)
- [ ] Win rate: Target 55-65% (accounting for fees)
- [ ] Contrarian trades: Should have >60% consensus in strong trends
- [ ] Peak balance: Reset manually after large losses to prevent false halts

### Jan 14, 2026 PM: Agent Confidence Threshold Fix

**Issue:** Bot placing trades with 18-19% average confidence
- MIN_VIABLE_THRESHOLD was 0.10 (should be 0.40) - hardcoded override ignored config
- MIN_CONFIDENCE config value (0.40) was never checked in decision logic
- Individual agents voting with 15-25% confidence (no per-agent threshold)
- Low-confidence trades had 0% win rate in testing (7 trades: 3 wins at 54-60% confidence, 4 losses at 18-33%)

**Root Cause:**
```python
# decision_engine.py line 200 (OLD):
MIN_VIABLE_THRESHOLD = 0.10  # Hardcoded - ignored CONSENSUS_THRESHOLD config!

# No MIN_CONFIDENCE check existed
# Agents defaulting to 0.15-0.25 confidence were counted in aggregation
```

**Fix Applied:**
1. **decision_engine.py**: Changed MIN_VIABLE_THRESHOLD to use `CONSENSUS_THRESHOLD` from config (0.40)
2. **decision_engine.py**: Added MIN_CONFIDENCE check (40% average confidence required)
3. **vote_aggregator.py**: Added per-agent confidence filter (30% minimum per agent, needs ≥2 agents)
4. **Agent confidence floors raised**:
   - tech_agent.py: 0.20 → 0.35
   - sentiment_agent.py: 0.15 → 0.35, 0.25 → 0.40
   - candle_agent.py: 0.20 → 0.35
5. **agent_config.py**: Added MIN_INDIVIDUAL_CONFIDENCE = 0.30 documentation

**Expected Impact:**
- Fewer trades (50% reduction expected), but higher quality
- Improved win rate target: 55-65% (up from 42.9%)
- No more 18-19% confidence trades
- Better entry quality (reject weak signals < $0.40 entry probability)
- Reduced catastrophic losing streaks

**Testing Results:** (To be updated after 20-30 trades)
- Average confidence per trade: TBD (target >40%)
- Win rate: TBD (target 55-65%)
- Trade frequency: TBD (expect ~50% fewer trades)
- Entry quality: TBD (expect more 0.60+ probability entries)

**Status:** Implemented Jan 14, 2026 15:35 UTC, awaiting deployment

### Jan 17, 2026: Entry Price Cap Adjustment

**Issue:** High entry prices causing unfavorable risk/reward despite good win rate
- 9 trades on Jan 17: 6 wins, 3 losses (66.7% win rate)
- All 3 losses at entries $0.55-$0.72: -$9.60 each
- Wins averaged only +$4.89 due to high entries
- Net result: Only +$0.58 profit despite 67% win rate

**Analysis (Backtest by Entry Price Threshold):**
```
Threshold | Trades | Win Rate | Total PnL
----------|--------|----------|----------
≤$0.45    |   1    |  100%    | +$5.96
≤$0.50    |   1    |  100%    | +$5.96
≤$0.55    |   2    |   50%    | -$3.63
≤$0.60    |   5    |   60%    | -$0.51
≤$0.65    |   6    |   67%    | +$2.07
All       |   9    |   67%    | +$0.58
```

**Root Cause:** Risk/reward asymmetry at high entries
- At $0.60 entry: Risk $0.60 to win $0.40 (1.5:1 unfavorable)
- At $0.30 entry: Risk $0.30 to win $0.70 (0.43:1 favorable)
- High entries punish losses more than they reward wins

**Fix Applied:** Added MAX_ENTRY_PRICE_CAP = $0.50 in intra_epoch_bot.py
```python
# Line 60: Hard cap on entry price
MAX_ENTRY_PRICE_CAP = 0.50

# Line 2263: Applied in trading logic
max_entry = accuracy - EDGE_BUFFER
max_entry = min(max_entry, MAX_ENTRY_PRICE_CAP)  # Apply hard cap
```

**Expected Impact:**
- Fewer trades (may drop to 1-3/day from 5-10/day)
- Better risk/reward on each trade
- Higher net PnL despite fewer trades
- All 3 losses from Jan 17 would have been avoided

**Monitoring Checklist:**
- [ ] Trades per day (expect 1-3)
- [ ] Entry prices (should all be ≤$0.50)
- [ ] Win rate (should remain 60%+)
- [ ] Net PnL per day (target +$5-10/day)

**Status:** Implemented Jan 17, 2026 18:30 UTC

---

**Remember:** This bot trades with real money. Always test changes locally, monitor performance, and never deploy untested code to the VPS.
