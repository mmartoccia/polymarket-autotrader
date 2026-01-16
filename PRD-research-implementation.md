# PRD: Research Implementation - Optimization Roadmap

## Introduction

Based on comprehensive research by 9 specialized personas (48 reports, 31 user stories),
this PRD translates findings into executable code changes to achieve 60-65% win rate target.

**Source:** Research Synthesis Report (`reports/RESEARCH_SYNTHESIS.md`)

**Timeline:** 4 weeks (Jan 16 - Feb 13, 2026)

**Strategic Approach:** Simplify first (remove what hurts), then optimize (improve what works).

---

## Goals

1. **Increase win rate** from 56-58% to 60-65%
2. **Reduce system complexity** from 11 agents to 3-5 agents
3. **Lower average entry price** to <$0.20 (from ~$0.24)
4. **Improve agent confidence** calibration
5. **Fix critical bugs** (state tracking, drawdown protection)
6. **Balance directional trades** (40-60% range, not 96.5% UP bias)

---

## System Context

**Current State:**
- Balance: $200.97 (33% drawdown from $300 peak)
- Win Rate: ~58% (validated with statistical significance)
- Architecture: Multi-agent consensus (11 agents voting)
- Critical Issues: State tracking bugs, over-complexity, underperforming agents

**Target State:**
- Balance: Growing steadily with 60-65% WR
- System: 3-5 high-performing agents
- Risk: Robust drawdown protection, balanced directional trades
- Trade Quality: Cheaper entries (<$0.20), better timing (late epoch)

---

## User Stories

#### US-RI-001: Milestone 1.1: Fix State Tracking Bugs
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Peak balance includes unredeemed position values
- Causes false drawdown halts (Jan 16 desync: $186 error)
- Drawdown protection fails when positions settle

**Acceptance Criteria:**
- [x] 1. Review `bot/momentum_bot_v12.py` → `Guardian.check_kill_switch()`
- [x] 2. Change `peak_balance` tracking to use **cash-only balance** (exclude open positions)
- [x] 3. Update peak only on actual cash increases (not position values)
- [x] 4. Add validation: `assert current_balance <= peak_balance`
- [x] Typecheck passes
- [ ] Verify success metrics:
  - No false halts for 7 days
  - Drawdown calculation accurate within $1
  - Peak balance only increases on actual cash gains

**Files to Modify:**
- ``bot/momentum_bot_v12.py``
- ``state/trading_state.json``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-002: Milestone 1.2: Remove Trend Filter
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Trend filter caused 96.5% UP bias (Jan 14 loss: $157 → $7)
- Blocked 319 DOWN bets, 0 UP bets in weak positive trend
- Regime detection (RegimeAgent) provides sufficient trend awareness

**Acceptance Criteria:**
- [x] 1. Review `bot/momentum_bot_v12.py` → trend filter logic
- [x] 2. Remove `TREND_FILTER_ENABLED` and related code
- [x] 3. Keep RegimeAgent for regime-based adjustments
- [x] 4. Remove `STRONG_TREND_THRESHOLD` (no longer needed)
- [x] Typecheck passes
- [ ] Verify success metrics:
  - Directional balance: 40-60% (vs 96.5% before)
  - Win rate: ≥58% (should improve without bias)
  - Trade frequency: Similar or higher (no artificial blocks)

**Files to Modify:**
- ``bot/momentum_bot_v12.py``
- ``config/agent_config.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-003: Milestone 1.3: Disable Underperforming Agents
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Per-agent analysis shows negative contributors:
  - **TechAgent:** 48% WR (below breakeven)
  - **SentimentAgent:** 52% WR (marginal)
  - **CandleAgent:** 49% WR (below breakeven)
- Consensus diluted by poor performers

**Acceptance Criteria:**
- [x] 1. Read `reports/vic_ramanujan/per_agent_performance.md`
- [x] 2. Identify agents with <53% WR (below breakeven)
- [x] 3. Update `config/agent_config.py`:
- [x] 4. Keep high performers: ML, RegimeAgent, RiskAgent
- [x] Typecheck passes
- [ ] Verify success metrics:
  - Trade frequency: Should drop 20-30% (higher quality bar)
  - Win rate: Should improve 2-3% (removing bad votes)
  - Consensus: Should be cleaner (fewer conflicting signals)

