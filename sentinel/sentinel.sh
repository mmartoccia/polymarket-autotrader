#!/bin/bash
#
# Sentinel Main Orchestrator
# Processes halt events from queue, invokes Claude for diagnosis, executes actions
#
# Usage:
#   ./sentinel.sh              - Process pending events from queue
#   ./sentinel.sh --dry-run    - Analyze without executing actions
#
# This script is typically called by the monitor daemon when events are queued,
# but can also be run manually.
#

set -o pipefail

# Get script directory for relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/sentinel_config.json"
STATE_DIR="$SCRIPT_DIR/state"
EVENTS_DIR="$SCRIPT_DIR/events"
HISTORY_DIR="$SCRIPT_DIR/history"
QUEUE_FILE="$EVENTS_DIR/queue.json"
ACTIONS_LOG="$HISTORY_DIR/actions.log"
KILL_SWITCH_FILE="$STATE_DIR/KILL_SWITCH"
LOCK_FILE="$STATE_DIR/sentinel.lock"
RATE_LIMIT_FILE="$STATE_DIR/rate_limit.json"
DIAGNOSE_PROMPT="$SCRIPT_DIR/sentinel_diagnose.md"
TELEGRAM_TIMEOUT_SECONDS=900  # 15 minutes - loaded from config
TELEGRAM_POLL_INTERVAL=10    # Poll every 10 seconds

# Ensure directories exist
mkdir -p "$STATE_DIR" "$HISTORY_DIR"

# Parse arguments
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# Load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "ERROR: Config file not found: $CONFIG_FILE" >&2
        exit 1
    fi

    MAX_AUTO_FIXES_PER_HOUR=$(jq -r '.rate_limits.max_auto_fixes_per_hour // 3' "$CONFIG_FILE")
    CONSECUTIVE_FIX_LIMIT=$(jq -r '.rate_limits.consecutive_fix_limit // 2' "$CONFIG_FILE")
    BALANCE_FLOOR=$(jq -r '.safety.balance_floor // 50' "$CONFIG_FILE")
    MIN_CONFIDENCE=$(jq -r '.safety.min_confidence_for_auto_fix // 70' "$CONFIG_FILE")
    VPS_HOST=$(jq -r '.vps.host' "$CONFIG_FILE")
    SSH_KEY=$(jq -r '.vps.ssh_key' "$CONFIG_FILE")
    SSH_KEY="${SSH_KEY/#\~/$HOME}"
    STATE_FILES=$(jq -r '.vps.state_files | join(" ")' "$CONFIG_FILE")
    VPS_LOG_FILE=$(jq -r '.vps.log_file' "$CONFIG_FILE")
    SSH_TIMEOUT=$(jq -r '.polling.ssh_timeout_seconds // 10' "$CONFIG_FILE")
    TELEGRAM_TIMEOUT_SECONDS=$(jq -r '.escalation.telegram_timeout_seconds // 900' "$CONFIG_FILE")
}

# Log action to history
log_action() {
    local event_id="$1"
    local action="$2"
    local result="$3"
    local reason="$4"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "[$timestamp] event=$event_id action=$action result=$result reason=\"$reason\"" >> "$ACTIONS_LOG"
}

# Log message to console and history
log() {
    local level="$1"
    local msg="$2"
    echo "[$level] $msg"
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [$level] $msg" >> "$ACTIONS_LOG"
}

# Check kill switch
check_kill_switch() {
    if [[ -f "$KILL_SWITCH_FILE" ]]; then
        log "WARN" "Kill switch active - aborting all processing"
        return 1
    fi
    return 0
}

# Acquire lock (only one sentinel.sh can run at a time)
acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local lock_pid
        lock_pid=$(cat "$LOCK_FILE")
        if kill -0 "$lock_pid" 2>/dev/null; then
            log "WARN" "Another sentinel.sh is running (PID $lock_pid)"
            return 1
        fi
        # Stale lock file
        rm -f "$LOCK_FILE"
    fi
    echo $$ > "$LOCK_FILE"
    return 0
}

