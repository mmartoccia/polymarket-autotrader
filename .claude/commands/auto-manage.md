# `/auto-manage` - Autonomous Event-Driven Management

**The Sentinel System - Monitor, Notify, Auto-Fix**

## Purpose

Interact with the Sentinel monitoring system which watches the trading bot for halt events, performance degradation, and configurable alerts. Sentinel runs locally on Mac, polling the VPS every 30 seconds.

## Argument Parsing

**IMPORTANT:** Parse the user's argument to determine which subcommand to execute:

1. If argument is empty or not provided → Execute **Default: Run Manual Diagnostic**
2. If argument is `status` → Execute **Subcommand: status**
3. If argument is `start` → Execute **Subcommand: start**
4. If argument is `stop` → Execute **Subcommand: stop**
5. If argument is `history` → Execute **Subcommand: history**
6. If argument is `config` → Execute **Subcommand: config**
7. If argument is anything else → Show "Unknown subcommand. Valid options: status, start, stop, history, config"

## Quick Reference

| Subcommand | Action |
|------------|--------|
| (no args)  | Run manual diagnostic (default) |
| `status`   | Show monitor status, pending events, rate limits |
| `start`    | Start the background monitor daemon |
| `stop`     | Stop the monitor daemon |
| `history`  | Show last 20 actions from audit log |
| `config`   | Display current configuration |

## Usage

### Default: Run Manual Diagnostic

When invoked without arguments, `/auto-manage` gathers current state from the VPS and provides a Claude analysis without taking any action.

**Execute these steps:**

1. **Gather VPS State:**
```bash
# Read primary state file (intra_epoch_state.json)
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cat /opt/polymarket-autotrader/state/intra_epoch_state.json 2>/dev/null || cat /opt/polymarket-autotrader/state/trading_state.json"
```

2. **Get Recent Logs:**
```bash
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "tail -50 /opt/polymarket-autotrader/bot.log"
```

3. **Check On-Chain Balance:**
```bash
# Query USDC balance from Polygon RPC
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "python3 -c \"
import requests, os
from dotenv import load_dotenv
load_dotenv('/opt/polymarket-autotrader/.env')
wallet = os.getenv('POLYMARKET_WALLET')
rpc = 'https://polygon-rpc.com'
usdc = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
resp = requests.post(rpc, json={'jsonrpc': '2.0', 'method': 'eth_call', 'params': [{'to': usdc, 'data': f'0x70a08231000000000000000000000000{wallet[2:]}'}, 'latest'], 'id': 1}, timeout=10)
print(f'{int(resp.json()[\"result\"], 16) / 1e6:.2f}')
\""
```

4. **Analyze** the gathered data and report:
   - Current bot mode (normal/halted/conservative/etc)
   - Balance status (current, peak, drawdown %)
   - Recent trading activity (wins/losses)
   - Any concerning patterns in logs
   - Recommended action if issues detected

5. **Do NOT take any action** - just report findings.

---

### Subcommand: `status`

Show current Sentinel status.

**Execute:**
```bash
cd /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel

# Check if monitor is running
if [ -f state/monitor.pid ]; then
    pid=$(cat state/monitor.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "Monitor: RUNNING (PID $pid)"
    else
        echo "Monitor: STOPPED (stale PID file)"
    fi
else
    echo "Monitor: STOPPED"
fi

# Show last state if available
echo ""
echo "=== Last Known State ==="
if [ -f state/last_state.json ]; then
    cat state/last_state.json | python3 -m json.tool
else
    echo "No state file found"
fi

# Show pending events
echo ""
echo "=== Pending Events ==="
cat events/queue.json | python3 -c "import json,sys; events=[e for e in json.load(sys.stdin) if e.get('status')=='pending']; print(f'{len(events)} pending event(s)'); [print(f'  - {e[\"type\"]}: {e[\"reason\"]}') for e in events[:5]]"

# Show rate limit usage
echo ""
echo "=== Rate Limit Usage ==="
if [ -f state/rate_limit.json ]; then
    cat state/rate_limit.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Fixes this hour: {d.get(\"count\", 0)}/3')"
else
    echo "Fixes this hour: 0/3"
fi
```

---

### Subcommand: `start`

Start the background monitor daemon.

**Execute:**
```bash
cd /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel
./sentinel_monitor.sh start
```

**Verify:**
```bash
./sentinel_monitor.sh status
```

---

### Subcommand: `stop`

Stop the monitor daemon.

**Execute:**
```bash
cd /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel
./sentinel_monitor.sh stop
```

**Verify:**
```bash
./sentinel_monitor.sh status
```

---

### Subcommand: `history`

Show recent actions from audit log.

**Execute:**
```bash
cd /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel
echo "=== Last 20 Sentinel Actions ==="
tail -20 history/actions.log
```

---

### Subcommand: `config`

Display current Sentinel configuration.