**Files to Modify:**
- ``config/agent_config.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-004: Milestone 1.4: Implement Atomic State Writes
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- `trading_state.json` written directly (not atomic)
- Crash during write → corrupted state file
- Bot fails to start after corruption

**Acceptance Criteria:**
- [ ] 1. Review `bot/momentum_bot_v12.py` → `save_state()` function
- [ ] 2. Implement atomic write pattern:
- [ ] 3. Add error handling: if write fails, don't delete old state
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - No state corruption in crash tests
  - State file always valid JSON
  - No data loss during crash recovery

**Files to Modify:**
- ``bot/momentum_bot_v12.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-005: Milestone 2.1: Raise Consensus Threshold
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Current threshold (0.75) allows marginal trades (52-56% WR)
- Need higher confidence bar for consistent profitability

**Acceptance Criteria:**
- [ ] 1. Read `reports/sarah_chen/statistical_significance.md`
- [ ] 2. Calculate optimal threshold:
- [ ] 3. Update `config/agent_config.py`:
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Trade frequency: Drop 30-40% (expected)
  - Win rate: Improve 3-5% (higher quality trades)
  - Min 5 trades/day (ensure sufficient activity)

**Files to Modify:**
- ``config/agent_config.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-006: Milestone 2.2: Optimize Entry Timing Windows
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Early trades (0-300s): 54% WR (high risk)
- Late trades (600-900s): 62% WR (best performance)
- Current strategy doesn't prioritize late entries

**Acceptance Criteria:**
- [ ] 1. Read `reports/jimmy_martinez/timing_window_analysis.md`
- [ ] 2. Add timing preference to decision logic:
- [ ] 3. Update `bot/momentum_bot_v12.py`:
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Late trades (600-900s): ≥60% of total trades
  - Late trade WR: Maintain or improve 62%
  - Overall WR: Improve 1-2%

**Files to Modify:**
- ``bot/momentum_bot_v12.py``
- ``config/agent_config.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-007: Milestone 2.3: Lower Entry Price Threshold
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Entries <$0.15: 68% WR (excellent)
- Entries >$0.25: 52% WR (poor)
- Current `MAX_ENTRY_PRICE = 0.30` (too permissive)

**Acceptance Criteria:**
- [ ] 1. Read `reports/jimmy_martinez/entry_vs_outcome.csv`
- [ ] 2. Update `config/agent_config.py`:
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Average entry price: <$0.20 (from ~$0.24)
  - Cheap entries (<$0.15): ≥40% of trades
  - Win rate: Improve 2-3%

**Files to Modify:**
- ``config/agent_config.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-008: Milestone 3.1: Reduce Agent Count (11 → 5)
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- 11 agents is over-engineered (high correlation, redundancy)
- Maintenance burden: 11 configs, 11 weights, 11 voting logic paths
- Diminishing returns: Most agents don't improve consensus

**Acceptance Criteria:**
- [ ] 1. Read `reports/alex_rousseau/elimination_candidates.md`
- [ ] 2. Keep only proven performers:
- [ ] 3. Remove:
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Agent count: 11 → 5 (55% reduction)
  - Code complexity: ~1600 lines → ~1200 lines
  - Win rate: Maintain or improve (should not drop)
  - Decision latency: Faster (fewer agents to query)

**Files to Modify:**
- ``config/agent_config.py``
- ``agents/` directory`
- ``bot/momentum_bot_v12.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-009: Milestone 3.2: Re-enable Contrarian Strategy
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Contrarian disabled after Jan 14 incident
- Historical data shows 70% WR for contrarian trades
- Missing cheap entry opportunities (<$0.20)

**Acceptance Criteria:**
- [ ] 1. Read `reports/jimmy_martinez/contrarian_performance.md`
- [ ] 2. Update `config/agent_config.py`:
- [ ] 3. Add safeguard: Only in SIDEWAYS/CHOPPY regime (not BULL/BEAR)
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Contrarian trades: 2-5/day (not dominant)
  - Contrarian WR: ≥65% (validate historical performance)
  - Average entry: <$0.15 (cheap entries)

**Files to Modify:**
- ``config/agent_config.py``
- ``bot/momentum_bot_v12.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-010: Milestone 4.1: Add Performance Degradation Alerts
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- No automated alerts for performance issues
- Slow to detect regime shifts or strategy degradation
- Manual monitoring required (time-intensive)

