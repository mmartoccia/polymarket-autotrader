#!/bin/bash
#
# Sentinel Monitor Daemon
# Polls VPS state every 30 seconds and detects halt events
#
# Usage:
#   ./sentinel_monitor.sh start   - Start polling daemon in background
#   ./sentinel_monitor.sh stop    - Stop the polling daemon
#   ./sentinel_monitor.sh status  - Show current status
#   ./sentinel_monitor.sh health  - Check health and attempt self-recovery if unhealthy
#

set -o pipefail

# Error handling: log errors and continue (don't exit on error in daemon)
# We intentionally don't use set -e here because the polling loop should continue
# even when individual operations fail

# Get script directory for relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/sentinel_config.json"
STATE_DIR="$SCRIPT_DIR/state"
EVENTS_DIR="$SCRIPT_DIR/events"
PID_FILE="$STATE_DIR/monitor.pid"
LOG_FILE="$STATE_DIR/monitor.log"
LAST_STATE_FILE="$STATE_DIR/last_state.json"
KILL_SWITCH_FILE="$STATE_DIR/KILL_SWITCH"
QUEUE_FILE="$EVENTS_DIR/queue.json"
ALERT_COOLDOWNS_FILE="$STATE_DIR/alert_cooldowns.json"
ERROR_LOG_FILE="$STATE_DIR/error.log"
HEARTBEAT_FILE="$STATE_DIR/heartbeat"

# Track consecutive SSH failures
SSH_FAILURE_COUNT=0
MAX_SSH_FAILURES=5

# Ensure state directory exists
mkdir -p "$STATE_DIR"

# Load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "ERROR: Config file not found: $CONFIG_FILE" >&2
        exit 1
    fi

    POLL_INTERVAL=$(jq -r '.polling.interval_seconds // 30' "$CONFIG_FILE")
    SSH_TIMEOUT=$(jq -r '.polling.ssh_timeout_seconds // 10' "$CONFIG_FILE")
    VPS_HOST=$(jq -r '.vps.host' "$CONFIG_FILE")
    SSH_KEY=$(jq -r '.vps.ssh_key' "$CONFIG_FILE")
    # Expand ~ in SSH_KEY path
    SSH_KEY="${SSH_KEY/#\~/$HOME}"
    STATE_FILES=$(jq -r '.vps.state_files[]' "$CONFIG_FILE")
}

# Log message with timestamp
log() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" >> "$LOG_FILE"
}

# Log error with stack trace to error.log
log_error() {
    local msg="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    {
        echo "=========================================="
        echo "[$timestamp] ERROR: $msg"
        echo "Stack trace:"
        local frame=0
        while caller $frame; do
            ((frame++))
        done
        echo "=========================================="
    } >> "$ERROR_LOG_FILE"

    # Also log to regular log
    log "ERROR" "$msg"
}

# Send critical error notification via Telegram (best effort)
# This is a simplified version that doesn't retry to avoid loops
send_critical_error_notification() {
    local error_msg="$1"

    # Escape for Python string
    local escaped_msg
    escaped_msg=$(echo "$error_msg" | sed 's/\\/\\\\/g; s/"/\\"/g')

    local message="🔴 <b>SENTINEL CRITICAL ERROR</b>

<code>$escaped_msg</code>

Time: $(date -u '+%Y-%m-%d %H:%M UTC')

⚠️ Sentinel monitor may require attention"

    # Try to send via VPS telegram_handler (best effort, no retry)
    local python_script="
import sys
sys.path.insert(0, '/opt/polymarket-autotrader')
from bot.telegram_handler import TelegramBot

bot = TelegramBot()
if bot.enabled:
    bot.send_message_sync('''$message''', parse_mode='HTML', silent=False)
"

    ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes \
        "$VPS_HOST" "cd /opt/polymarket-autotrader && python3 -c \"$python_script\"" 2>/dev/null || true
}

