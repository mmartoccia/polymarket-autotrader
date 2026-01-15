# PRD: Week 1 - Per-Agent Performance Tracking

## Introduction

Implement per-agent performance tracking to identify which of the 7 deployed agents (Tech, Sentiment, Regime, Candlestick, TimePattern, OrderBook, FundingRate) contribute positively vs negatively to overall win rate. This enables data-driven decisions to disable underperforming agents and improve win rate by 2-3%.

**Strategic Context:** See `PRD-strategic.md` for 4-week optimization roadmap.

## Goals

- Track individual agent vote accuracy (win rate per agent)
- Identify underperforming agents (<50% win rate with 20+ votes)
- Enable/disable agents based on performance data
- Improve overall win rate by 2-3% by removing low-performers

## User Stories

### US-001: Database schema for agent performance tracking
**Description:** As a developer, I need database tables to store agent performance metrics so the system can track win rates per agent over time.

**Acceptance Criteria:**
- [x] Add `agent_performance` table to `simulation/trade_journal.py`
- [x] Table columns: agent_name, total_votes, correct_votes, incorrect_votes, win_rate, avg_confidence, last_updated
- [x] Add `agent_votes_outcomes` table to link agent votes to trade outcomes
- [x] Table columns: vote_id, agent_vote_id, outcome_id, was_correct, created_at
- [x] Foreign keys properly defined
- [x] Typecheck passes

**Status:** ✅ COMPLETE (Jan 15, 2026)

---

### US-002: Agent performance tracker module
**Description:** As a developer, I need a tool to analyze agent performance so I can identify which agents help vs hurt win rate.

**Acceptance Criteria:**
- [x] Create `analytics/agent_performance_tracker.py`
- [x] Implement `update_agent_outcomes()` to match votes to outcomes
- [x] Implement `calculate_agent_performance()` to compute win rates
- [x] Implement `get_underperforming_agents(threshold, min_votes)`
- [x] Implement `print_agent_report()` for CLI output
- [x] Can run standalone: `python3 analytics/agent_performance_tracker.py`
- [x] Typecheck passes

**Status:** ✅ COMPLETE (Jan 15, 2026)

---

### US-003: Agent enable/disable configuration
**Description:** As a developer, I need flags to enable/disable specific agents so I can turn off underperformers without code changes.

**Acceptance Criteria:**
- [x] Add `AGENT_ENABLED` dict to `config/agent_config.py`
- [x] Dict maps agent name to boolean (True = enabled, False = disabled)
- [x] Add `get_enabled_agents()` helper function
- [x] Document usage with comments
- [x] Default: 7 agents enabled, 2 disabled (OnChain, Social - no API keys)
- [x] Typecheck passes

**Status:** ✅ COMPLETE (Jan 15, 2026)

---

### US-004: Integrate agent flags into bot initialization
**Description:** As a bot operator, I need the bot to respect AGENT_ENABLED flags so disabled agents don't participate in decisions.

**Acceptance Criteria:**
- [x] Import `get_enabled_agents()` in `bot/momentum_bot_v12.py`
- [x] Log enabled agents on startup
- [x] Filter agent initialization based on AGENT_ENABLED flags
- [x] Verify disabled agents (OnChain, Social) are NOT initialized
- [x] Verify agent votes only come from enabled agents
- [x] Typecheck passes
- [ ] Test on VPS with logs showing enabled agents list

**Status:** ✅ COMPLETE (Jan 15, 2026)

---

### US-005: Wait for 100+ trades and analyze performance
**Description:** As a data analyst, I need to analyze agent performance after sufficient data collection so I can make statistically valid decisions.

**Acceptance Criteria:**
- [ ] Wait until `agent_performance` table has 100+ votes per agent
- [ ] Run `python3 analytics/agent_performance_tracker.py`
- [ ] Identify agents with win rate <50% and 20+ votes
- [ ] Document findings in `progress.txt`
- [ ] If underperformers found: Update `AGENT_ENABLED` to disable them
- [ ] If no underperformers: Document that all agents performing well
- [ ] Measure win rate change before/after disabling (target: +2-3%)

**Status:** ⏳ BLOCKED (waiting for data)

**Dependencies:**
- Requires US-004 complete
- Requires bot running for ~100+ trades (~2-3 days at 15-20 trades/day)

---

## Non-Goals

- No new agents added (focus on optimizing existing 7)
- No changes to agent voting logic (just tracking + enable/disable)
- No real-time agent performance updates during trading (analyzed post-mortem)
- No automated agent disabling (manual review required)

## Technical Considerations