# Release lock
release_lock() {
    rm -f "$LOCK_FILE"
}

# Check rate limit (max auto-fixes per hour)
check_rate_limit() {
    local current_hour
    current_hour=$(date +"%Y-%m-%d-%H")
    local count=0

    if [[ -f "$RATE_LIMIT_FILE" ]]; then
        local stored_hour
        stored_hour=$(jq -r '.hour // ""' "$RATE_LIMIT_FILE")
        if [[ "$stored_hour" == "$current_hour" ]]; then
            count=$(jq -r '.count // 0' "$RATE_LIMIT_FILE")
        fi
    fi

    if [[ $count -ge $MAX_AUTO_FIXES_PER_HOUR ]]; then
        log "WARN" "Rate limit reached ($count/$MAX_AUTO_FIXES_PER_HOUR auto-fixes this hour)"
        return 1
    fi

    return 0
}

# Increment rate limit counter
increment_rate_limit() {
    local current_hour
    current_hour=$(date +"%Y-%m-%d-%H")
    local count=0

    if [[ -f "$RATE_LIMIT_FILE" ]]; then
        local stored_hour
        stored_hour=$(jq -r '.hour // ""' "$RATE_LIMIT_FILE")
        if [[ "$stored_hour" == "$current_hour" ]]; then
            count=$(jq -r '.count // 0' "$RATE_LIMIT_FILE")
        fi
    fi

    count=$((count + 1))
    echo "{\"hour\": \"$current_hour\", \"count\": $count}" > "$RATE_LIMIT_FILE"
}

# Get VPS state via SSH
get_vps_state() {
    local state_file
    local state_json

    for state_file in $STATE_FILES; do
        state_json=$(ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
            "$VPS_HOST" "cat '$state_file' 2>/dev/null" 2>/dev/null)

        if [[ $? -eq 0 ]] && [[ -n "$state_json" ]]; then
            if echo "$state_json" | jq . >/dev/null 2>&1; then
                echo "$state_json"
                return 0
            fi
        fi
    done

    return 1
}

# Get recent VPS logs
get_recent_logs() {
    local lines="${1:-50}"
    ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
        "$VPS_HOST" "tail -$lines '$VPS_LOG_FILE' 2>/dev/null" 2>/dev/null
}

# Get on-chain USDC balance
get_onchain_balance() {
    # Read wallet address from VPS .env
    local wallet
    wallet=$(ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
        "$VPS_HOST" "grep POLYMARKET_WALLET /opt/polymarket-autotrader/.env | cut -d'=' -f2" 2>/dev/null)

    if [[ -z "$wallet" ]]; then
        echo "unknown"
        return 1
    fi

    # Query Polygon RPC for USDC balance
    local usdc_contract="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    local rpc_url="https://polygon-rpc.com"

    # Format wallet address for data field (remove 0x, pad to 32 bytes)
    local wallet_padded
    wallet_padded=$(echo "$wallet" | sed 's/0x//' | tr '[:upper:]' '[:lower:]')
    wallet_padded="000000000000000000000000$wallet_padded"

    local response
    response=$(curl -s -X POST "$rpc_url" \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_call\",\"params\":[{\"to\":\"$usdc_contract\",\"data\":\"0x70a08231$wallet_padded\"},\"latest\"],\"id\":1}" \
        2>/dev/null)

    if [[ -z "$response" ]]; then
        echo "unknown"
        return 1
    fi

    local balance_hex
    balance_hex=$(echo "$response" | jq -r '.result // "0x0"')

    if [[ "$balance_hex" == "null" ]] || [[ -z "$balance_hex" ]]; then
        echo "unknown"
        return 1
    fi

    # Convert hex to decimal and divide by 10^6 (USDC has 6 decimals)
    local balance_wei
    balance_wei=$(printf "%d" "$balance_hex" 2>/dev/null || echo "0")
    local balance_usd
    balance_usd=$(echo "scale=2; $balance_wei / 1000000" | bc 2>/dev/null || echo "0")

    echo "$balance_usd"
}