# Get VPS state via SSH with retry logic
# Returns: 0 on success, 1 on failure
# Sets global SSH_FAILURE_COUNT for tracking consecutive failures
get_vps_state() {
    local state_file
    local state_json
    local max_retries=3
    local retry_delay=2

    # Try each state file in order (primary first, then fallback)
    for state_file in $STATE_FILES; do
        local retry=0
        while [[ $retry -lt $max_retries ]]; do
            state_json=$(ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
                -o ServerAliveInterval=5 -o ServerAliveCountMax=2 \
                "$VPS_HOST" "cat '$state_file' 2>/dev/null" 2>/dev/null)

            local ssh_exit_code=$?

            if [[ $ssh_exit_code -eq 0 ]] && [[ -n "$state_json" ]]; then
                # Validate it's valid JSON
                if echo "$state_json" | jq . >/dev/null 2>&1; then
                    # Reset failure counter on success
                    SSH_FAILURE_COUNT=0
                    echo "$state_json"
                    return 0
                else
                    # Malformed JSON in state file
                    log_error "Malformed JSON in state file: $state_file"
                    log "WARN" "State file $state_file contains invalid JSON, trying next file"
                    break  # Try next state file
                fi
            fi

            # SSH failed, retry
            ((retry++))
            if [[ $retry -lt $max_retries ]]; then
                log "WARN" "SSH attempt $retry/$max_retries failed for $state_file, retrying in ${retry_delay}s..."
                sleep $retry_delay
            fi
        done
    done

    # All attempts failed
    ((SSH_FAILURE_COUNT++))
    log_error "SSH connection failed after $max_retries retries (consecutive failures: $SSH_FAILURE_COUNT)"

    # Check for critical threshold
    if [[ $SSH_FAILURE_COUNT -ge $MAX_SSH_FAILURES ]]; then
        log_error "Critical: $SSH_FAILURE_COUNT consecutive SSH failures (threshold: $MAX_SSH_FAILURES)"
        send_critical_error_notification "SSH connection to VPS failed $SSH_FAILURE_COUNT times consecutively"
        # Don't reset the counter - let it continue to accumulate
    fi

    return 1
}

# Check if mode transitioned to halted
check_halt_transition() {
    local current_state="$1"
    local current_mode
    local last_mode

    current_mode=$(echo "$current_state" | jq -r '.mode // "unknown"')

    # Get last known mode
    if [[ -f "$LAST_STATE_FILE" ]]; then
        last_mode=$(jq -r '.mode // "unknown"' "$LAST_STATE_FILE")
    else
        last_mode="unknown"
    fi

    # Save current state for next comparison
    echo "$current_state" > "$LAST_STATE_FILE"

    # Check for halt transition (mode changed TO halted)
    if [[ "$current_mode" == "halted" ]] && [[ "$last_mode" != "halted" ]]; then
        return 0  # Halt transition detected
    fi

    return 1  # No halt transition
}

# Add halt event to queue
add_halt_event() {
    local state="$1"
    local timestamp
    local halt_reason
    local balance
    local drawdown
    local event_id

    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    halt_reason=$(echo "$state" | jq -r '.halt_reason // "unknown"')
    balance=$(echo "$state" | jq -r '.current_balance // 0')
    drawdown=$(echo "$state" | jq -r '.drawdown_pct // 0')
    event_id="halt_$(date +%s)"

    # Read existing queue
    local queue
    if [[ -f "$QUEUE_FILE" ]]; then
        queue=$(cat "$QUEUE_FILE")
    else
        queue="[]"
    fi

    # Add new event
    local event
    event=$(jq -n \
        --arg id "$event_id" \
        --arg ts "$timestamp" \
        --arg reason "$halt_reason" \
        --arg bal "$balance" \
        --arg dd "$drawdown" \
        --arg status "pending" \
        '{
            id: $id,
            type: "halt",
            timestamp: $ts,
            halt_reason: $reason,
            balance: ($bal | tonumber),
            drawdown_pct: ($dd | tonumber),
            status: $status
        }')

    # Append to queue
    echo "$queue" | jq --argjson event "$event" '. + [$event]' > "$QUEUE_FILE"

    log "INFO" "Halt event added to queue: $event_id (reason: $halt_reason, balance: $balance)"
}

