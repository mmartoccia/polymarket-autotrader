# PRD: Optimizer - Hourly Performance Review & Auto-Tuning System

## Introduction

Optimizer is an automated hourly performance review system that runs on the VPS alongside the trading bot. It analyzes recent trading activity, identifies issues (inactivity or poor performance), and auto-adjusts configuration parameters to optimize profit.

**Key Design Decisions:**
- Runs on VPS via cron (hourly)
- Auto-adjusts parameters within safe bounds (aggressive mode)
- Alerts on both: zero trades in 2+ hours OR win rate drops below 50%
- Direct access to logs, state files, and SQLite database
- Never touches safety-critical parameters (drawdown, position sizing)

## Goals

- Detect trading inactivity (0 trades in 2+ hours) and diagnose causes
- Detect performance degradation (win rate < 50% over last 10 trades)
- Analyze skip reasons to identify which filters are blocking trades
- Auto-tune parameters within safe bounds to optimize trade flow
- Send Telegram reports (silent for healthy, alert for issues)
- Maintain full audit trail of all parameter adjustments

## User Stories

### US-OPT-001: Create optimizer directory structure and configuration
**Description:** As a developer, I need the foundational directory structure and configuration file so other components have a place to store state and read settings.

**Acceptance Criteria:**
- [x] Create `optimizer/` directory with subdirectories: `history/`, `state/`
- [x] Create `optimizer/optimizer_config.json` with settings:
  - review_interval_hours: 1
  - lookback_hours: 2
  - alert_thresholds.no_trades_hours: 2
  - alert_thresholds.min_win_rate: 0.50
  - alert_thresholds.min_trades_for_win_rate: 10
  - alert_thresholds.max_skip_rate: 0.90
  - tunable_parameters with bounds for: MAX_ENTRY_PRICE_CAP, MIN_PATTERN_ACCURACY, CONSENSUS_THRESHOLD, MIN_CONFIDENCE, EDGE_BUFFER
  - protected_parameters: ["RISK_MAX_DRAWDOWN", "RISK_DAILY_LOSS_LIMIT", "RISK_POSITION_TIERS"]
- [x] Create empty `optimizer/history/adjustments.txt`
- [x] Create `optimizer/state/.gitkeep` (state files are gitignored)
- [x] Add `optimizer/state/` to .gitignore
- [x] Typecheck passes (N/A - config files only)

---

### US-OPT-002: Implement data collection module
**Description:** As a developer, I need functions to collect trading data from logs, database, and state files.

**Acceptance Criteria:**
- [x] Create `optimizer/data_collector.py`
- [x] Implement `collect_trades(hours: int) -> list[dict]` - get trades from SQLite `simulation/trade_journal.db`
- [x] Implement `collect_skips(hours: int) -> list[dict]` - get skip decisions from SQLite decisions table
- [x] Implement `collect_vetoes(hours: int) -> list[str]` - parse VETO lines from `bot.log`
- [x] Implement `get_current_state() -> dict` - read `state/intra_epoch_state.json`
- [x] Handle missing files/tables gracefully (return empty results)
- [x] Typecheck passes

---

### US-OPT-003: Implement analysis engine
**Description:** As a developer, I need to analyze collected data to identify issues and opportunities.

**Acceptance Criteria:**
- [x] Create `optimizer/analyzer.py`
- [x] Implement `analyze_trade_performance(trades: list) -> dict` with:
  - total_trades, wins, losses, win_rate, total_pnl
- [x] Implement `analyze_skip_distribution(skips: list) -> dict` with:
  - skip reasons grouped by type with counts and percentages
- [x] Implement `analyze_veto_patterns(vetoes: list) -> dict` with:
  - veto reasons grouped with frequency
- [x] Implement `diagnose_inactivity(skips: list, vetoes: list) -> str` that determines primary cause
- [x] Returns structured analysis dict with findings
- [x] Typecheck passes

---

### US-OPT-004: Implement tuning rules engine
**Description:** As a developer, I need decision logic that maps analysis findings to parameter adjustments.