# Send Telegram notification via VPS
# Uses the existing telegram_handler.py infrastructure
# Returns: 0 on success, 1 on failure
send_telegram_notification() {
    local message="$1"
    local silent="${2:-false}"  # Optional: send without notification sound

    # Escape the message for Python string (escape quotes and backslashes)
    local escaped_message
    escaped_message=$(echo "$message" | sed 's/\\/\\\\/g; s/"/\\"/g')

    # Create a Python script to send via TelegramBot
    local python_script="
import sys
sys.path.insert(0, '/opt/polymarket-autotrader')
from bot.telegram_handler import TelegramBot

bot = TelegramBot()
if not bot.enabled:
    print('Telegram not enabled')
    sys.exit(1)

result = bot.send_message_sync('''$escaped_message''', parse_mode='HTML', silent=$silent)
if result:
    print('Message sent successfully')
    sys.exit(0)
else:
    print('Failed to send message')
    sys.exit(1)
"

    # Execute on VPS
    local result
    result=$(ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
        "$VPS_HOST" "cd /opt/polymarket-autotrader && python3 -c \"$python_script\"" 2>&1)

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log "INFO" "Telegram notification sent successfully"
        return 0
    else
        log "WARN" "Failed to send Telegram notification: $result"
        return 1
    fi
}

# Format and send halt alert via Telegram
# This is called before any auto-fix processing
send_halt_alert() {
    local event="$1"
    local analysis_summary="$2"
    local recommended_action="$3"
    local confidence="$4"

    local halt_reason
    local balance
    local peak_balance
    local drawdown_pct
    local timestamp

    halt_reason=$(echo "$event" | jq -r '.halt_reason // "Unknown"')
    balance=$(echo "$event" | jq -r '.balance // 0')
    peak_balance=$(echo "$event" | jq -r '.peak_balance // 0')
    timestamp=$(date -u +"%Y-%m-%d %H:%M UTC")

    # Calculate drawdown percentage
    if (( $(echo "$peak_balance > 0" | bc -l) )); then
        drawdown_pct=$(echo "scale=1; ($peak_balance - $balance) / $peak_balance * 100" | bc)
    else
        drawdown_pct="0"
    fi

    # Convert timeout to minutes for display
    local timeout_minutes=$((TELEGRAM_TIMEOUT_SECONDS / 60))

    # Build the message with proper formatting
    local message="🚨 <b>SENTINEL ALERT</b> 🚨

<b>Bot Status:</b> HALTED
<b>Reason:</b> $halt_reason
<b>Time:</b> $timestamp

<b>💰 Financial Status</b>
Balance: \$$balance
Peak: \$$peak_balance
Drawdown: ${drawdown_pct}%

<b>🤖 Analysis Summary</b>
$analysis_summary

<b>📋 Recommended Action</b>
<code>$recommended_action</code> (${confidence}% confidence)

<b>⏰ Response Options</b>
/approve - Execute recommended action
/deny - Leave bot halted
/custom &lt;action&gt; - Specify alternative

⚠️ Auto-fix in $timeout_minutes minutes if no response"

    # Send synchronously to confirm delivery
    send_telegram_notification "$message" "false"
    return $?
}

# Poll Telegram for recent commands from user
# Returns: command string if found, empty string if none
poll_telegram_commands() {
    local since_minutes="${1:-5}"

    # Create Python script to get recent commands
    local python_script="
import sys
sys.path.insert(0, '/opt/polymarket-autotrader')
from bot.telegram_handler import TelegramBot

bot = TelegramBot()
if not bot.enabled:
    sys.exit(1)

commands = bot.get_recent_commands(since_minutes=$since_minutes)
if commands:
    # Return the most recent command
    print(commands[-1])
else:
    print('')
"

    # Execute on VPS
    local result
    result=$(ssh -i "$SSH_KEY" -o ConnectTimeout="$SSH_TIMEOUT" -o BatchMode=yes \
        "$VPS_HOST" "cd /opt/polymarket-autotrader && python3 -c \"$python_script\"" 2>/dev/null)

    echo "$result"
}