**Acceptance Criteria:**
- [ ] 1. Create `utils/performance_monitor.py`
- [ ] 2. Track rolling metrics (last 50 trades):
- [ ] 3. Define alert thresholds:
- [ ] 4. Send alerts via:
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Alerts triggered correctly in test scenarios
  - No false positives (alert when no actual issue)
  - Alerts visible in dashboard

**Files to Modify:**
- ``utils/performance_monitor.py``
- ``bot/momentum_bot_v12.py``

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---

#### US-RI-011: Milestone 4.2: Shadow Strategy Auto-Promotion
**Priority:** MEDIUM
**Source:** Research Synthesis + Deployment Roadmap

**Problem:**
- Shadow strategies collect data but require manual review
- Best-performing shadows should auto-promote to production
- Continuous optimization requires human intervention

**Acceptance Criteria:**
- [ ] 1. Create `scripts/auto_promote_strategy.py`
- [ ] 2. Query `simulation/trade_journal.db` daily
- [ ] 3. Compare shadow strategies to live strategy:
- [ ] 4. If shadow wins, generate promotion PR:
- [ ] Typecheck passes
- [ ] Verify success metrics:
  - Script identifies outperforming strategies
  - Promotion PRs generated automatically
  - Human approval still required (safety)

**Files to Modify:**
- ``scripts/auto_promote_strategy.py``
- `Cron job: Run daily at 00:00 UTC`

**Testing:**
- Run typecheck: `mypy scripts/research/`
- Verify bot starts without errors
- Monitor for 24-48 hours (shadow testing recommended)

---


---

## Completion Criteria

**ALL user stories complete** when:
- ✅ All checkboxes marked `[x]`
- ✅ Typecheck passes for all modified files
- ✅ Bot runs without errors in production
- ✅ Win rate improvement validated (100+ trades)
- ✅ No critical bugs or regressions

**Success Validation:**
- Win rate: 60-65% over 100 trades
- System complexity: 5 agents, <1200 lines of code
- Trade quality: <$0.20 avg entry, 60%+ late trades
- Risk: No false halts, balanced directional trades

---

## Rollback Strategy

Each user story includes:
- Clear acceptance criteria (testable)
- File paths (easy to revert with git)
- Success metrics (objective go/no-go)
- Testing requirements (shadow testing recommended)

**Rollback Procedure:**
1. Identify failing user story (WR drop, errors, etc.)
2. Revert git commits for that story only
3. Restore config files from backup
4. Monitor for 24 hours to confirm stability
5. Investigate root cause before re-attempting

**Escalation:**
- WR drop <1%: Monitor for 24h (may be noise)
- WR drop 1-2%: Rollback single story
- WR drop >2%: Rollback entire week
- Critical error: HALT bot, full audit

---

## Execution Instructions

Run Ralph to execute this PRD autonomously:

```bash
./ralph.sh PRD-research-implementation.md 50 2
```

Ralph will:
1. Read each user story sequentially
2. Implement changes according to acceptance criteria
3. Run tests and typecheck
4. Mark story complete `[x]` if tests pass
5. Commit changes with descriptive message
6. Continue to next story

**Manual Oversight:**
- Review each commit before deploying to production VPS
- Shadow test major changes (Week 3 agent reduction)
- Monitor win rate after each milestone
- Rollback immediately if WR drops >1%

---

## Progress Tracking

Progress logged in `progress-research-implementation.txt`:

```
## Iteration [N] - US-RI-XXX: [Task Name]
**Priority:** CRITICAL/HIGH/MEDIUM/LOW
**Completed:** YYYY-MM-DD HH:MM
**Files Changed:**
- path/to/file1.py
- path/to/file2.md

**Learnings:**
- Pattern discovered: [useful context]
- Gotcha: [edge case handled]

---
```

---

## Next Steps After Completion

1. **Validate performance** (100+ trades at 60-65% WR)
2. **Update documentation** (CLAUDE.md, STRATEGY.md)
3. **Archive old configs** (`config/archived/`)
4. **Tag release** (`v13.0 - Research Implementation`)
5. **Monitor for 1 month** (ensure stability across regimes)
6. **Scale up** (if 65%+ WR sustained, increase position sizing)

---

**Document Version:** 1.0 (Auto-generated)
**Last Updated:** 2026-01-16
**Status:** READY FOR EXECUTION
**Total User Stories:** {story_counter - 1}

---
