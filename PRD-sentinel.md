# PRD: Sentinel - Event-Driven Autonomous Bot Management

## Introduction

Sentinel is an event-driven autonomous monitoring system that watches the trading bot for halt events, performance degradation, and configurable alerts. When issues are detected, Sentinel notifies the user via Telegram first, then auto-fixes if no response within the timeout period. It runs locally on the Mac, polling the VPS state every 30 seconds.

**Key Design Decisions:**
- Notify user first, auto-fix after timeout (15 min)
- Monitor `intra_epoch_state.json` (primary) with fallback to `trading_state.json`
- Auto-escalate after 2 consecutive auto-fixes for same issue type (loop detection)
- Full monitoring with configurable alert rules (not just halts)
- `/auto-manage` runs manual diagnostic by default

## Goals

- Detect bot halts within 30 seconds of occurrence
- Notify user via Telegram with diagnostic summary and recommended action
- Auto-fix safe issues if user doesn't respond within 15 minutes
- Detect and prevent fix loops (escalate after 2 consecutive fixes)
- Support configurable alerts beyond halts (balance, win rate, etc.)
- Provide `/auto-manage` skill for manual diagnostics and control
- Maintain full audit trail of all actions taken

## User Stories

### US-001: Create Sentinel directory structure and configuration
**Description:** As a developer, I need the foundational directory structure and configuration file so other components have a place to store state and read settings.

**Acceptance Criteria:**
- [x] Create `sentinel/` directory with subdirectories: `events/`, `history/`, `state/`
- [x] Create `sentinel/sentinel_config.json` with settings:
  - polling.interval_seconds: 30
  - polling.ssh_timeout_seconds: 10
  - rate_limits.max_auto_fixes_per_hour: 3
  - rate_limits.consecutive_fix_limit: 2
  - safety.balance_floor: 50.0
  - safety.min_confidence_for_auto_fix: 70
  - escalation.telegram_timeout_seconds: 900
  - vps.host: "root@216.238.85.11"
  - vps.ssh_key: "~/.ssh/polymarket_vultr"
  - vps.state_files: ["/opt/polymarket-autotrader/state/intra_epoch_state.json", "/opt/polymarket-autotrader/state/trading_state.json"]
  - vps.log_file: "/opt/polymarket-autotrader/bot.log"
  - alerts (configurable rules array - empty for now)
- [x] Create empty `sentinel/events/queue.json` initialized as `[]`
- [x] Create empty `sentinel/history/actions.log`
- [x] Create `sentinel/state/.gitkeep` (state files are gitignored)
- [x] Add `sentinel/state/` to .gitignore
- [x] Typecheck passes (N/A - config files only)

---

### US-002: Create sentinel_monitor.sh polling daemon
**Description:** As a user, I want a background daemon that polls the VPS state every 30 seconds so halt events are detected automatically.

**Acceptance Criteria:**
- [x] Create `sentinel/sentinel_monitor.sh` with start/stop/status commands
- [x] `start` command runs polling loop in background, writes PID to `state/monitor.pid`
- [x] `stop` command kills the process using stored PID
- [x] `status` command shows if running and last poll time
- [x] Polling loop SSHs to VPS, reads state file, compares mode to last known state
- [x] On halt transition (mode changed TO "halted"), writes event to `events/queue.json`
- [x] Respects kill switch: skips processing if `state/KILL_SWITCH` file exists
- [x] Logs activity to `state/monitor.log`
- [x] Script is executable (chmod +x)
- [x] Test: `./sentinel_monitor.sh status` runs without error

---

### US-003: Create sentinel_diagnose.md Claude prompt template
**Description:** As a developer, I need a well-structured prompt template that guides Claude's diagnostic analysis so decisions are consistent and well-reasoned.

**Acceptance Criteria:**
- [x] Create `sentinel/sentinel_diagnose.md` with sections:
  - Context: Role as Sentinel monitoring system
  - Decision Types: `auto_fix` vs `escalate`
  - Available Actions: `reset_peak_balance`, `resume_trading`, `reset_loss_streak`, `restart_bot`
  - Decision Criteria: When to auto-fix vs escalate (with specific conditions)
  - Output Format: JSON block with decision, action, reason, confidence, analysis