**Database:**
- Schema changes backward compatible (new tables, no alterations)
- SQLite handles concurrent reads/writes with WAL mode

**Analysis Requirements:**
- Minimum 20 votes per agent for statistical significance
- Chi-square test (p<0.05) recommended before disabling agents
- Track win rate in 20-trade rolling window for early detection

**Bot Integration:**
- Agent filtering happens at initialization (not per-decision)
- Disabled agents consume zero resources (not instantiated)
- Can enable/disable via config without code changes

---

## Week 2: Selective Trading Enhancement

### US-006: Create ultra_selective shadow strategy
**Description:** As a strategy designer, I need a shadow strategy with higher thresholds so I can test if fewer, higher-quality trades improve win rate.

**Acceptance Criteria:**
- [ ] Add `ultra_selective` to `simulation/strategy_configs.py` STRATEGY_LIBRARY
- [ ] Set consensus_threshold=0.80 (increased from 0.75)
- [ ] Set min_confidence=0.70 (increased from 0.60)
- [ ] Set min_viable_threshold=0.70 (increased from 0.40)
- [ ] Keep adaptive_weights=True
- [ ] Copy agent_weights from default strategy
- [ ] Add strategy to SHADOW_STRATEGIES list in `config/agent_config.py`
- [ ] Typecheck passes

**Status:** ⏳ PENDING

---

### US-007: Verify ultra_selective shadow testing
**Description:** As a QA engineer, I need to verify the shadow strategy is running so I know data is being collected correctly.

**Acceptance Criteria:**
- [ ] Restart bot (systemctl restart polymarket-bot on VPS)
- [ ] Check logs show: "Shadow Trading: [X] strategies" (includes ultra_selective)
- [ ] Run `python3 simulation/dashboard.py` - shows ultra_selective in list
- [ ] Query database: `SELECT COUNT(*) FROM trades WHERE strategy='ultra_selective'` returns >0 after 24h
- [ ] Verify ultra_selective makes fewer trades than default (target: 50% fewer)

**Status:** ⏳ PENDING

**Dependencies:** Requires US-006 complete

---

### US-008: Compare ultra_selective vs default performance
**Description:** As a data analyst, I need to statistically validate ultra_selective performance so I can decide if it should replace default.

**Acceptance Criteria:**
- [ ] Wait for 100+ trades from both strategies
- [ ] Run `python3 simulation/analyze.py compare --strategies default,ultra_selective`
- [ ] Calculate metrics: win rate, trades/day, Sharpe ratio, max drawdown
- [ ] Run chi-square test (p<0.05 for significance)
- [ ] Document results in `progress.txt` with comparison table
- [ ] Validation criteria: win_rate ≥65%, Sharpe ≥1.5, drawdown ≤20%

**Status:** ⏳ BLOCKED (waiting for data)

**Dependencies:**
- Requires US-007 complete
- Requires ~7-10 days for 100+ trades at reduced frequency

---

### US-009: Promote ultra_selective if validated (staged rollout)
**Description:** As a bot operator, I need to gradually promote ultra_selective so I can roll back if problems arise.

**Acceptance Criteria:**
- [ ] ONLY if US-008 validation passes (win_rate ≥65%, Sharpe ≥1.5)
- [ ] Update `config/agent_config.py`: Set LIVE_STRATEGY = 'ultra_selective'
- [ ] Set LIVE_STRATEGY_ALLOCATION = 0.25 (25% of trades)
- [ ] Monitor for 50 trades (2-3 days)
- [ ] If still outperforming: Increase to 0.50 (50%)
- [ ] Monitor for 50 more trades
- [ ] If still outperforming: Increase to 1.00 (100%)
- [ ] Document rollout in `progress.txt`
- [ ] Auto-rollback plan: If win rate drops below 50%, revert to default

**Status:** ⏳ BLOCKED (pending US-008 validation)

---

## Week 3: Kelly Criterion Position Sizing

### US-010: Create position_sizer module with Kelly logic
**Description:** As a developer, I need a Kelly Criterion position sizer so the bot can calculate mathematically optimal bet sizes.

**Acceptance Criteria:**
- [ ] Create `bot/position_sizer.py`
- [ ] Implement `KellyPositionSizer` class
- [ ] Implement `calculate_kelly_size(win_prob, entry_price, balance, min_size_pct, max_size_pct)`
- [ ] Kelly formula: f* = (p*b - q) / b where b = (1 - entry_price) / entry_price
- [ ] Apply fractional Kelly (25% of full Kelly for safety)
- [ ] Clamp to min/max range (2% - 15% of balance)
- [ ] Return tuple: (position_size_usd, debug_info_dict)
- [ ] Implement `compare_with_fixed_tiers()` for analysis
- [ ] Add example usage in `if __name__ == "__main__"` block
- [ ] Typecheck passes
- [ ] Test: `python3 bot/position_sizer.py` shows example calculations