**Acceptance Criteria:**
- [x] Create `optimizer/tuning_rules.py`
- [x] Define `TuningRule` dataclass with: name, condition_fn, parameter, direction (increase/decrease), step
- [x] Implement rules:
  - `too_few_trades_entry_price`: If >40% skips are SKIP_ENTRY_PRICE, increase MAX_ENTRY_PRICE_CAP
  - `too_few_trades_weak_pattern`: If >40% skips are SKIP_WEAK, decrease MIN_PATTERN_ACCURACY
  - `too_few_trades_consensus`: If >40% skips are consensus-related, decrease CONSENSUS_THRESHOLD
  - `poor_win_rate_tighten`: If win_rate < 0.50, increase MIN_PATTERN_ACCURACY and CONSENSUS_THRESHOLD
- [x] Implement `select_tunings(analysis: dict, config: dict) -> list[dict]` returns list of adjustments
- [x] Each adjustment includes: parameter, old_value, new_value, reason
- [x] Bounds checking enforced (min/max from config)
- [x] Never adjust protected_parameters
- [x] Typecheck passes

---

### US-OPT-005: Implement parameter adjustment executor
**Description:** As a developer, I need to safely apply parameter changes to config files.

**Acceptance Criteria:**
- [ ] Create `optimizer/executor.py`
- [ ] Implement `apply_adjustment(param: str, old_value: float, new_value: float, config: dict) -> bool`
- [ ] Reads target file (bot/intra_epoch_bot.py or config/agent_config.py based on config)
- [ ] Creates backup before modification (.bak file)
- [ ] Uses regex to find and replace parameter value
- [ ] Logs change to `history/adjustments.log` with timestamp, param, old, new, reason
- [ ] Updates `state/parameter_history.json` with change record
- [ ] Returns True on success, False on failure
- [ ] Typecheck passes

---

### US-OPT-006: Implement Telegram reporting
**Description:** As a developer, I need to send hourly reports and alerts via Telegram.

**Acceptance Criteria:**
- [ ] Create `optimizer/reporter.py`
- [ ] Implement `send_hourly_report(analysis: dict, adjustments: list, silent: bool = True)`
- [ ] Report format includes:
  - Period (last hour)
  - Trades summary (count, W/L, win rate)
  - Balance change
  - Skip analysis (top 3 reasons with percentages)
  - Status (Healthy/Alert)
  - Adjustments made (if any)
- [ ] Silent reports use `disable_notification=True` in Telegram API
- [ ] Alert reports (issues detected) use notification sound
- [ ] Uses existing `bot/telegram_handler.py` TelegramBot class
- [ ] Handles Telegram API errors gracefully
- [ ] Typecheck passes

---

### US-OPT-007: Create main optimizer.py orchestrator
**Description:** As a developer, I need the main script that ties everything together, run by cron.

**Acceptance Criteria:**
- [ ] Create `optimizer/optimizer.py` as main entry point
- [ ] Loads config from `optimizer_config.json`
- [ ] Collects data for last 1-2 hours using data_collector
- [ ] Runs analysis using analyzer
- [ ] Applies tuning rules using tuning_rules
- [ ] Executes adjustments using executor (if any)
- [ ] Sends Telegram report using reporter
- [ ] Saves review results to `state/last_review.json`
- [ ] Implements `--dry-run` flag to test without applying changes
- [ ] Implements rate limiting (max 1 adjustment per parameter per hour)
- [ ] Handles errors gracefully with logging
- [ ] Typecheck passes
- [ ] Test: `python3 optimizer/optimizer.py --dry-run` runs without error

---

### US-OPT-008: Set up cron job on VPS
**Description:** As a user, I need hourly execution via cron on the VPS.

**Acceptance Criteria:**
- [ ] Create `optimizer/install_cron.sh` script that:
  - Adds cron entry: `0 * * * * cd /opt/polymarket-autotrader && /opt/polymarket-autotrader/venv/bin/python3 optimizer/optimizer.py >> optimizer/cron.log 2>&1`
  - Sets proper permissions
- [ ] Create `optimizer/uninstall_cron.sh` to remove the cron entry
- [ ] Document cron setup in script comments
- [ ] Test: Verify cron job appears in `crontab -l` after install
- [ ] Test: Wait for next hour and verify optimizer ran (check cron.log)