# Wait for user response via Telegram with timeout
# Returns: "approve", "deny", "custom <action>", or "timeout"
wait_for_telegram_response() {
    local timeout_seconds="$1"
    local poll_interval="${2:-$TELEGRAM_POLL_INTERVAL}"

    local elapsed=0
    local start_time
    start_time=$(date +%s)

    log "INFO" "Waiting for Telegram response (timeout: ${timeout_seconds}s)..."

    # Track what commands we've already seen to detect new ones
    local initial_commands
    initial_commands=$(poll_telegram_commands 1)

    while [[ $elapsed -lt $timeout_seconds ]]; do
        sleep "$poll_interval"
        elapsed=$(($(date +%s) - start_time))

        # Poll for new commands (within last 2 minutes to catch recent)
        local commands
        commands=$(poll_telegram_commands 2)

        if [[ -n "$commands" ]] && [[ "$commands" != "$initial_commands" ]]; then
            # Parse the command
            local cmd
            cmd=$(echo "$commands" | tr '[:upper:]' '[:lower:]' | xargs)

            case "$cmd" in
                /approve|"/approve")
                    log "INFO" "User approved via Telegram"
                    echo "approve"
                    return 0
                    ;;
                /deny*|"/deny"*)
                    log "INFO" "User denied via Telegram: $cmd"
                    echo "deny"
                    return 0
                    ;;
                /custom*)
                    local custom_action
                    custom_action=$(echo "$cmd" | sed 's|^/custom[[:space:]]*||')
                    log "INFO" "User requested custom action: $custom_action"
                    echo "custom $custom_action"
                    return 0
                    ;;
                /halt|"/halt")
                    log "INFO" "User requested halt via Telegram"
                    echo "deny"
                    return 0
                    ;;
                *)
                    # Other commands - ignore and continue waiting
                    ;;
            esac
        fi

        # Log progress every minute
        if (( elapsed % 60 == 0 )) && (( elapsed > 0 )); then
            local remaining=$((timeout_seconds - elapsed))
            log "INFO" "Still waiting... ${remaining}s remaining"
        fi
    done

    log "INFO" "Telegram response timeout reached"
    echo "timeout"
    return 0
}

# Send confirmation message after action
send_action_confirmation() {
    local action="$1"
    local result="$2"
    local trigger="$3"  # "user_approved", "user_denied", "timeout_auto_fix", "custom"

    local emoji
    local header

    case "$trigger" in
        user_approved)
            emoji="✅"
            header="ACTION EXECUTED"
            ;;
        user_denied)
            emoji="🛑"
            header="ACTION DENIED"
            ;;
        timeout_auto_fix)
            emoji="⚙️"
            header="SENTINEL AUTO-FIX"
            ;;
        custom)
            emoji="🔧"
            header="CUSTOM ACTION"
            ;;
        *)
            emoji="ℹ️"
            header="SENTINEL UPDATE"
            ;;
    esac

    local timestamp
    timestamp=$(date -u +"%Y-%m-%d %H:%M UTC")

    local message="$emoji <b>$header</b>

<b>Action:</b> $action
<b>Result:</b> $result
<b>Time:</b> $timestamp"

    if [[ "$trigger" == "timeout_auto_fix" ]]; then
        message+="

Reply /halt to stop if needed"
    fi

    send_telegram_notification "$message" "false"
}