# Initialize alert cooldowns file if needed
init_alert_cooldowns() {
    if [[ ! -f "$ALERT_COOLDOWNS_FILE" ]]; then
        echo "{}" > "$ALERT_COOLDOWNS_FILE"
    fi
}

# Check if an alert is in cooldown
# Returns: 0 if in cooldown (should skip), 1 if not in cooldown (can trigger)
check_alert_cooldown() {
    local alert_name="$1"
    local cooldown_minutes="$2"

    init_alert_cooldowns

    local last_trigger
    last_trigger=$(jq -r --arg name "$alert_name" '.[$name] // 0' "$ALERT_COOLDOWNS_FILE")

    local current_time
    current_time=$(date +%s)
    local cooldown_seconds=$((cooldown_minutes * 60))
    local cutoff=$((current_time - cooldown_seconds))

    if [[ $last_trigger -gt $cutoff ]]; then
        return 0  # In cooldown, skip
    fi

    return 1  # Not in cooldown, can trigger
}

# Update alert cooldown timestamp
update_alert_cooldown() {
    local alert_name="$1"

    init_alert_cooldowns

    local current_time
    current_time=$(date +%s)

    local cooldowns
    cooldowns=$(cat "$ALERT_COOLDOWNS_FILE")
    cooldowns=$(echo "$cooldowns" | jq --arg name "$alert_name" --argjson ts "$current_time" '.[$name] = $ts')
    echo "$cooldowns" > "$ALERT_COOLDOWNS_FILE"
}

# Evaluate a single alert condition against state values
# Args: condition string, state JSON
# Returns: 0 if condition is true (alert should trigger), 1 if false
evaluate_condition() {
    local condition="$1"
    local state="$2"

    # Extract values from state
    local balance
    local drawdown_pct
    local consecutive_losses

    balance=$(echo "$state" | jq -r '.current_balance // .balance // 0')
    drawdown_pct=$(echo "$state" | jq -r '.drawdown_pct // 0')
    consecutive_losses=$(echo "$state" | jq -r '.consecutive_losses // 0')

    # Create a bc-compatible expression by substituting variable names
    local expr="$condition"
    expr=$(echo "$expr" | sed "s/balance/$balance/g")
    expr=$(echo "$expr" | sed "s/drawdown_pct/$drawdown_pct/g")
    expr=$(echo "$expr" | sed "s/consecutive_losses/$consecutive_losses/g")

    # Evaluate with bc (returns 1 for true, 0 for false)
    local result
    result=$(echo "$expr" | bc -l 2>/dev/null)

    if [[ "$result" == "1" ]]; then
        return 0  # Condition true
    fi
    return 1  # Condition false
}

# Get emoji for alert severity
get_severity_emoji() {
    local severity="$1"
    case "$severity" in
        info)     echo "ℹ️" ;;
        warning)  echo "⚠️" ;;
        critical) echo "🚨" ;;
        *)        echo "📢" ;;
    esac
}

