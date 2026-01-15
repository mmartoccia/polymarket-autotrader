# ML Bot Production Stabilization - PRD

**Status:** URGENT - Critical Bugs Blocking ML Performance
**Created:** January 15, 2026
**Priority:** P0 - Production Down
**Owner:** Development Team

---

## Executive Summary

The ML Random Forest trading bot is **deployed and profitable** (60% win rate), but **critical bugs are causing conflicting trades** that negate the edge. We need immediate fixes to stabilize the system before it can prove its full potential.

**Current Status:**
- ✅ ML model working (67.3% test accuracy → 60% live)
- ✅ Order placement fixed
- ✅ Auto-redemption fixed
- ✅ Trade logging implemented
- ✅ **FIXED: Conflicting positions bug** (added live API position check)

**Immediate Goal:** Deploy fixes and collect 50+ clean trades to validate ML performance.

---

## Problem Statement

### Critical Issue: Conflicting Positions

**Observed Behavior:**
All 4 cryptos (BTC, ETH, SOL, XRP) have BOTH Up AND Down positions for the same epoch (11:30-11:45 AM ET).

**Example:**
- XRP 11:30-11:45: Up (40.7 shares @ $0.43) AND Down (15.8 shares @ $0.57)
- BTC 11:30-11:45: Up (26.6 shares @ $0.42) AND Down (31.7 shares @ $0.57)

**Impact:**
- Net loss: $14.18 on these 8 conflicting positions
- ML edge is negated when betting both sides
- Unprofitable even with 60% directional accuracy

**Root Cause (Hypothesis):**
1. Multiple code paths still active (ML + agent fallback?)
2. Correlation protection not working correctly
3. Guardian not tracking positions properly
4. Race condition in order placement

---

## Immediate Priorities (Next 24 Hours)

### ✅ P0: Fix Conflicting Positions Bug (COMPLETED)

**Status:** FIXED - Iteration 1-2 (Jan 15, 2026)

**Acceptance Criteria:**
- ✅ Bot can only hold 1 position per crypto per epoch (either Up OR Down, not both)
- ✅ Explicit validation before order placement: check existing positions for same crypto/epoch
- ✅ If position exists, log clear rejection message: "Already have [direction] position on [crypto] epoch [time]"
- ✅ No agent system fallback when ML is enabled (pure ML mode)

**Implementation Steps:**
1. ✅ Add position conflict check before every order - Guardian.check_live_position_conflicts()
2. ✅ Query live positions from Polymarket API - https://data-api.polymarket.com/positions
3. ✅ Match by crypto + direction - Parses title/outcome fields
4. ✅ Reject order if conflict detected - Returns (True, conflict_message)
5. ✅ Add comprehensive logging for debugging - log.warning/error for conflicts

**Testing:**
- Deploy fix to VPS
- Monitor next 2 hours for conflicts
- Verify only 1 position per crypto per epoch
- Check logs for rejection messages

**Success Metrics:**
- Zero conflicting positions in next 10 trades
- Clean directional bets only

---

### ✅ P1: Add Position Conflict Protection (Guardian Enhancement) (COMPLETED)

**Status:** FIXED - Iteration 1 (included in P0 fix)

**Why:** Guardian was tracking internal positions but not querying live blockchain state.

**Changes Implemented:**
```python
class Guardian:
    def check_live_position_conflicts(self, crypto, direction):
        # Query live Polymarket API for current positions
        # Check for conflicts by crypto + direction
        # Returns (has_conflict, conflict_message)

    def can_open_position(self, crypto, epoch, direction):
        # PRIORITY 1: Check live API first
        has_conflict, msg = self.check_live_position_conflicts(crypto, direction)
        if has_conflict:
            return False, msg
        # ... existing checks
```

**Testing:**
- ✅ Unit test created: test_conflict_check.py (5/5 scenarios pass)
- Integration test: deploy and verify no conflicts in live trading

---

### ✅ P2: Disable Agent System Fallback (Pure ML Mode) (COMPLETED)

**Status:** FIXED - Iteration 2 (Jan 15, 2026)

**Why:** Any fallback to agents risks conflicting decisions.

