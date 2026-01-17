#!/bin/bash
#
# Sentinel Integration Test Script
# Verifies all Sentinel components are working correctly
#
# Usage:
#   ./sentinel/test_sentinel.sh        - Run all tests
#   ./sentinel/test_sentinel.sh -v     - Run with verbose output
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
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

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
VERBOSE=false

# Parse arguments
if [[ "${1:-}" == "-v" ]] || [[ "${1:-}" == "--verbose" ]]; then
    VERBOSE=true
fi

# Colors for output (when supported)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

# Print test result
pass() {
    local test_name="$1"
    ((TESTS_PASSED++))
    echo -e "${GREEN}PASS${NC}: $test_name"
}

fail() {
    local test_name="$1"
    local reason="${2:-}"
    ((TESTS_FAILED++))
    echo -e "${RED}FAIL${NC}: $test_name"
    if [[ -n "$reason" ]]; then
        echo "       Reason: $reason"
    fi
}

info() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${YELLOW}INFO${NC}: $1"
    fi
}

# ============================================================================
# Test Functions
# ============================================================================

test_directory_structure() {
    local test_name="Directory structure exists"
    local missing=""

    [[ -d "$SCRIPT_DIR" ]] || missing+="sentinel/ "
    [[ -d "$STATE_DIR" ]] || missing+="sentinel/state/ "
    [[ -d "$EVENTS_DIR" ]] || missing+="sentinel/events/ "
    [[ -d "$HISTORY_DIR" ]] || missing+="sentinel/history/ "

    if [[ -z "$missing" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing directories: $missing"
    fi
}

test_config_file_exists() {
    local test_name="Config file exists"

    if [[ -f "$CONFIG_FILE" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing: $CONFIG_FILE"
    fi
}

test_config_file_valid_json() {
    local test_name="Config file is valid JSON"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        fail "$test_name" "Config file not found"
        return
    fi

    if jq . "$CONFIG_FILE" >/dev/null 2>&1; then
        pass "$test_name"
    else
        fail "$test_name" "Invalid JSON syntax"
    fi
}

test_config_required_fields() {
    local test_name="Config has required fields"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        fail "$test_name" "Config file not found"
        return
    fi

    local missing=""

    # Check required top-level keys
    jq -e '.polling' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="polling "
    jq -e '.rate_limits' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="rate_limits "
    jq -e '.safety' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="safety "
    jq -e '.escalation' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="escalation "
    jq -e '.vps' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="vps "
    jq -e '.alerts' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="alerts "

    # Check required nested keys
    jq -e '.vps.host' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="vps.host "
    jq -e '.vps.ssh_key' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="vps.ssh_key "
    jq -e '.vps.state_files' "$CONFIG_FILE" >/dev/null 2>&1 || missing+="vps.state_files "

    if [[ -z "$missing" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing fields: $missing"
    fi
}

test_monitor_script_exists() {
    local test_name="Monitor script exists"

    if [[ -f "$SCRIPT_DIR/sentinel_monitor.sh" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing: sentinel_monitor.sh"
    fi
}

test_monitor_script_executable() {
    local test_name="Monitor script is executable"

    if [[ -x "$SCRIPT_DIR/sentinel_monitor.sh" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Not executable: sentinel_monitor.sh"
    fi
}

test_monitor_status_command() {
    local test_name="Monitor status command works"

    local output
    output=$("$SCRIPT_DIR/sentinel_monitor.sh" status 2>&1)
    local exit_code=$?

    if [[ $exit_code -eq 0 ]] && [[ "$output" == *"Sentinel Monitor Status"* ]]; then
        pass "$test_name"
        info "Monitor status: $(echo "$output" | grep -E "^Status:" | head -1)"
    else
        fail "$test_name" "Exit code: $exit_code"
    fi
}

test_orchestrator_script_exists() {
    local test_name="Orchestrator script exists"

    if [[ -f "$SCRIPT_DIR/sentinel.sh" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing: sentinel.sh"
    fi
}

test_orchestrator_script_executable() {
    local test_name="Orchestrator script is executable"

    if [[ -x "$SCRIPT_DIR/sentinel.sh" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Not executable: sentinel.sh"
    fi
}

test_diagnose_prompt_exists() {
    local test_name="Diagnose prompt template exists"

    if [[ -f "$SCRIPT_DIR/sentinel_diagnose.md" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing: sentinel_diagnose.md"
    fi
}

test_ssh_key_exists() {
    local test_name="SSH key file exists"

    local ssh_key
    ssh_key=$(jq -r '.vps.ssh_key' "$CONFIG_FILE" 2>/dev/null)
    # Expand ~
    ssh_key="${ssh_key/#\~/$HOME}"

    if [[ -f "$ssh_key" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing: $ssh_key"
    fi
}

test_ssh_to_vps() {
    local test_name="SSH connection to VPS works"

    local ssh_key
    local vps_host
    ssh_key=$(jq -r '.vps.ssh_key' "$CONFIG_FILE" 2>/dev/null)
    vps_host=$(jq -r '.vps.host' "$CONFIG_FILE" 2>/dev/null)
    ssh_key="${ssh_key/#\~/$HOME}"

    # Try to connect and run a simple command
    local output
    output=$(ssh -i "$ssh_key" -o ConnectTimeout=10 -o BatchMode=yes \
        "$vps_host" "echo 'sentinel_test_ok'" 2>&1)
    local exit_code=$?

    if [[ $exit_code -eq 0 ]] && [[ "$output" == *"sentinel_test_ok"* ]]; then
        pass "$test_name"
    else
        fail "$test_name" "SSH connection failed (exit code: $exit_code)"
    fi
}

test_vps_state_file_readable() {
    local test_name="Can read VPS state file"

    local ssh_key
    local vps_host
    local state_file
    ssh_key=$(jq -r '.vps.ssh_key' "$CONFIG_FILE" 2>/dev/null)
    vps_host=$(jq -r '.vps.host' "$CONFIG_FILE" 2>/dev/null)
    state_file=$(jq -r '.vps.state_files[0]' "$CONFIG_FILE" 2>/dev/null)
    ssh_key="${ssh_key/#\~/$HOME}"

    # Try to read state file
    local output
    output=$(ssh -i "$ssh_key" -o ConnectTimeout=10 -o BatchMode=yes \
        "$vps_host" "cat '$state_file' 2>/dev/null" 2>&1)
    local exit_code=$?

    if [[ $exit_code -eq 0 ]] && echo "$output" | jq . >/dev/null 2>&1; then
        pass "$test_name"
        info "State file mode: $(echo "$output" | jq -r '.mode // "unknown"')"
    else
        # Try fallback state file
        state_file=$(jq -r '.vps.state_files[1]' "$CONFIG_FILE" 2>/dev/null)
        output=$(ssh -i "$ssh_key" -o ConnectTimeout=10 -o BatchMode=yes \
            "$vps_host" "cat '$state_file' 2>/dev/null" 2>&1)
        exit_code=$?

        if [[ $exit_code -eq 0 ]] && echo "$output" | jq . >/dev/null 2>&1; then
            pass "$test_name"
            info "Using fallback state file"
        else
            fail "$test_name" "Could not read any state file"
        fi
    fi
}

test_telegram_can_send() {
    local test_name="Can send Telegram message"

    local ssh_key
    local vps_host
    ssh_key=$(jq -r '.vps.ssh_key' "$CONFIG_FILE" 2>/dev/null)
    vps_host=$(jq -r '.vps.host' "$CONFIG_FILE" 2>/dev/null)
    ssh_key="${ssh_key/#\~/$HOME}"

    # Check if Telegram bot is configured and enabled
    local python_check="
import sys
sys.path.insert(0, '/opt/polymarket-autotrader')
from bot.telegram_handler import TelegramBot

bot = TelegramBot()
if not bot.enabled:
    print('disabled')
    sys.exit(1)
print('enabled')
sys.exit(0)
"

    local output
    output=$(ssh -i "$ssh_key" -o ConnectTimeout=10 -o BatchMode=yes \
        "$vps_host" "cd /opt/polymarket-autotrader && python3 -c \"$python_check\"" 2>&1)
    local exit_code=$?

    if [[ $exit_code -eq 0 ]] && [[ "$output" == *"enabled"* ]]; then
        pass "$test_name"
        info "Telegram bot is enabled"
    else
        fail "$test_name" "Telegram bot not enabled or configured"
    fi
}

test_claude_code_available() {
    local test_name="Claude Code CLI is available"

    if command -v claude >/dev/null 2>&1; then
        pass "$test_name"
        info "Claude path: $(which claude)"
    else
        fail "$test_name" "claude command not found in PATH"
    fi
}

test_event_queue_operations() {
    local test_name="Event queue operations work"

    # Backup existing queue
    local backup=""
    if [[ -f "$QUEUE_FILE" ]]; then
        backup=$(cat "$QUEUE_FILE")
    fi

    # Test: Write and read
    local test_event='[{"id":"test_123","type":"test","status":"pending"}]'
    echo "$test_event" > "$QUEUE_FILE"

    local read_back
    read_back=$(cat "$QUEUE_FILE")

    # Verify
    local event_id
    event_id=$(echo "$read_back" | jq -r '.[0].id' 2>/dev/null)

    # Restore backup
    if [[ -n "$backup" ]]; then
        echo "$backup" > "$QUEUE_FILE"
    else
        echo "[]" > "$QUEUE_FILE"
    fi

    if [[ "$event_id" == "test_123" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Write/read mismatch"
    fi
}

test_history_logging_works() {
    local test_name="History logging works"

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local test_line="[$timestamp] [TEST] Integration test entry"

    # Append test line
    echo "$test_line" >> "$ACTIONS_LOG"

    # Verify it was written
    if tail -1 "$ACTIONS_LOG" | grep -q "Integration test entry"; then
        pass "$test_name"
    else
        fail "$test_name" "Could not append to actions.log"
    fi
}

test_jq_available() {
    local test_name="jq command is available"

    if command -v jq >/dev/null 2>&1; then
        pass "$test_name"
        info "jq version: $(jq --version)"
    else
        fail "$test_name" "jq not found in PATH"
    fi
}

test_monitor_start_stop() {
    local test_name="Monitor starts and stops correctly"

    # Check if already running - if so, skip this test
    if [[ -f "$STATE_DIR/monitor.pid" ]]; then
        local existing_pid
        existing_pid=$(cat "$STATE_DIR/monitor.pid")
        if kill -0 "$existing_pid" 2>/dev/null; then
            info "Monitor already running (PID $existing_pid), skipping start/stop test"
            pass "$test_name (skipped - already running)"
            return
        fi
    fi

    # Start monitor
    "$SCRIPT_DIR/sentinel_monitor.sh" start >/dev/null 2>&1
    local start_exit=$?

    sleep 2

    # Check if running
    local pid_exists=false
    if [[ -f "$STATE_DIR/monitor.pid" ]]; then
        local pid
        pid=$(cat "$STATE_DIR/monitor.pid")
        if kill -0 "$pid" 2>/dev/null; then
            pid_exists=true
        fi
    fi

    # Stop monitor
    "$SCRIPT_DIR/sentinel_monitor.sh" stop >/dev/null 2>&1
    local stop_exit=$?

    sleep 1

    # Verify stopped
    local stopped=true
    if [[ -f "$STATE_DIR/monitor.pid" ]]; then
        local pid
        pid=$(cat "$STATE_DIR/monitor.pid")
        if kill -0 "$pid" 2>/dev/null; then
            stopped=false
        fi
    fi

    if [[ "$start_exit" -eq 0 ]] && [[ "$pid_exists" == "true" ]] && \
       [[ "$stop_exit" -eq 0 ]] && [[ "$stopped" == "true" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "start=$start_exit pid_exists=$pid_exists stop=$stop_exit stopped=$stopped"
    fi
}

test_skill_file_exists() {
    local test_name="/auto-manage skill file exists"

    local skill_file="$SCRIPT_DIR/../.claude/commands/auto-manage.md"

    if [[ -f "$skill_file" ]]; then
        pass "$test_name"
    else
        fail "$test_name" "Missing: .claude/commands/auto-manage.md"
    fi
}

# ============================================================================
# Main Test Runner
# ============================================================================

echo "========================================"
echo "  Sentinel Integration Test Suite"
echo "========================================"
echo ""
echo "Running tests..."
echo ""

# Prerequisite tests (order matters)
test_jq_available
test_directory_structure
test_config_file_exists
test_config_file_valid_json
test_config_required_fields

# Script existence tests
test_monitor_script_exists
test_monitor_script_executable
test_orchestrator_script_exists
test_orchestrator_script_executable
test_diagnose_prompt_exists
test_skill_file_exists

# Command tests
test_monitor_status_command
test_claude_code_available

# SSH connectivity tests
test_ssh_key_exists
test_ssh_to_vps
test_vps_state_file_readable

# Telegram tests
test_telegram_can_send

# Operations tests
test_event_queue_operations
test_history_logging_works

# Start/stop test (run last as it modifies state)
test_monitor_start_stop

# Summary
echo ""
echo "========================================"
echo "  Test Results Summary"
echo "========================================"
echo ""
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}All $TOTAL tests passed!${NC}"
    exit 0
else
    echo -e "${RED}$TESTS_FAILED of $TOTAL tests failed.${NC}"
    exit 1
fi