---

### US-OPT-009: Add /optimizer-status skill
**Description:** As a user, I want a Claude Code skill to check optimizer status and history.

**Acceptance Criteria:**
- [ ] Create `.claude/commands/optimizer-status.md` skill file
- [ ] Default behavior: Show last review results and current parameter values
- [ ] Support subcommands:
  - `history`: Show last 20 adjustments from adjustments.log
  - `bounds`: Display current tuning bounds from config
  - `run`: Manually trigger optimizer (dry-run by default)
  - `run --apply`: Manually trigger with changes applied
- [ ] Include current parameter values for all tunable params
- [ ] Typecheck passes (N/A - markdown file)

---

### US-OPT-010: Write integration tests
**Description:** As a developer, I need tests to verify the optimizer works correctly.

**Acceptance Criteria:**
- [ ] Create `optimizer/test_optimizer.py`
- [ ] Tests include:
  - Data collection returns expected format
  - Analysis calculations are correct
  - Tuning rules fire on correct conditions
  - Bounds are respected (never exceed min/max)
  - Protected parameters are never modified
  - Dry-run mode doesn't modify files
- [ ] All tests pass
- [ ] Typecheck passes

---

### US-OPT-011: Update CLAUDE.md with Optimizer documentation
**Description:** As a user, I want Optimizer documented in CLAUDE.md so future Claude sessions understand how to use and maintain it.

**Acceptance Criteria:**
- [ ] Add "Optimizer System" section to CLAUDE.md
- [ ] Document:
  - Purpose and architecture overview
  - How it runs (cron hourly on VPS)
  - Tunable parameters and their bounds
  - Protected parameters (never auto-adjusted)
  - How to use /optimizer-status skill
  - How to view adjustment history
  - How to manually trigger
- [ ] Include example Telegram report format
- [ ] Include example adjustment log entry
- [ ] Typecheck passes (N/A - markdown file)

---

## Non-Goals

- **Strategy changes:** Optimizer adjusts filters/thresholds, not trading strategy
- **Real-time adjustment:** Runs hourly via cron, not continuously
- **Position sizing:** Never auto-adjusts risk/position parameters
- **Drawdown limits:** Never auto-adjusts safety-critical parameters
- **Agent enable/disable:** Strategic decisions require manual approval
- **ML model retraining:** Out of scope for this system

## Technical Considerations

- **Location:** Runs on VPS (direct file access, no SSH needed)
- **Database:** Uses existing `analysis/epoch_history.db` SQLite database
- **Config files:** Modifies `bot/intra_epoch_bot.py` and `config/agent_config.py`
- **Backups:** Creates .bak files before any modification
- **Rate limiting:** Max 1 change per parameter per hour
- **Telegram:** Uses existing `bot/telegram_handler.py`

## Tunable Parameters

| Parameter | File | Current | Min | Max | Step |
|-----------|------|---------|-----|-----|------|
| MAX_ENTRY_PRICE_CAP | bot/intra_epoch_bot.py | 0.50 | 0.35 | 0.65 | 0.05 |
| MIN_PATTERN_ACCURACY | bot/intra_epoch_bot.py | 0.735 | 0.65 | 0.80 | 0.01 |
| CONSENSUS_THRESHOLD | config/agent_config.py | 0.40 | 0.30 | 0.55 | 0.05 |
| MIN_CONFIDENCE | config/agent_config.py | 0.50 | 0.35 | 0.65 | 0.05 |
| EDGE_BUFFER | bot/intra_epoch_bot.py | 0.05 | 0.02 | 0.10 | 0.01 |

## Protected Parameters (Never Auto-Adjusted)

- RISK_MAX_DRAWDOWN
- RISK_DAILY_LOSS_LIMIT
- RISK_POSITION_TIERS
- Agent enable/disable flags

## Dependencies

- Python 3.11+
- SQLite3 (for epoch_history.db)
- requests (for Telegram API)
- Existing bot/telegram_handler.py
- Existing analysis/epoch_history.db
