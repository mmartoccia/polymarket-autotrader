# ML Bot Monitoring System

Automated health checks and alerting for the Polymarket AutoTrader ML bot.

## Overview

The monitoring script (`monitor.sh`) runs periodic health checks on the bot and alerts when issues are detected.

## What It Checks

### 1. Bot Process Status
- Verifies `momentum_bot_v12.py` process is running
- **Alert:** CRITICAL if process not found

### 2. Position Conflicts
- Scans logs for "CONFLICT" messages
- Detects when bot tries to place both Up/Down on same crypto
- **Alert:** WARNING if conflicts found

### 3. Balance Drops
- Tracks balance over time in `state/balance_history.txt`
- Calculates percentage change over last 15 minutes
- **Alert:** CRITICAL if drop >10%

### 4. Order Placement Failures
- Counts "ORDER FAILED" messages in logs
- **Alert:** CRITICAL if >3 failures detected

### 5. ML Decision Exceptions
- Counts ML Bot errors and exceptions
- **Alert:** WARNING if >5 exceptions detected

## Installation

### Manual Run

```bash
cd /opt/polymarket-autotrader
./scripts/monitor.sh
```

### Automated (Cron)

Add to crontab (runs every 5 minutes):

```bash
# Edit crontab
crontab -e

# Add this line:
*/5 * * * * /opt/polymarket-autotrader/scripts/monitor.sh >> /opt/polymarket-autotrader/monitor.log 2>&1
```

### Verify Cron Job

```bash
# List cron jobs
crontab -l

# Check monitor log
tail -f /opt/polymarket-autotrader/monitor.log
```

## Output Files

### `monitor.log`
- Full monitoring output
- Timestamped health check results
- Location: `/opt/polymarket-autotrader/monitor.log`

### `monitor_alerts.txt`
- Critical and warning alerts only
- Format: `[timestamp] SEVERITY: message`
- Location: `/opt/polymarket-autotrader/monitor_alerts.txt`

### `state/balance_history.txt`
- Historical balance tracking
- Format: `timestamp balance`
- Keeps last 24 hours of data

## Alert Severity Levels

### CRITICAL
- Bot process not running
- Balance dropped >10% in 15 minutes
- >3 consecutive order failures

### WARNING
- Position conflicts detected
- >5 ML decision exceptions

## Thresholds (Configurable)

Edit `scripts/monitor.sh` to adjust:

```bash
BALANCE_DROP_THRESHOLD=0.10      # 10% balance drop
MAX_CONSECUTIVE_FAILURES=3       # Order failures
CHECK_WINDOW_MINUTES=15          # Balance check window
```

## Example Output

### Healthy System

```
[2026-01-15 12:00:00] Starting ML Bot Health Check
[2026-01-15 12:00:00] Checking if bot is running...
[2026-01-15 12:00:00] ✅ Bot is running
[2026-01-15 12:00:00] Checking for position conflicts...
[2026-01-15 12:00:00] ✅ No position conflicts detected
[2026-01-15 12:00:00] Checking for balance drops...
[2026-01-15 12:00:00] ✅ Balance stable: $176.78 (-2.1% change)
[2026-01-15 12:00:00] Checking for order placement failures...
[2026-01-15 12:00:00] ✅ No excessive order failures (0 detected, threshold: 3)
[2026-01-15 12:00:00] Checking for ML decision exceptions...
[2026-01-15 12:00:00] ✅ No excessive ML errors (0 detected)
[2026-01-15 12:00:00] ✅ All checks passed - bot is healthy
```

### System with Issues

```
[2026-01-15 12:05:00] Starting ML Bot Health Check
[2026-01-15 12:05:00] ❌ ERROR: Bot process not found - may have crashed
[2026-01-15 12:05:00] ⚠️  WARNING: Found 5 position conflict warnings in logs
[2026-01-15 12:05:00] ❌ ERROR: Balance dropped 15.2% in last 15 minutes ($200.00 -> $169.60)
[2026-01-15 12:05:00] ⚠️  Some checks failed - see alerts above
Recent alerts:
[2026-01-15 12:05:00] CRITICAL: Bot process not found - may have crashed
[2026-01-15 12:05:00] WARNING: Found 5 position conflict warnings in logs
[2026-01-15 12:05:00] CRITICAL: Balance dropped 15.2% in last 15 minutes
```

## Extending Alerts

### Email Notifications

Replace `send_alert()` function in `monitor.sh`:

```bash
send_alert() {
    local severity=$1
    local message=$2

    # Log to file
    echo "[$timestamp] $severity: $message" >> "$ALERT_FILE"

    # Send email (requires mail command)
    if [ "$severity" == "CRITICAL" ]; then
        echo "$message" | mail -s "ML Bot CRITICAL Alert" your@email.com
    fi
}
```

### Slack Notifications

```bash
send_alert() {
    local severity=$1
    local message=$2

    # Log to file
    echo "[$timestamp] $severity: $message" >> "$ALERT_FILE"

    # Send to Slack webhook
    if [ "$severity" == "CRITICAL" ]; then
        curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
            -H 'Content-Type: application/json' \
            -d "{\"text\": \"🚨 ML Bot Alert: $message\"}"
    fi
}
```

## Troubleshooting

### Script Not Running

```bash
# Check if cron is running
systemctl status cron

# Check script permissions
ls -l /opt/polymarket-autotrader/scripts/monitor.sh

# Make executable
chmod +x /opt/polymarket-autotrader/scripts/monitor.sh
```

### No Alerts Generated

```bash
# Check alert file exists
cat /opt/polymarket-autotrader/monitor_alerts.txt

# Verify log file location
ls -l /opt/polymarket-autotrader/bot.log

# Run script manually to see errors
./scripts/monitor.sh
```

### Balance History Not Updating

```bash
# Check state file exists
cat /opt/polymarket-autotrader/state/trading_state.json

# Verify balance_history.txt is being written
cat /opt/polymarket-autotrader/state/balance_history.txt

# Should show: timestamp balance (one per run)
```

## Integration with Dashboard

The monitoring script is complementary to the live dashboard:

- **Dashboard**: Real-time visual monitoring (manual)
- **Monitor Script**: Automated alerting (runs in background)

Use both for comprehensive monitoring:

```bash
# Terminal 1: Live dashboard
python3 dashboard/live_dashboard.py

# Terminal 2: Monitor alerts
tail -f monitor_alerts.txt
```

## Maintenance

### Clear Old Alerts

```bash
# Keep only last 100 alerts
tail -100 monitor_alerts.txt > monitor_alerts.txt.tmp
mv monitor_alerts.txt.tmp monitor_alerts.txt
```

### Clear Balance History

```bash
# Balance history auto-cleans (keeps 24 hours)
# Manual cleanup:
rm state/balance_history.txt
```

### Disable Monitoring

```bash
# Remove from crontab
crontab -e
# Delete the line: */5 * * * * /opt/polymarket-autotrader/scripts/monitor.sh
```

---

**Last Updated:** January 15, 2026
**Version:** 1.0