**Status:** ⏳ PENDING

---

### US-011: Create kelly_sizing shadow strategy
**Description:** As a strategy designer, I need a shadow strategy using Kelly sizing so I can compare it to fixed tiers.

**Acceptance Criteria:**
- [ ] Add `kelly_sizing` to `simulation/strategy_configs.py` STRATEGY_LIBRARY
- [ ] Copy thresholds from default (0.75 consensus, 0.60 confidence)
- [ ] Add special flag: `use_kelly_sizing=True`
- [ ] Add to SHADOW_STRATEGIES list in `config/agent_config.py`
- [ ] Typecheck passes

**Status:** ⏳ PENDING

**Dependencies:** Requires US-010 complete

---

### US-012: Integrate Kelly sizing into shadow system
**Description:** As a developer, I need shadow strategies to use Kelly sizing when configured so I can test it with virtual money.

**Acceptance Criteria:**
- [ ] Modify `simulation/shadow_strategy.py` execute_trade() method
- [ ] Check if `self.config.use_kelly_sizing` is True
- [ ] If True: Import KellyPositionSizer, use confidence as win_prob
- [ ] If False: Use existing fixed tier sizing
- [ ] Log Kelly sizing calculations (debug level)
- [ ] Verify kelly_sizing strategy appears in `python3 simulation/dashboard.py`
- [ ] Verify kelly_sizing uses variable position sizes (not fixed)
- [ ] Typecheck passes

**Status:** ⏳ PENDING

**Dependencies:** Requires US-011 complete

---

### US-013: Compare kelly_sizing vs fixed tiers performance
**Description:** As a data analyst, I need to validate Kelly sizing performance so I can decide if it improves ROI.

**Acceptance Criteria:**
- [ ] Wait for 100+ trades from both strategies
- [ ] Run `python3 simulation/analyze.py compare --strategies default,kelly_sizing`
- [ ] Calculate: ROI, Sharpe ratio, max drawdown, average position size
- [ ] Validation criteria: ROI 20-30% higher, Sharpe ≥1.2, drawdown ≤25% (same as fixed)
- [ ] Document results with comparison table in `progress.txt`
- [ ] Include position size distribution analysis

**Status:** ⏳ BLOCKED (waiting for data)

**Dependencies:**
- Requires US-012 complete
- Requires ~7-10 days for 100+ trades

---

### US-014: Integrate Kelly sizing into live bot if validated
**Description:** As a bot operator, I need Kelly sizing in the live bot so I can improve ROI without increasing risk.

**Acceptance Criteria:**
- [ ] ONLY if US-013 validation passes (ROI +20-30%, Sharpe ≥1.2, drawdown ≤25%)
- [ ] Modify `bot/momentum_bot_v12.py` Guardian.calculate_position_size()
- [ ] Import KellyPositionSizer at top of file
- [ ] Add config flag: `USE_KELLY_SIZING = True` in constants
- [ ] Replace fixed tier logic with Kelly calculation
- [ ] Use ML confidence as win_prob input
- [ ] Log Kelly sizing details on each trade
- [ ] Test locally with small balance before VPS deployment
- [ ] Typecheck passes
- [ ] Deploy to VPS with monitoring

**Status:** ⏳ BLOCKED (pending US-013 validation)

---

## Week 4: Automated Optimization Infrastructure

### US-015: Create auto_promoter module
**Description:** As a developer, I need an auto-promoter that identifies outperforming shadow strategies so manual promotion isn't required.

**Acceptance Criteria:**
- [ ] Create `simulation/auto_promoter.py`
- [ ] Implement `AutoPromoter` class with db_path, config_path, dry_run params
- [ ] Implement `get_live_performance()` - returns live strategy metrics
- [ ] Implement `get_shadow_performance(strategy_name)` - returns shadow metrics
- [ ] Implement `get_promotion_candidates()` - filters by: win_rate +5%, 100+ trades, Sharpe ≥1.2, drawdown ≤25%
- [ ] Implement `promote_strategy(strategy_name, allocation)` - updates config
- [ ] Implement `run_promotion_check()` - main workflow
- [ ] Add CLI args: --dry-run (default), --live (actually promotes)
- [ ] Typecheck passes
- [ ] Test: `python3 simulation/auto_promoter.py --dry-run` shows recommendations

**Status:** ⏳ PENDING

---

### US-016: Create alert_system module
**Description:** As a developer, I need an alert system that detects performance degradation so losses can be prevented early.

