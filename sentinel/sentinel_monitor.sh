#!/bin/bash
#
# Sentinel Monitor Daemon
# Polls VPS state every 30 seconds and detects halt events
#
# Usage:
#   ./sentinel_monitor.sh start   - Start polling daemon in background
#   ./sentinel_monitor.sh stop    - Stop the polling daemon
#   ./sentinel_monitor.sh status  - Show current status
#

set -o pipefail

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

# Get VPS state via SSH
get_vps_state() {
    local state_file
    local state_json

    # Try each state file in order (primary first, then fallback)
    for state_file in $STATE_FILES; do
        state_json=$(ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
            "$VPS_HOST" "cat '$state_file' 2>/dev/null" 2>/dev/null)

        if [[ $? -eq 0 ]] && [[ -n "$state_json" ]]; then
            # Validate it's valid JSON
            if echo "$state_json" | jq . >/dev/null 2>&1; then
                echo "$state_json"
                return 0
            fi
        fi
    done

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

# Main polling loop
poll_loop() {
    log "INFO" "Monitor started with PID $$"

    while true; do
        # Check kill switch
        if [[ -f "$KILL_SWITCH_FILE" ]]; then
            log "WARN" "Kill switch active, skipping poll cycle"
            sleep "$POLL_INTERVAL"
            continue
        fi

        # Get VPS state
        local state
        state=$(get_vps_state)

        if [[ $? -ne 0 ]] || [[ -z "$state" ]]; then
            log "ERROR" "Failed to get VPS state"
            sleep "$POLL_INTERVAL"
            continue
        fi

        # Check for halt transition
        if check_halt_transition "$state"; then
            log "WARN" "Halt transition detected!"
            add_halt_event "$state"
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
        *)
            echo "Usage: $0 {start|stop|status}"
            exit 1
            ;;
    esac
}

main "$@"