**Changes Implemented:**
1. ✅ ML path does `continue` at line 2240 (skips agents)
2. ✅ ML exception handler does `continue` (doesn't fall through)
3. ✅ Added explicit guard in agent path to double-check ML mode

**Code Added:**
```python
# Line ~2250 (bot/momentum_bot_v12.py):
elif agent_system and agent_system.enabled:
    # SAFETY: Ensure we never run agents when ML mode is active
    if use_ml_bot and ML_BOT_AVAILABLE:
        log.warning(f"Skipping agent decision - ML mode active")
        continue
    # Agent code only runs when ML disabled
    ...
```

**Testing:**
- ✅ Code review: ML path continues, agents can't run
- ✅ Explicit guard added for safety
- Deploy and verify: should be ZERO agent decisions when ML enabled

---

## Secondary Priorities (Next 48 Hours)

### P3: Validate Trade Logging is Working

**Goal:** Confirm ML trades are being logged to `simulation/trade_journal.db`

**Steps:**
1. Check database for `ml_live_ml_random_forest` strategy entries
2. Verify trades logged since 16:00 UTC today
3. Compare log count vs actual orders placed

**Query to Run:**
```bash
sqlite3 simulation/trade_journal.db "SELECT COUNT(*) FROM trades WHERE strategy = 'ml_live_ml_random_forest' AND timestamp > $(date -d '16:00' +%s)"
```

**Expected:** 15-20 trades logged (matching number of orders placed)

---

### P4: Add Monitoring & Alerts

**Immediate Monitoring Needed:**
1. **Position Conflict Alert:** Check every 5 minutes for same crypto with both Up/Down
2. **Balance Drop Alert:** If balance drops >10% in 15 minutes
3. **Order Placement Failures:** Count consecutive failures (>3 = alert)
4. **ML Decision Failures:** Count exceptions in ML decision path

**Implementation:**
Simple script that runs on VPS and sends alerts:
```bash
# /opt/polymarket-autotrader/scripts/monitor.sh
# Run via cron: */5 * * * * /opt/polymarket-autotrader/scripts/monitor.sh

# Check for conflicting positions
# Check balance vs 15min ago
# Check error logs
# Send alert if issues found
```

---

## Success Criteria (Week 1)

### Day 1 (Today) - Critical Fixes
- ✅ No conflicting positions in next 20 trades
- ✅ Pure ML decisions only (no agent fallback)
- ✅ Trade logging confirmed working

### Day 2-3 - Data Collection
- ✅ Collect 50+ resolved trades with ML-only logic
- ✅ Track win rate, P&L, confidence levels
- ✅ No system crashes or halts

### Day 4-7 - Performance Validation
- ✅ Calculate actual win rate (target: 55-65%)
- ✅ Compare live vs shadow ML strategies
- ✅ Statistical significance test (chi-square p<0.05)
- ✅ Validate 60% win rate hypothesis

**Go/No-Go Decision (Day 7):**
- **GO:** Win rate >55% sustained → continue ML trading, increase capital
- **NO-GO:** Win rate <50% → investigate model, retrain, or revert to agents

---

## Risk Management

### Current Safeguards (Keeping Active)
1. ✅ 30% drawdown halt (automatic stop)
2. ✅ Position sizing limits (5-15% per trade)
3. ✅ Correlation limits (max 4 positions total)
4. ✅ Guardian risk checks before every trade

### New Safeguards (Adding)
1. **Epoch Conflict Prevention:** Max 1 position per crypto per epoch
2. **Pure ML Mode:** No agent fallback when ML enabled
3. **Real-time Monitoring:** 5-minute conflict checks
4. **Conservative Threshold:** Keep 55% confidence minimum

### Rollback Plan
If critical issues persist after fixes:
1. Stop bot immediately (manual halt file)
2. Set `USE_ML_BOT=false` in systemd service
3. Revert to agent consensus mode (last stable config)
4. Redeem all positions
5. Investigate offline before re-enabling

---

## Known Issues (Tracking)

### Critical (P0)
1. ✅ **Conflicting positions bug** - Both Up/Down same epoch - **FIXED**
   - Status: Fixed in iterations 1-2 (Jan 15, 2026)
   - Root cause: Guardian not querying live API, relied on internal list
   - Solution: Added check_live_position_conflicts() method
   - Ready for deployment testing

### High (P1)
2. ⚠️ **Peak balance tracking** - Includes unrealized positions, causes false halts
   - Workaround: Manual reset via script
   - Long-term fix: Track realized cash only

### Medium (P2)
3. ⚠️ **Minimum order size errors** - Some ML trades too small (3 shares < 5 minimum)
   - Impact: Missed trading opportunities
   - Fix: Increase minimum sizing to 5 shares

### Low (P3)
4. ℹ️ **sklearn version warning** - Model trained on 1.7.2, running on 1.8.0
   - Impact: None (predictions work correctly)
   - Fix: Retrain models with 1.8.0 (low priority)

---

## Technical Debt

### Code Cleanup Needed
1. Remove unused agent system code when `USE_ML_BOT=true`
2. Simplify Guardian position tracking (single source of truth)
3. Consolidate trade logging (eliminate duplicate paths)
4. Add comprehensive unit tests for order placement

### Documentation Needed
1. ML deployment checklist
2. Debugging guide for position conflicts
3. Manual redemption procedure
4. Emergency rollback steps

---

## Metrics & KPIs

### Real-time Tracking
- **Balance:** Track every 15 minutes
- **Open Positions:** Count and direction per crypto
- **ML Confidence:** Average per trade
- **Order Success Rate:** Orders placed / ML TRADE decisions

### Daily Reporting
- **Trades Placed:** Count per day
- **Win Rate:** Resolved wins / total resolved
- **P&L:** Daily gain/loss
- **Drawdown:** Max intraday drawdown

### Weekly Analysis
- **Cumulative Win Rate:** 7-day rolling average
- **ROI:** Weekly return on starting balance
- **Per-Crypto Performance:** BTC/ETH/SOL/XRP win rates
- **Confidence Calibration:** Actual win rate by confidence bucket

---

## Dependencies

### External Systems
- Polymarket CLOB API (order placement)
- Polymarket Data API (position tracking)
- Polygon RPC (balance checks, redemptions)
- Exchange APIs (Binance, Kraken, Coinbase for price feeds)

### Internal Systems
- ML Random Forest model (trained Jan 14, 2026)
- Shadow trading system (strategy comparison)
- Trade journal database (SQLite logging)
- Guardian risk management (position limits)

### Environment
- VPS: 216.238.85.11 (Vultr Mexico City)
- Python: 3.12 (venv)
- Bot: momentum_bot_v12.py (ML mode enabled)
- Service: systemd (polymarket-bot.service)

---

## Timeline

### Immediate (Next 4 Hours)
- ⏰ **16:30-17:00:** Investigate conflicting positions root cause
- ⏰ **17:00-18:00:** Implement position conflict check
- ⏰ **18:00-18:30:** Deploy and test fix
- ⏰ **18:30-20:30:** Monitor next 8 trades for conflicts

### Short-term (Next 24 Hours)
- ⏰ **Day 1 Evening:** Confirm zero conflicts in 20+ trades
- ⏰ **Day 1 Night:** Let bot run overnight with monitoring
- ⏰ **Day 2 Morning:** Review overnight performance, adjust if needed

### Medium-term (Week 1)
- ⏰ **Day 2-3:** Collect 50+ resolved trades
- ⏰ **Day 4:** Statistical analysis (chi-square test)
- ⏰ **Day 5-7:** Performance validation and reporting
- ⏰ **Day 7:** Go/No-Go decision meeting

---

## Communication Plan

### Stakeholders
- **User (Product Owner):** Real-time updates on critical fixes
- **Development Team:** Technical details and code reviews
- **Agent Team:** Focused PRD for autonomous execution

### Update Frequency
- **Critical Issues:** Immediate (Slack/Discord)
- **Daily Standup:** 9:00 AM - Progress, blockers, plan
- **Weekly Review:** Sunday evening - Performance analysis

### Escalation Path
1. **Minor issues:** Log and fix in next sprint
2. **Major issues:** Stop trading, investigate immediately
3. **Critical issues:** Manual intervention, user notification

---

## Open Questions

1. **Is agent system completely disabled when USE_ML_BOT=true?**
   - Need to verify no code paths can trigger agent decisions
   - Check all exception handlers for agent fallback

2. **Why are positions still conflicting after guardian.add_position fix?**
   - Is there a race condition?
   - Multiple scan cycles placing orders before position update?
   - Guardian not querying live positions correctly?

3. **Should we add a hard limit: max 1 position per crypto globally?**
   - Would prevent all conflicts but reduce trading frequency
   - Trade-off: safety vs opportunity

4. **Is the ML model directionally accurate on these conflicting positions?**
   - If we just took the first ML decision (ignore second), would we win?
   - This would validate model quality separate from system bugs

---

## Appendix

### Deployment History (Jan 15, 2026)

**16:00 UTC:** ML bot deployed to production
- Commit: 7943a75 - Added order placement logic

**16:05 UTC:** Bug #1 discovered - ML not placing orders
- Fixed: Added complete order execution flow

**16:10 UTC:** Bug #2 discovered - Auto-redemption not working
- Fixed: Check every cycle instead of epoch-gated

**16:15 UTC:** Bug #3 discovered - Agent fallback causing conflicts
- Fixed: Removed guardian.add_position() call

**16:20 UTC:** Bug #4 discovered - Conflicts still occurring
- Status: Under investigation (CURRENT)

### Performance Data

**ML Model:**
- Training: 711 samples, 10 features
- Test Accuracy: 67.3%
- Live Win Rate: 60% (5 trades resolved)

**Recent Trading:**
- Balance Start: $242.44 (after redemptions)
- Balance Current: $176.78
- Loss: $65.66 (due to conflicting positions bug)
- Pending Value: $102.74 (8 positions)

### Key Files Modified Today

1. `bot/momentum_bot_v12.py`
   - Added ML order placement logic (lines 2058-2128)
   - Added direct SQLite logging (lines 73-104)
   - Removed guardian.add_position call (line 2152)
   - Fixed AutoRedeemer epoch gating (lines 1269-1275)

2. `bot/ml_bot_adapter.py`
   - ML decision adapter (unchanged today)

3. `simulation/trade_journal.db`
   - SQLite database for trade logging (needs validation)

---

**Next Step:** Team to investigate conflicting positions bug and implement fix within 4 hours.