# Send alert via Telegram with retry logic (using VPS telegram_handler.py)
# Retries up to 3 times with exponential backoff
send_alert_notification() {
    local alert_name="$1"
    local severity="$2"
    local condition="$3"
    local state="$4"

    local max_retries=3
    local retry_delay=2

    local emoji
    emoji=$(get_severity_emoji "$severity")

    local balance
    local drawdown_pct
    local consecutive_losses

    balance=$(echo "$state" | jq -r '.current_balance // .balance // 0')
    drawdown_pct=$(echo "$state" | jq -r '.drawdown_pct // 0')
    consecutive_losses=$(echo "$state" | jq -r '.consecutive_losses // 0')

    local timestamp
    timestamp=$(date -u +"%Y-%m-%d %H:%M UTC")

    # Build message
    local message="$emoji <b>SENTINEL ALERT: ${alert_name}</b>

<b>Severity:</b> $(echo "$severity" | tr '[:lower:]' '[:upper:]')
<b>Condition:</b> <code>$condition</code>
<b>Time:</b> $timestamp

<b>Current State:</b>
• Balance: \$$balance
• Drawdown: ${drawdown_pct}%
• Consecutive Losses: $consecutive_losses"

    # Escape for Python string
    local escaped_message
    escaped_message=$(echo "$message" | sed 's/\\/\\\\/g; s/"/\\"/g')

    # Send via SSH to VPS telegram_handler with retry
    local python_script="
import sys
sys.path.insert(0, '/opt/polymarket-autotrader')
from bot.telegram_handler import TelegramBot

bot = TelegramBot()
if not bot.enabled:
    sys.exit(1)

result = bot.send_message_sync('''$escaped_message''', parse_mode='HTML', silent=False)
sys.exit(0 if result else 1)
"

    local retry=0
    while [[ $retry -lt $max_retries ]]; do
        ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
            "$VPS_HOST" "cd /opt/polymarket-autotrader && python3 -c \"$python_script\"" 2>/dev/null

        if [[ $? -eq 0 ]]; then
            return 0
        fi

        ((retry++))
        if [[ $retry -lt $max_retries ]]; then
            log "WARN" "Telegram send attempt $retry/$max_retries failed, retrying in ${retry_delay}s..."
            sleep $retry_delay
            retry_delay=$((retry_delay * 2))  # Exponential backoff
        fi
    done

    # All retries failed
    log_error "Failed to send Telegram alert '$alert_name' after $max_retries retries"
    return 1
}

# Evaluate all alert rules against current state
evaluate_alerts() {
    local state="$1"

    # Get alerts array from config
    local alerts
    alerts=$(jq -c '.alerts // []' "$CONFIG_FILE")

    # Iterate through each alert rule
    echo "$alerts" | jq -c '.[]' 2>/dev/null | while read -r alert; do
        local name
        local condition
        local severity
        local cooldown_minutes

        name=$(echo "$alert" | jq -r '.name')
        condition=$(echo "$alert" | jq -r '.condition')
        severity=$(echo "$alert" | jq -r '.severity // "info"')
        cooldown_minutes=$(echo "$alert" | jq -r '.cooldown_minutes // 60')

        # Check if condition is met
        if evaluate_condition "$condition" "$state"; then
            # Check cooldown
            if check_alert_cooldown "$name" "$cooldown_minutes"; then
                log "DEBUG" "Alert '$name' in cooldown, skipping"
                continue
            fi

            log "WARN" "Alert triggered: $name (condition: $condition)"

            # Send notification
            if send_alert_notification "$name" "$severity" "$condition" "$state"; then
                log "INFO" "Alert notification sent for: $name"
                update_alert_cooldown "$name"
            else
                log "ERROR" "Failed to send alert notification for: $name"
            fi
        fi
    done
}

# Write heartbeat timestamp
write_heartbeat() {
    date +%s > "$HEARTBEAT_FILE"
}