- [x] Include rule: Always escalate if balance < $50
- [x] Include rule: Always escalate manual halts
- [x] Include rule: Escalate if confidence < 70%
- [x] Include examples of good diagnostic reasoning
- [x] Typecheck passes (N/A - markdown file)

---

### US-004: Create sentinel.sh main orchestrator
**Description:** As a user, I want the main orchestrator script that processes halt events, invokes Claude for diagnosis, and executes the appropriate action.

**Acceptance Criteria:**
- [x] Create `sentinel/sentinel.sh` that processes events from queue
- [x] Loads configuration from `sentinel_config.json`
- [x] For each pending event:
  - Gathers diagnostics via SSH (state file, recent logs, on-chain balance)
  - Invokes Claude Code with `--dangerously-skip-permissions` using diagnose prompt
  - Parses JSON decision from Claude's output
- [x] Implements safety checks before any action:
  - Kill switch check
  - Balance floor check ($50)
  - Rate limit check (max 3/hour)
  - Consecutive fix check (max 2 for same issue type)
- [x] Logs all actions to `history/actions.log` with timestamp
- [x] Updates event status in queue after processing
- [x] Script is executable (chmod +x)
- [x] Test: `./sentinel.sh` runs without error when queue is empty

---

### US-005: Implement Telegram notification for halt events
**Description:** As a user, I want to receive a Telegram message when a halt is detected so I can review the situation and respond.

**Acceptance Criteria:**
- [x] sentinel.sh sends Telegram message on halt detection (before any auto-fix)
- [x] Message format includes:
  - Emoji alert header (🚨 SENTINEL ALERT)
  - Halt reason
  - Current balance and drawdown
  - Claude's analysis summary
  - Response options: /approve, /deny, /custom
  - Timeout warning (15 min)
- [x] Uses existing `bot/telegram_handler.py` infrastructure (via SSH to VPS)
- [x] Message sent synchronously to confirm delivery before starting timeout
- [x] Test: Manually trigger and verify Telegram message received

---

### US-006: Add get_recent_commands method to telegram_handler.py
**Description:** As a developer, I need a method to poll Telegram for recent command responses so Sentinel can detect user approvals/denials.

**Acceptance Criteria:**
- [x] Add `get_recent_commands(self, since_minutes: int = 5) -> list[str]` method to TelegramBot class
- [x] Method calls Telegram getUpdates API with offset=-10
- [x] Filters to commands (start with /) from authorized chat_id within time window
- [x] Returns list of command strings (e.g., ["/approve", "/deny reason"])
- [x] Handles API errors gracefully (returns empty list)
- [x] Add required imports: `datetime`, `timedelta`
- [x] Typecheck passes

---

### US-007: Implement Telegram response polling in sentinel.sh
**Description:** As a user, I want Sentinel to wait for my Telegram response before auto-fixing so I have control over the action taken.

**Acceptance Criteria:**
- [x] After sending notification, sentinel.sh polls Telegram for response
- [x] Polls every 10 seconds for up to 15 minutes (configurable)
- [x] Recognizes commands: /approve, /deny, /custom <action>
- [x] On /approve: Execute recommended action, notify user of completion
- [x] On /deny: Log denial, leave bot halted, notify user
- [x] On /custom: Log custom request, attempt to parse and execute if safe
- [x] On timeout: Execute auto-fix if confidence >= 70%, otherwise leave halted
- [x] Send confirmation message after any action taken
- [x] Test: Verify polling works with manual /approve command

---

### US-008: Implement auto-fix execution functions
**Description:** As a developer, I need functions that execute specific fix actions on the VPS so Sentinel can resolve issues.

**Acceptance Criteria:**
- [x] Implement `execute_fix()` function in sentinel.sh that handles:
  - `reset_peak_balance`: SSH to VPS, update state file peak_balance = current_balance, set mode = "normal"
  - `resume_trading`: SSH to VPS, set mode = "normal", clear halt_reason
  - `reset_loss_streak`: SSH to VPS, set consecutive_losses = 0, set mode = "normal"
  - `restart_bot`: SSH to VPS, run `systemctl restart polymarket-bot`
