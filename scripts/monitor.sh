#!/bin/bash
#
# ML Bot Monitoring Script
#
# Checks for critical issues and alerts if found:
# 1. Position conflicts (same crypto with both Up/Down)
# 2. Balance drops >10% in 15 minutes
# 3. Order placement failures (>3 consecutive)
# 4. ML decision exceptions
#
# Usage:
#   ./scripts/monitor.sh
#
# Cron (every 5 minutes):
#   */5 * * * * /opt/polymarket-autotrader/scripts/monitor.sh >> /opt/polymarket-autotrader/monitor.log 2>&1
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BOT_LOG="$PROJECT_ROOT/bot.log"
STATE_FILE="$PROJECT_ROOT/state/trading_state.json"
ALERT_FILE="$PROJECT_ROOT/monitor_alerts.txt"
BALANCE_HISTORY="$PROJECT_ROOT/state/balance_history.txt"

# Alert thresholds
BALANCE_DROP_THRESHOLD=0.10  # 10%
MAX_CONSECUTIVE_FAILURES=3
CHECK_WINDOW_MINUTES=15

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR:${NC} $1"
}

# Alert function (prints to file for now - can extend to email/slack)
send_alert() {
    local severity=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] $severity: $message" >> "$ALERT_FILE"

    if [ "$severity" == "CRITICAL" ]; then
        log_error "$message"
    else
        log_warning "$message"
    fi
}

# Check 1: Position conflicts
check_position_conflicts() {
    log_info "Checking for position conflicts..."

    # Look for CONFLICT messages in recent logs
    local conflicts=$(grep -i "CONFLICT" "$BOT_LOG" 2>/dev/null | tail -20 | wc -l)

    if [ "$conflicts" -gt 0 ]; then
        send_alert "WARNING" "Found $conflicts position conflict warnings in logs"
        return 1
    fi

    log_info "✅ No position conflicts detected"
    return 0
}

# Check 2: Balance drop
check_balance_drop() {
    log_info "Checking for balance drops..."

    # Get current balance from state
    if [ ! -f "$STATE_FILE" ]; then
        log_warning "State file not found: $STATE_FILE"
        return 0
    fi

    local current_balance=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
    print(state.get('current_balance', 0))
")

    # Record balance with timestamp
    local timestamp=$(date +%s)
    echo "$timestamp $current_balance" >> "$BALANCE_HISTORY"

    # Keep only last 24 hours of history
    local cutoff=$((timestamp - 86400))
    grep -E "^[0-9]+ " "$BALANCE_HISTORY" 2>/dev/null | \
        awk -v cutoff="$cutoff" '$1 >= cutoff' > "$BALANCE_HISTORY.tmp" || true
    mv "$BALANCE_HISTORY.tmp" "$BALANCE_HISTORY" 2>/dev/null || true

    # Check balance from 15 minutes ago
    local window_cutoff=$((timestamp - CHECK_WINDOW_MINUTES * 60))
    local old_balance=$(awk -v cutoff="$window_cutoff" '$1 <= cutoff {last=$2} END {print last}' "$BALANCE_HISTORY")

    if [ -z "$old_balance" ] || [ "$old_balance" == "0" ]; then
        log_info "No historical balance data (bot may have just started)"
        return 0
    fi

    # Calculate percentage drop
    local drop=$(python3 -c "
old = float($old_balance)
current = float($current_balance)
if old > 0:
    drop = (old - current) / old
    print(f'{drop:.4f}')
else:
    print('0')
")

    local drop_pct=$(python3 -c "print(f'{float($drop) * 100:.1f}')")

    if (( $(echo "$drop > $BALANCE_DROP_THRESHOLD" | bc -l) )); then
        send_alert "CRITICAL" "Balance dropped ${drop_pct}% in last $CHECK_WINDOW_MINUTES minutes ($$old_balance -> $$current_balance)"
        return 1
    fi

    log_info "✅ Balance stable: $$current_balance (${drop_pct}% change)"
    return 0
}

# Check 3: Order placement failures
check_order_failures() {
    log_info "Checking for order placement failures..."

    # Look for ORDER FAILED messages in recent logs
    local failures=$(grep -i "ORDER.*FAIL\|FAILED.*ORDER" "$BOT_LOG" 2>/dev/null | tail -20 | wc -l)

    if [ "$failures" -gt "$MAX_CONSECUTIVE_FAILURES" ]; then
        send_alert "CRITICAL" "Found $failures order placement failures in recent logs (threshold: $MAX_CONSECUTIVE_FAILURES)"
        return 1
    fi

    log_info "✅ No excessive order failures ($failures detected, threshold: $MAX_CONSECUTIVE_FAILURES)"
    return 0
}

# Check 4: ML decision failures
check_ml_exceptions() {
    log_info "Checking for ML decision exceptions..."

    # Look for ML Bot errors in recent logs
    local ml_errors=$(grep -i "\[ML Bot\].*ERROR\|ML Bot.*Exception\|Failed to get ML decision" "$BOT_LOG" 2>/dev/null | tail -20 | wc -l)

    if [ "$ml_errors" -gt 5 ]; then
        send_alert "WARNING" "Found $ml_errors ML decision errors in recent logs"
        return 1
    fi

    log_info "✅ No excessive ML errors ($ml_errors detected)"
    return 0
}

# Check 5: Bot is running
check_bot_running() {
    log_info "Checking if bot is running..."

    # Check if bot process exists (adjust process name if needed)
    if pgrep -f "momentum_bot_v12.py" > /dev/null; then
        log_info "✅ Bot is running"
        return 0
    else
        send_alert "CRITICAL" "Bot process not found - may have crashed"
        return 1
    fi
}

# Main monitoring loop
main() {
    log_info "=" * 80
    log_info "Starting ML Bot Health Check"
    log_info "=" * 80

    # Initialize alert file if needed
    touch "$ALERT_FILE"

    # Initialize balance history if needed
    touch "$BALANCE_HISTORY"

    # Run all checks
    local all_pass=true

    check_bot_running || all_pass=false
    check_position_conflicts || all_pass=false
    check_balance_drop || all_pass=false
    check_order_failures || all_pass=false
    check_ml_exceptions || all_pass=false

    # Summary
    log_info "=" * 80
    if [ "$all_pass" = true ]; then
        log_info "✅ All checks passed - bot is healthy"
    else
        log_error "⚠️  Some checks failed - see alerts above"
        log_info "Recent alerts:"
        tail -5 "$ALERT_FILE" 2>/dev/null || echo "No recent alerts"
    fi
    log_info "=" * 80

    exit 0
}

# Run main
main