# Main polling loop
poll_loop() {
    log "INFO" "Monitor started with PID $$"

    while true; do
        # Write heartbeat at start of each poll
        write_heartbeat

        # Check kill switch
        if [[ -f "$KILL_SWITCH_FILE" ]]; then
            log "WARN" "Kill switch active, skipping poll cycle"
            sleep "$POLL_INTERVAL"
            continue
        fi

        # Get VPS state (includes retry logic and error handling)
        local state
        state=$(get_vps_state)
        local get_state_result=$?

        if [[ $get_state_result -ne 0 ]] || [[ -z "$state" ]]; then
            # Error already logged by get_vps_state
            log "DEBUG" "Skipping poll cycle due to state retrieval failure"
            sleep "$POLL_INTERVAL"
            continue
        fi

        # Check for halt transition
        if check_halt_transition "$state"; then
            log "WARN" "Halt transition detected!"
            add_halt_event "$state"
        fi

        # Evaluate alert rules (wrapped in error handling)
        if ! evaluate_alerts "$state" 2>/dev/null; then
            log "WARN" "Alert evaluation encountered issues (non-critical)"
        fi

        log "DEBUG" "Poll complete, mode=$(echo "$state" | jq -r '.mode // "unknown"')"

        sleep "$POLL_INTERVAL"
    done
}

# Start command
cmd_start() {
    # Check if already running
    if [[ -f "$PID_FILE" ]]; then
        local old_pid
        old_pid=$(cat "$PID_FILE")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "Monitor already running with PID $old_pid"
            exit 1
        fi
        # Stale PID file, remove it
        rm -f "$PID_FILE"
    fi

    load_config

    # Start in background
    poll_loop &
    local new_pid=$!
    echo "$new_pid" > "$PID_FILE"

    echo "Monitor started with PID $new_pid"
    echo "Log file: $LOG_FILE"
}

# Stop command
cmd_stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "Monitor not running (no PID file)"
        exit 1
    fi

    local pid
    pid=$(cat "$PID_FILE")

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        rm -f "$PID_FILE"
        echo "Monitor stopped (PID $pid)"
        log "INFO" "Monitor stopped by user"
    else
        rm -f "$PID_FILE"
        echo "Monitor was not running (stale PID file removed)"
    fi
}

# Status command
cmd_status() {
    echo "=== Sentinel Monitor Status ==="

    # Check if running
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Status: RUNNING (PID $pid)"
        else
            echo "Status: STOPPED (stale PID file)"
        fi
    else
        echo "Status: STOPPED"
    fi

    # Last poll info
    if [[ -f "$LAST_STATE_FILE" ]]; then
        local last_mod
        last_mod=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$LAST_STATE_FILE" 2>/dev/null || \
                   stat -c "%y" "$LAST_STATE_FILE" 2>/dev/null | cut -d'.' -f1)
        echo "Last poll: $last_mod"

        local last_mode
        last_mode=$(jq -r '.mode // "unknown"' "$LAST_STATE_FILE")
        echo "Last mode: $last_mode"
    else
        echo "Last poll: Never"
    fi

    # Pending events
    if [[ -f "$QUEUE_FILE" ]]; then
        local pending
        pending=$(jq '[.[] | select(.status == "pending")] | length' "$QUEUE_FILE")
        echo "Pending events: $pending"
    else
        echo "Pending events: 0"
    fi

    # Kill switch
    if [[ -f "$KILL_SWITCH_FILE" ]]; then
        echo "Kill switch: ACTIVE"
    else
        echo "Kill switch: Inactive"
    fi
}

# Health check constants
HEARTBEAT_MAX_AGE_SECONDS=120  # 2 minutes

# Check if heartbeat is recent (within last 2 minutes)
# Returns: 0 if healthy, 1 if stale/missing
check_heartbeat() {
    if [[ ! -f "$HEARTBEAT_FILE" ]]; then
        echo "Heartbeat: MISSING"
        return 1
    fi

    local last_heartbeat
    last_heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null)

    if [[ -z "$last_heartbeat" ]]; then
        echo "Heartbeat: INVALID (empty file)"
        return 1
    fi

    local current_time
    current_time=$(date +%s)
    local age=$((current_time - last_heartbeat))

    if [[ $age -gt $HEARTBEAT_MAX_AGE_SECONDS ]]; then
        echo "Heartbeat: STALE (${age}s ago, max ${HEARTBEAT_MAX_AGE_SECONDS}s)"
        return 1
    fi

    echo "Heartbeat: OK (${age}s ago)"
    return 0
}