- [x] Each fix updates state file atomically (read, modify, write)
- [x] Returns success/failure status
- [x] Logs fix attempt and result to history
- [x] Test: Manually call each fix type and verify VPS state changes

---

### US-009: Implement consecutive fix loop detection
**Description:** As a user, I want Sentinel to detect when it's stuck in a fix loop so it escalates instead of repeatedly auto-fixing.

**Acceptance Criteria:**
- [x] Track recent fixes in `state/recent_fixes.json` with timestamp and issue_type
- [x] Before auto-fixing, check if same issue_type was fixed in last 30 minutes
- [x] If 2+ fixes for same issue in 30 min window, escalate instead of auto-fix
- [x] Escalation message indicates loop detected and manual intervention needed
- [x] Clear fix history for issue_type when user manually approves/denies
- [x] Test: Simulate 2 consecutive halts with same reason, verify escalation

---

### US-010: Implement configurable alert rules system
**Description:** As a user, I want to configure custom alerts (not just halts) so I'm notified of important conditions like low balance or dropping win rate.

**Acceptance Criteria:**
- [x] Add `alerts` array to sentinel_config.json with rule structure:
  - name: string (e.g., "low_balance")
  - condition: string (e.g., "balance < 75")
  - severity: "info" | "warning" | "critical"
  - cooldown_minutes: number (prevent spam)
- [x] sentinel_monitor.sh evaluates alert rules on each poll
- [x] Triggered alerts send Telegram notification with severity-appropriate emoji
- [x] Track last trigger time per alert in `state/alert_cooldowns.json`
- [x] Add default alerts:
  - low_balance: balance < 75 (warning)
  - critical_balance: balance < 30 (critical)
  - high_drawdown: drawdown > 25% (warning)
  - losing_streak: consecutive_losses >= 3 (warning)
- [x] Test: Set balance threshold high, verify alert triggers

---

### US-011: Create /auto-manage skill definition
**Description:** As a user, I want a `/auto-manage` skill so I can manually interact with Sentinel from Claude Code.

**Acceptance Criteria:**
- [x] Create `.claude/commands/auto-manage.md` skill file
- [x] Default behavior (no args): Run manual diagnostic
  - SSH to VPS, gather current state
  - Invoke Claude analysis
  - Report findings without taking action
- [x] Support subcommands:
  - `status`: Show monitor status, last poll, pending events
  - `start`: Start the monitor daemon
  - `stop`: Stop the monitor daemon
  - `history`: Show last 20 actions from actions.log
  - `config`: Display current configuration
- [x] Include safety information (kill switch location, rate limits)
- [x] Typecheck passes (N/A - markdown file)

---

### US-012: Implement /auto-manage skill execution logic
**Description:** As a user, I want the /auto-manage skill to actually execute the commands when invoked.

**Acceptance Criteria:**
- [x] Skill reads command argument and routes to appropriate action
- [x] `status` subcommand outputs:
  - Monitor running/stopped (check PID file)
  - Last state from `state/last_state.json`
  - Pending events count from queue
  - Rate limit usage (X/3 this hour)
- [x] `start` subcommand calls `./sentinel/sentinel_monitor.sh start`
- [x] `stop` subcommand calls `./sentinel/sentinel_monitor.sh stop`
- [x] `history` subcommand reads and displays `history/actions.log`
- [x] `config` subcommand displays `sentinel_config.json` formatted
- [x] Default (diagnose) gathers state and runs Claude analysis inline
- [x] Test: Run `/auto-manage status` and verify output

---

### US-013: Add auto-fix notification with undo option
**Description:** As a user, I want to be notified when Sentinel auto-fixes an issue (after timeout) so I know what happened and can undo if needed.

**Acceptance Criteria:**
- [x] After auto-fix executes (due to timeout), send Telegram notification
- [x] Message format:
  - ✅ SENTINEL AUTO-FIX header
  - Action taken
  - Reason and confidence level
  - "Reply /halt to stop if needed"