**Acceptance Criteria:**
- [ ] Create `analytics/alert_system.py`
- [ ] Implement `AlertSystem` class with db_path, state_path, alert_log_path
- [ ] Implement `check_win_rate_drop(window=20, threshold=0.50)` - alert if <50%
- [ ] Implement `check_balance_drop(threshold_pct=0.20)` - alert if -20% from peak
- [ ] Implement `check_shadow_outperformance(threshold=0.10, min_trades=100)` - alert if shadow +10% better
- [ ] Implement `check_daily_loss_limit(loss_limit_usd=30, loss_limit_pct=0.20)`
- [ ] Implement `check_agent_consensus_failure(min_confidence=0.30)`
- [ ] Implement `run_all_checks()` - runs all alert checks
- [ ] Implement `send_alerts()` - logs to file, prints to stdout
- [ ] Alerts logged to `logs/alerts.log`
- [ ] Typecheck passes
- [ ] Test: `python3 analytics/alert_system.py --test` generates test alert

**Status:** ⏳ PENDING

---

### US-017: Integrate alert system into bot
**Description:** As a bot operator, I need alerts running every 10 minutes so I'm notified of problems quickly.

**Acceptance Criteria:**
- [ ] Modify `bot/momentum_bot_v12.py` main loop
- [ ] Add `alert_check_interval = 600` (10 minutes)
- [ ] Add `last_alert_check = 0` tracker
- [ ] Inside main loop: Check if `time.time() - last_alert_check >= alert_check_interval`
- [ ] If yes: Import AlertSystem, run checks, send alerts, update tracker
- [ ] Wrap in try/except to prevent bot crashes
- [ ] Log alert check completion
- [ ] Typecheck passes
- [ ] Deploy to VPS
- [ ] Verify: `tail -f logs/alerts.log` shows periodic checks

**Status:** ⏳ PENDING

**Dependencies:** Requires US-016 complete

---

### US-018: Schedule auto-promoter daily checks
**Description:** As a bot operator, I need auto-promoter running daily so outperforming strategies are promoted automatically.

**Acceptance Criteria:**
- [ ] Create cron job OR systemd timer for daily execution
- [ ] Schedule: 00:00 UTC daily
- [ ] Command: `cd /opt/polymarket-autotrader && python3 simulation/auto_promoter.py --live >> logs/auto_promoter.log 2>&1`
- [ ] Verify logs created at `logs/auto_promoter.log`
- [ ] Test manually: `python3 simulation/auto_promoter.py --live`
- [ ] Verify promotions (if any) appear in logs
- [ ] Document cron/timer setup in `docs/DEPLOYMENT.md`

**Status:** ⏳ PENDING

**Dependencies:** Requires US-015 complete

---

### US-019: End-to-end validation of automation
**Description:** As a QA engineer, I need to verify the full automation pipeline works so continuous optimization is operational.

**Acceptance Criteria:**
- [ ] Auto-promoter runs daily (check logs for timestamps)
- [ ] Alert system runs every 10 min (check logs for periodic entries)
- [ ] Shadow strategies collect data continuously
- [ ] Promotion workflow triggers when criteria met (simulate by adjusting thresholds)
- [ ] Staged rollout works (25% → 50% → 100%)
- [ ] Auto-rollback works (simulate by forcing win rate drop)
- [ ] All alerts trigger correctly (simulate each condition)
- [ ] Document complete automation workflow in `progress.txt`
- [ ] Measure overall metrics: win rate 60-65%, ROI +20-30%

**Status:** ⏳ PENDING

**Dependencies:** Requires US-015, US-016, US-017, US-018 complete

---

## Final Success Criteria

**Week 1 Complete:**
- [ ] Per-agent tracking operational
- [ ] 1-2 underperformers identified and disabled
- [ ] Win rate improves by 1-2%

**Week 2 Complete:**
- [ ] Higher threshold strategy tested (100+ trades)
- [ ] If validated: promoted with staged rollout
- [ ] Win rate 65%+ OR kept current thresholds with learnings documented

**Week 3 Complete:**
- [ ] Kelly sizing tested (100+ trades)
- [ ] If validated: ROI 20-30% higher
- [ ] If not: kept fixed sizing with learnings documented

**Week 4 Complete:**
- [ ] Auto-promoter operational (daily checks)
- [ ] Alert system operational (10-min checks)
- [ ] Continuous optimization without manual intervention
- [ ] Overall win rate: 60-65%
- [ ] Monthly ROI: +20-30%

---

See `PRD-strategic.md` for high-level roadmap and rationale.