# Check if PID file matches a running process
# Returns: 0 if healthy, 1 if unhealthy
check_pid_health() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "PID file: MISSING"
        return 1
    fi

    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null)

    if [[ -z "$pid" ]]; then
        echo "PID file: INVALID (empty)"
        return 1
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        echo "PID file: STALE (process $pid not running)"
        return 1
    fi

    echo "PID file: OK (process $pid running)"
    return 0
}

# Check SSH failure count from error log (approximation based on recent errors)
# Returns: 0 if healthy, 1 if too many failures
check_ssh_health() {
    # Count SSH failure messages in error log from last 10 minutes
    if [[ ! -f "$ERROR_LOG_FILE" ]]; then
        echo "SSH errors: OK (no error log)"
        return 0
    fi

    local cutoff_time
    cutoff_time=$(date -v-10M +%s 2>/dev/null || date -d '10 minutes ago' +%s 2>/dev/null)
    local current_time
    current_time=$(date +%s)

    # Count recent SSH errors (look for "SSH connection failed" in recent log entries)
    local recent_ssh_errors=0
    while IFS= read -r line; do
        # Extract timestamp from log line format: [YYYY-MM-DD HH:MM:SS] ERROR:
        if [[ "$line" =~ ^\[([0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2})\] ]]; then
            local log_timestamp="${BASH_REMATCH[1]}"
            local log_epoch
            log_epoch=$(date -j -f "%Y-%m-%d %H:%M:%S" "$log_timestamp" +%s 2>/dev/null || \
                       date -d "$log_timestamp" +%s 2>/dev/null)
            if [[ -n "$log_epoch" ]] && [[ $log_epoch -ge $cutoff_time ]]; then
                if [[ "$line" == *"SSH connection failed"* ]]; then
                    ((recent_ssh_errors++))
                fi
            fi
        fi
    done < <(grep -E "^\[.*\].*SSH connection failed" "$ERROR_LOG_FILE" 2>/dev/null | tail -20)

    if [[ $recent_ssh_errors -ge $MAX_SSH_FAILURES ]]; then
        echo "SSH errors: UNHEALTHY ($recent_ssh_errors failures in last 10 min, max $MAX_SSH_FAILURES)"
        return 1
    fi

    echo "SSH errors: OK ($recent_ssh_errors recent failures)"
    return 0
}

# Attempt self-recovery (stop then start)
# Returns: 0 on success, 1 on failure
attempt_self_recovery() {
    log "WARN" "Attempting self-recovery..."
    echo "Attempting self-recovery..."

    # Stop (quietly, ignoring errors)
    if [[ -f "$PID_FILE" ]]; then
        local old_pid
        old_pid=$(cat "$PID_FILE" 2>/dev/null)
        if [[ -n "$old_pid" ]]; then
            kill "$old_pid" 2>/dev/null || true
            sleep 1
            # Force kill if still running
            kill -9 "$old_pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi

    # Clear heartbeat to force fresh start
    rm -f "$HEARTBEAT_FILE"

    # Wait a moment for cleanup
    sleep 2

    # Start fresh
    load_config
    poll_loop &
    local new_pid=$!
    echo "$new_pid" > "$PID_FILE"

    # Wait for first heartbeat (up to 10 seconds)
    local wait_count=0
    while [[ $wait_count -lt 10 ]]; do
        sleep 1
        ((wait_count++))
        if [[ -f "$HEARTBEAT_FILE" ]]; then
            local hb
            hb=$(cat "$HEARTBEAT_FILE" 2>/dev/null)
            local now
            now=$(date +%s)
            if [[ -n "$hb" ]] && [[ $((now - hb)) -lt 5 ]]; then
                log "INFO" "Self-recovery successful - monitor restarted with PID $new_pid"
                echo "Self-recovery SUCCESSFUL - new PID: $new_pid"
                return 0
            fi
        fi
    done

    log_error "Self-recovery failed - no heartbeat after restart"
    echo "Self-recovery FAILED - no heartbeat detected"
    return 1
}