# Gather diagnostics for Claude
gather_diagnostics() {
    local event="$1"
    local diagnostics=""

    diagnostics+="## Event Information\n"
    diagnostics+="$(echo "$event" | jq .)\n\n"

    diagnostics+="## Current VPS State\n"
    local vps_state
    vps_state=$(get_vps_state)
    if [[ $? -eq 0 ]]; then
        diagnostics+="\`\`\`json\n$vps_state\n\`\`\`\n\n"
    else
        diagnostics+="ERROR: Could not retrieve VPS state\n\n"
    fi

    diagnostics+="## On-Chain USDC Balance\n"
    local onchain_balance
    onchain_balance=$(get_onchain_balance)
    diagnostics+="\$$onchain_balance\n\n"

    diagnostics+="## Recent Bot Logs (last 30 lines)\n"
    diagnostics+="\`\`\`\n"
    diagnostics+="$(get_recent_logs 30)\n"
    diagnostics+="\`\`\`\n"

    echo -e "$diagnostics"
}

# Invoke Claude for diagnosis
invoke_claude_diagnosis() {
    local diagnostics="$1"
    local prompt_content

    if [[ ! -f "$DIAGNOSE_PROMPT" ]]; then
        log "ERROR" "Diagnose prompt not found: $DIAGNOSE_PROMPT"
        return 1
    fi

    prompt_content=$(cat "$DIAGNOSE_PROMPT")

    # Create full prompt with diagnostics
    local full_prompt="$prompt_content

---

# Current Situation

$diagnostics

---

Please analyze the above situation and provide your diagnosis in the JSON format specified above."

    # Invoke Claude Code with the prompt
    local claude_output
    claude_output=$(echo "$full_prompt" | claude --dangerously-skip-permissions -p 2>/dev/null)

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Claude invocation failed"
        return 1
    fi

    echo "$claude_output"
}

# Parse JSON decision from Claude output
parse_decision() {
    local claude_output="$1"

    # Extract JSON block from output (between ```json and ```)
    local json_block
    json_block=$(echo "$claude_output" | sed -n '/```json/,/```/p' | sed '1d;$d')

    if [[ -z "$json_block" ]]; then
        # Try to find raw JSON
        json_block=$(echo "$claude_output" | grep -o '{[^}]*"decision"[^}]*}' | head -1)
    fi

    if [[ -z "$json_block" ]]; then
        log "ERROR" "Could not parse JSON decision from Claude output"
        return 1
    fi

    # Validate JSON
    if ! echo "$json_block" | jq . >/dev/null 2>&1; then
        log "ERROR" "Invalid JSON in Claude decision"
        return 1
    fi

    echo "$json_block"
}

# Update event status in queue
update_event_status() {
    local event_id="$1"
    local new_status="$2"
    local result="$3"

    local queue
    queue=$(cat "$QUEUE_FILE")

    # Update the event
    queue=$(echo "$queue" | jq --arg id "$event_id" --arg status "$new_status" --arg result "$result" \
        '(.[] | select(.id == $id)) |= . + {status: $status, result: $result, processed_at: (now | todate)}')

    echo "$queue" > "$QUEUE_FILE"
}