**Execute:**
```bash
cd /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel
echo "=== Sentinel Configuration ==="
cat sentinel_config.json | python3 -m json.tool
```

---

## Safety Information

### Kill Switch

To immediately stop Sentinel from taking any automated actions:

```bash
touch /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel/state/KILL_SWITCH
```

Remove to re-enable:
```bash
rm /Volumes/TerraTitan/Development/polymarket-autotrader/sentinel/state/KILL_SWITCH
```

### Rate Limits

Sentinel has built-in safety limits:

| Limit | Value | Purpose |
|-------|-------|---------|
| Max auto-fixes per hour | 3 | Prevent runaway fixes |
| Consecutive fix limit | 2 | Detect fix loops, escalate |
| Balance floor | $50 | Always escalate if balance below |
| Min confidence for auto-fix | 70% | Require high confidence |
| Telegram timeout | 15 min | Wait for user before auto-fix |

### Fix Loop Detection

If Sentinel detects the same issue occurring twice within 30 minutes after attempting fixes, it will:
1. Stop attempting auto-fixes
2. Escalate to the user via Telegram
3. Require manual intervention

### What Sentinel Can Do

**Allowed Actions:**
- `reset_peak_balance` - Fix false drawdown halts
- `resume_trading` - Resume from halt (set mode=normal)
- `reset_loss_streak` - Clear consecutive losses counter
- `restart_bot` - Restart the systemd service

**Cannot Do:**
- Change bot code or strategy
- Withdraw funds
- Disable safety limits
- Trade directly

---

## How Sentinel Works

```
┌──────────────────────────────────────────────────────────────┐
│                    SENTINEL ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  sentinel_monitor.sh (background daemon)                       │
│    • Polls VPS every 30 seconds                               │
│    • Detects halt transitions and alert conditions            │
│    • Writes events to events/queue.json                       │
│                                                                │
│                          ↓                                     │
│                                                                │
│  sentinel.sh (orchestrator)                                    │
│    • Processes events from queue                              │
│    • Gathers diagnostics (state, logs, balance)               │
│    • Invokes Claude for analysis                              │
│    • Sends Telegram notification to user                      │
│    • Waits 15 min for user response                           │
│    • Auto-fixes if timeout + high confidence                  │
│                                                                │
│                          ↓                                     │
│                                                                │
│  User via Telegram                                             │
│    • /approve - Execute recommended action                    │
│    • /deny [reason] - Reject, leave bot halted                │
│    • /custom <action> - Request specific action               │
│    • /halt - Emergency stop                                   │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## File Locations

| File | Purpose |
|------|---------|
| `sentinel/sentinel_monitor.sh` | Background polling daemon |
| `sentinel/sentinel.sh` | Main orchestrator script |
| `sentinel/sentinel_diagnose.md` | Claude prompt template |
| `sentinel/sentinel_config.json` | Configuration settings |
| `sentinel/events/queue.json` | Pending/processed events |
| `sentinel/history/actions.log` | Audit trail of all actions |
| `sentinel/state/monitor.pid` | Running monitor PID |
| `sentinel/state/last_state.json` | Last VPS state snapshot |
| `sentinel/state/KILL_SWITCH` | Emergency stop file |

---

## Troubleshooting

### Monitor Not Starting

```bash
# Check for existing process
ps aux | grep sentinel_monitor

# Check logs
tail -50 sentinel/state/monitor.log

# Remove stale PID file if needed
rm sentinel/state/monitor.pid
```

### Telegram Not Working

```bash
# Test Telegram from VPS
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "python3 -c \"
from bot.telegram_handler import TelegramBot
bot = TelegramBot()
bot.send_message_sync('Test from Sentinel')
\""
```

### Events Not Processing

```bash
# Check queue
cat sentinel/events/queue.json

# Run orchestrator manually
cd sentinel && ./sentinel.sh --dry-run
```

---

## Examples

### Example 1: Check Status

```
/auto-manage status
```

Output:
```
Monitor: RUNNING (PID 12345)

=== Last Known State ===
{
    "mode": "normal",
    "current_balance": 185.50,
    "peak_balance": 200.00,
    "consecutive_losses": 0
}

=== Pending Events ===
0 pending event(s)

=== Rate Limit Usage ===
Fixes this hour: 0/3
```

### Example 2: Run Diagnostic

```
/auto-manage
```

Output:
```
=== Sentinel Diagnostic Report ===

Bot Status: NORMAL
Balance: $185.50 (peak: $200.00, drawdown: 7.3%)
Mode: normal
Recent Activity: 3 wins, 1 loss in last hour

Analysis:
- Bot is operating normally
- Drawdown is within acceptable limits (7.3% < 30%)
- No concerning patterns in logs
- Win rate looks healthy

Recommendation: No action needed. Bot is healthy.
```

### Example 3: Start Monitor

```
/auto-manage start
```

Output:
```
Starting Sentinel monitor daemon...
Monitor started successfully (PID 12346)
Polling VPS every 30 seconds.
```