# Send recovery failure notification via Telegram
send_recovery_failure_notification() {
    local health_summary="$1"

    local message="🔴 <b>SENTINEL SELF-RECOVERY FAILED</b>

The Sentinel monitor attempted self-recovery but failed.
Manual intervention is required.

<b>Health Check Summary:</b>
<code>$health_summary</code>

<b>Time:</b> $(date -u '+%Y-%m-%d %H:%M UTC')

<b>Actions to try:</b>
• SSH to Mac and check: <code>./sentinel/sentinel_monitor.sh status</code>
• Check logs: <code>cat sentinel/state/error.log | tail -20</code>
• Manual restart: <code>./sentinel/sentinel_monitor.sh start</code>"

    # Escape for Python string
    local escaped_message
    escaped_message=$(echo "$message" | sed 's/\\/\\\\/g; s/"/\\"/g')

    # Load config if not already loaded
    if [[ -z "${VPS_HOST:-}" ]]; then
        load_config
    fi

    # Send via VPS telegram_handler (best effort)
    local python_script="
import sys
sys.path.insert(0, '/opt/polymarket-autotrader')
from bot.telegram_handler import TelegramBot

bot = TelegramBot()
if bot.enabled:
    bot.send_message_sync('''$escaped_message''', parse_mode='HTML', silent=False)
"

    ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes \
        "$VPS_HOST" "cd /opt/polymarket-autotrader && python3 -c \"$python_script\"" 2>/dev/null || true
}

# Health command - comprehensive health check with optional self-recovery
cmd_health() {
    echo "=== Sentinel Monitor Health Check ==="
    echo ""

    local health_issues=0
    local health_summary=""

    # Load config for SSH checks
    load_config 2>/dev/null || true

    # Check 1: PID file matches running process
    local pid_status
    pid_status=$(check_pid_health)
    echo "$pid_status"
    health_summary+="$pid_status"$'\n'
    if [[ $? -ne 0 ]] || [[ "$pid_status" != *"OK"* ]]; then
        ((health_issues++))
    fi

    # Check 2: Heartbeat within last 2 minutes
    local heartbeat_status
    heartbeat_status=$(check_heartbeat)
    echo "$heartbeat_status"
    health_summary+="$heartbeat_status"$'\n'
    if [[ $? -ne 0 ]] || [[ "$heartbeat_status" != *"OK"* ]]; then
        ((health_issues++))
    fi

    # Check 3: No repeated SSH failures
    local ssh_status
    ssh_status=$(check_ssh_health)
    echo "$ssh_status"
    health_summary+="$ssh_status"$'\n'
    if [[ $? -ne 0 ]] || [[ "$ssh_status" != *"OK"* ]]; then
        ((health_issues++))
    fi

    echo ""

    if [[ $health_issues -eq 0 ]]; then
        echo "Overall: HEALTHY ✓"
        return 0
    fi

    echo "Overall: UNHEALTHY ($health_issues issues detected)"
    echo ""

    # Attempt self-recovery
    echo "Initiating self-recovery..."
    if attempt_self_recovery; then
        echo ""
        echo "Monitor recovered successfully."
        log "INFO" "Health check triggered self-recovery - success"
        return 0
    else
        echo ""
        echo "Self-recovery failed. Sending Telegram alert..."
        send_recovery_failure_notification "$health_summary"
        log_error "Health check triggered self-recovery - FAILED"
        return 1
    fi
}

# Main entry point
main() {
    case "${1:-}" in
        start)
            cmd_start
            ;;
        stop)
            cmd_stop
            ;;
        status)
            cmd_status
            ;;
        health)
            cmd_health
            ;;
        *)
            echo "Usage: $0 {start|stop|status|health}"
            exit 1
            ;;
    esac
}

main "$@"