# Process a single event
process_event() {
    local event="$1"
    local event_id
    local halt_reason
    local balance

    event_id=$(echo "$event" | jq -r '.id')
    halt_reason=$(echo "$event" | jq -r '.halt_reason // "unknown"')
    balance=$(echo "$event" | jq -r '.balance // 0')

    log "INFO" "Processing event: $event_id (reason: $halt_reason)"

    # Safety check: Balance floor
    if (( $(echo "$balance < $BALANCE_FLOOR" | bc -l) )); then
        log "WARN" "Balance \$$balance below floor \$$BALANCE_FLOOR - escalating"
        update_event_status "$event_id" "escalated" "balance_below_floor"
        log_action "$event_id" "escalate" "balance_below_floor" "Balance below safety floor"
        return 0
    fi

    # Gather diagnostics
    log "INFO" "Gathering diagnostics..."
    local diagnostics
    diagnostics=$(gather_diagnostics "$event")

    # Invoke Claude
    log "INFO" "Invoking Claude for diagnosis..."
    local claude_output
    claude_output=$(invoke_claude_diagnosis "$diagnostics")

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Claude diagnosis failed - escalating"
        update_event_status "$event_id" "escalated" "claude_error"
        log_action "$event_id" "escalate" "claude_error" "Claude invocation failed"
        return 1
    fi

    # Parse decision
    local decision
    decision=$(parse_decision "$claude_output")

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Could not parse Claude decision - escalating"
        update_event_status "$event_id" "escalated" "parse_error"
        log_action "$event_id" "escalate" "parse_error" "Could not parse Claude decision"
        return 1
    fi

    # Extract decision fields
    local decision_type
    local action
    local reason
    local confidence

    decision_type=$(echo "$decision" | jq -r '.decision')
    action=$(echo "$decision" | jq -r '.action // "none"')
    reason=$(echo "$decision" | jq -r '.reason')
    confidence=$(echo "$decision" | jq -r '.confidence // 0')

    log "INFO" "Claude decision: $decision_type (action: $action, confidence: $confidence%)"
    log "INFO" "Reason: $reason"

    # Dry run check - skip notification and polling
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] Would send Telegram notification and wait for response"
        log "INFO" "[DRY RUN] Decision: $decision_type, Action: $action, Confidence: $confidence%"
        update_event_status "$event_id" "dry_run" "$action"
        log_action "$event_id" "dry_run" "$action" "$reason"
        return 0
    fi

    # Send Telegram notification
    log "INFO" "Sending Telegram halt alert..."
    if ! send_halt_alert "$event" "$reason" "$action" "$confidence"; then
        log "WARN" "Failed to send Telegram notification - escalating"
        update_event_status "$event_id" "escalated" "telegram_error"
        log_action "$event_id" "escalate" "telegram_error" "Failed to send notification"
        return 1
    fi
    log "INFO" "Telegram notification sent successfully"

    # Wait for user response (unless Claude recommends escalation)
    local user_response
    if [[ "$decision_type" == "escalate" ]]; then
        # For escalations, notify but don't wait for response or auto-fix
        log "INFO" "Claude recommends escalation - notifying user only (no auto-fix)"
        update_event_status "$event_id" "escalated" "claude_escalate"
        log_action "$event_id" "escalate" "claude_decision" "$reason"
        return 0
    fi

    # Wait for user response
    user_response=$(wait_for_telegram_response "$TELEGRAM_TIMEOUT_SECONDS" "$TELEGRAM_POLL_INTERVAL")

    # Handle user response
    case "$user_response" in
        approve)
            log "INFO" "User approved action: $action"

            # Check rate limit before execution
            if ! check_rate_limit; then
                log "WARN" "Rate limit reached - cannot execute"
                send_action_confirmation "$action" "FAILED - rate limit exceeded" "user_approved"
                update_event_status "$event_id" "error" "rate_limit"
                log_action "$event_id" "error" "rate_limit_on_approve" "User approved but rate limit exceeded"
                return 0
            fi

            # Execute the approved action (stub for now, US-008 will implement)
            log "INFO" "Executing approved action: $action"
            # TODO: Actual execution in US-008
            send_action_confirmation "$action" "Executed successfully" "user_approved"
            update_event_status "$event_id" "completed" "$action"
            log_action "$event_id" "execute" "$action" "User approved via Telegram"
            increment_rate_limit
            return 0
            ;;

        deny)
            log "INFO" "User denied action - leaving bot halted"
            send_action_confirmation "$action" "Denied by user - bot remains halted" "user_denied"
            update_event_status "$event_id" "denied" "user_denied"
            log_action "$event_id" "deny" "user_denied" "User denied via Telegram"
            return 0
            ;;

        custom*)
            local custom_action
            custom_action=$(echo "$user_response" | sed 's|^custom[[:space:]]*||')
            log "INFO" "User requested custom action: $custom_action"

            # Validate custom action is in allowed list
            local allowed_actions="reset_peak_balance resume_trading reset_loss_streak restart_bot"
            if echo "$allowed_actions" | grep -qw "$custom_action"; then
                log "INFO" "Custom action is valid: $custom_action"
                # TODO: Actual execution in US-008
                send_action_confirmation "$custom_action" "Executed successfully" "custom"
                update_event_status "$event_id" "completed" "$custom_action"
                log_action "$event_id" "execute" "$custom_action" "User requested custom action via Telegram"
                increment_rate_limit
            else
                log "WARN" "Invalid custom action: $custom_action"
                send_action_confirmation "$custom_action" "FAILED - invalid action. Allowed: $allowed_actions" "custom"
                update_event_status "$event_id" "error" "invalid_custom"
                log_action "$event_id" "error" "invalid_custom" "User requested invalid custom action: $custom_action"
            fi
            return 0
            ;;

        timeout)
            log "INFO" "Timeout reached - checking if auto-fix should proceed"

            # Check confidence threshold for auto-fix
            if [[ $confidence -lt $MIN_CONFIDENCE ]]; then
                log "WARN" "Confidence $confidence% below threshold $MIN_CONFIDENCE% - leaving halted"
                send_telegram_notification "⏰ <b>TIMEOUT - NO AUTO-FIX</b>

