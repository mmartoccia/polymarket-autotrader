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

**Next Phase Preview:**
- Week 2: Selective trading (test 0.80/0.70 thresholds)
- Week 3: Kelly Criterion position sizing
- Week 4: Automated promotion + alerts

See `PRD-strategic.md` for full 4-week roadmap.