- [x] Include timestamp in message
- [x] Log auto-fix with "timeout_auto_fix" flag in history
- [x] Test: Let timeout expire, verify notification sent

---

### US-014: Add comprehensive error handling to sentinel scripts
**Description:** As a developer, I need robust error handling so Sentinel doesn't crash or leave the system in a bad state.

**Acceptance Criteria:**
- [x] sentinel_monitor.sh handles SSH connection failures gracefully (log and retry)
- [x] sentinel.sh handles Claude invocation failures (escalate to user)
- [x] Handle malformed JSON in state files (log error, skip processing)
- [x] Handle Telegram API failures (retry 3 times, then log and continue)
- [x] All errors logged to `state/error.log` with stack trace
- [x] Critical errors also sent to Telegram if possible
- [x] Add `set -e` with trap for cleanup on script exit
- [x] Test: Simulate SSH failure, verify graceful handling

---

### US-015: Add monitor health check and self-recovery
**Description:** As a user, I want the monitor to detect if it's unhealthy and attempt self-recovery so it stays running reliably.

**Acceptance Criteria:**
- [x] Monitor writes heartbeat timestamp to `state/heartbeat` on each poll
- [x] Add `health` subcommand to sentinel_monitor.sh
- [x] Health check verifies:
  - Heartbeat within last 2 minutes
  - No repeated SSH failures (>5 consecutive)
  - PID file matches running process
- [x] If unhealthy, attempt restart (stop then start)
- [x] Send Telegram alert if self-recovery fails
- [x] Test: Kill monitor process, verify health check detects it

---

### US-016: Write integration test script
**Description:** As a developer, I need an integration test script to verify Sentinel works end-to-end before relying on it in production.

**Acceptance Criteria:**
- [x] Create `sentinel/test_sentinel.sh` script
- [x] Tests include:
  - Directory structure exists
  - Config file is valid JSON
  - Monitor starts and stops correctly
  - Can SSH to VPS and read state
  - Can send Telegram message
  - Can invoke Claude Code
  - Event queue operations work
  - History logging works
- [x] Each test outputs PASS/FAIL with description
- [x] Final summary shows total passed/failed
- [x] Script is executable (chmod +x)
- [x] Test: Run `./sentinel/test_sentinel.sh` and verify all pass

---

### US-017: Update CLAUDE.md with Sentinel documentation
**Description:** As a user, I want Sentinel documented in CLAUDE.md so future Claude sessions understand how to use and maintain it.

**Acceptance Criteria:**
- [x] Add "Sentinel Monitoring System" section to CLAUDE.md
- [x] Document:
  - Purpose and architecture overview
  - How to start/stop the monitor
  - How to use /auto-manage skill
  - Configuration options
  - Safety guardrails (kill switch, rate limits)
  - Troubleshooting common issues
- [x] Include example Telegram message formats
- [x] Include example commands and expected output
- [x] Typecheck passes (N/A - markdown file)

---

## Non-Goals

- **VPS-based Sentinel:** System runs locally only, not on VPS (requires Mac to be on)
- **Web dashboard:** No web UI, Telegram is the only interface
- **Historical analytics:** No performance charts or trend analysis (just event logging)
- **Multi-bot support:** Only monitors single bot instance
- **Automated strategy changes:** Sentinel fixes operational issues, not trading strategy
- **Real-time log streaming:** Uses polling, not continuous log tail

## Technical Considerations

- **SSH Key:** Uses `~/.ssh/polymarket_vultr` for VPS access
- **Claude Code:** Invoked with `--dangerously-skip-permissions` flag (like ralph.sh)
- **Telegram:** Reuses existing `bot/telegram_handler.py` infrastructure
- **State Files:** Primary is `intra_epoch_state.json`, fallback to `trading_state.json`
- **JSON Parsing:** Uses `jq` for bash JSON operations
- **Concurrency:** Only one sentinel.sh instance runs at a time (use lock file)

## Dependencies

- `jq` - JSON parsing in bash (already installed on Mac)
- `ssh` - VPS access (already configured)
- Claude Code CLI - For AI analysis
- Telegram Bot - Already configured with token and chat_id