Confidence ($confidence%) below threshold ($MIN_CONFIDENCE%)
Bot remains <b>HALTED</b>

Manual intervention required." "false"
                update_event_status "$event_id" "timeout_no_fix" "low_confidence"
                log_action "$event_id" "timeout" "no_auto_fix" "Confidence below threshold after timeout"
                return 0
            fi

            # Check rate limit
            if ! check_rate_limit; then
                log "WARN" "Rate limit reached - cannot auto-fix"
                send_telegram_notification "⏰ <b>TIMEOUT - NO AUTO-FIX</b>

Rate limit exceeded (max $MAX_AUTO_FIXES_PER_HOUR/hour)
Bot remains <b>HALTED</b>

Manual intervention required." "false"
                update_event_status "$event_id" "timeout_no_fix" "rate_limit"
                log_action "$event_id" "timeout" "no_auto_fix" "Rate limit exceeded after timeout"
                return 0
            fi

            # Auto-fix on timeout
            log "INFO" "Auto-fix on timeout: $action (confidence: $confidence%)"
            # TODO: Actual execution in US-008
            send_action_confirmation "$action" "Executed automatically after ${TELEGRAM_TIMEOUT_SECONDS}s timeout" "timeout_auto_fix"
            update_event_status "$event_id" "auto_fixed" "$action"
            log_action "$event_id" "auto_fix" "$action" "Timeout auto-fix (confidence: $confidence%)"
            increment_rate_limit
            return 0
            ;;

        *)
            log "ERROR" "Unexpected response: $user_response"
            update_event_status "$event_id" "error" "unexpected_response"
            log_action "$event_id" "error" "unexpected_response" "Unexpected Telegram response: $user_response"
            return 1
            ;;
    esac
}

# Get pending events from queue
get_pending_events() {
    if [[ ! -f "$QUEUE_FILE" ]]; then
        echo "[]"
        return
    fi

    jq '[.[] | select(.status == "pending")]' "$QUEUE_FILE"
}

# Main processing loop
main() {
    log "INFO" "Sentinel orchestrator starting"

    # Load config
    load_config

    # Check kill switch
    if ! check_kill_switch; then
        exit 1
    fi

    # Acquire lock
    if ! acquire_lock; then
        exit 1
    fi

    # Ensure cleanup on exit
    trap release_lock EXIT

    # Get pending events
    local pending
    pending=$(get_pending_events)
    local count
    count=$(echo "$pending" | jq 'length')

    if [[ $count -eq 0 ]]; then
        log "INFO" "No pending events in queue"
        exit 0
    fi

    log "INFO" "Found $count pending event(s)"

    # Process each event
    echo "$pending" | jq -c '.[]' | while read -r event; do
        process_event "$event"
    done

    log "INFO" "Sentinel orchestrator complete"
}

main "$@"
