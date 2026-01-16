# Risk Management Team Report
## Incident Analysis: January 15, 2026

**Team Lead:** Risk Manager
**Team Members:** Quant Risk Analyst, Portfolio Manager
**Report Date:** January 16, 2026
**Priority:** 🔴 **CRITICAL**

---

## Executive Summary

**Finding:** Drawdown protection system **worked correctly** but was fed **incorrect data** due to state tracking failure.

**Actual Drawdown:** 33% ($300 → $201)
**Threshold:** 30%
**Expected Behavior:** Bot should halt
**Actual Behavior:** Bot did not halt

**Root Cause:** State file had `peak_balance = $14.91` (wrong), causing drawdown calculation to return **negative value** (-12.48), which never triggers halt.

**Key Insight:** The risk system is sound. The bug is in **data quality**, not risk logic.

---

## Drawdown Protection Analysis

### Current System Design

**Code Location:** `bot/momentum_bot_v12.py` lines 570-588

```python
def check_kill_switch(self) -> Tuple[bool, str]:
    if self.state.peak_balance > 0:
        cash_balance = get_usdc_balance()
        redeemable_value = self.get_redeemable_value()
        effective_balance = cash_balance + redeemable_value

        drawdown = (self.state.peak_balance - effective_balance) / self.state.peak_balance
        if drawdown > MAX_DRAWDOWN_PCT:
            return True, f"Drawdown {drawdown*100:.1f}% exceeds {MAX_DRAWDOWN_PCT*100}%"
```

**Design Assessment:** ✅ **CORRECT**

This is industry-standard drawdown calculation:
- Uses high-water mark (peak_balance)
- Includes unrealized value (redeemable positions)
- Clear threshold enforcement
- Proper logging

### Why It Failed

**Input Data:**
```python
peak_balance = 14.91        # WRONG (should be 300.00)
effective_balance = 200.97  # CORRECT (from blockchain)

drawdown = (14.91 - 200.97) / 14.91 = -12.48
```

**Result:** Negative drawdown = Bot thinks it's winning, not losing.

**Correct Calculation:**
```python
peak_balance = 300.00       # CORRECT
effective_balance = 200.97  # CORRECT

drawdown = (300.00 - 200.97) / 300.00 = 0.3301 = 33.01%
```

**Result:** 33% > 30% threshold → **Should halt immediately**

### Timeline of Failure

1. **Jan 13-14:** Balance reaches $300 (true peak)
2. **Jan 14-15:** Losses occur, balance drops to ~$201
3. **Jan 15 00:00:** Daily reset triggers, `peak_balance = current_balance` (Bug #1)
4. **Jan 15 AM:** State file manually edited or corrupted (`peak = $14.91`)
5. **Jan 15 PM:** Bot continues trading with wrong peak reference
6. **Result:** 33% drawdown not detected

---

## Risk Rule Violations Analysis

### Position Limits (✅ Not Violated)

**Rules:**
- Max 4 positions total (1 per crypto)
- Max 8% exposure in one direction

**Incident Data:**
- 28 trades placed
- Database shows mix of BTC, ETH, SOL, XRP
- No evidence of >4 concurrent positions

**Conclusion:** Position limits were respected.

### Position Sizing (⚠️ Needs Review)

**Current Tiers:**
```python
POSITION_TIERS = [
    (30, 0.15),     # Balance < $30: max 15%
    (75, 0.10),     # Balance $30-75: max 10%
    (150, 0.07),    # Balance $75-150: max 7%
    (inf, 0.05),    # Balance > $150: max 5%
]
```

**Actual Sizing (from trade data):**
- Balance: $200-300 range
- Tier: 5% max (inf tier)
- Expected: $10-15 per trade
- Actual: Varies by entry price and ML confidence

**Assessment:** ✅ **Appropriate**

At $250 balance:
- 5% = $12.50 max position
- Typical ML trade: $9-15
- Within limits ✓

### Drawdown Limit (❌ VIOLATED)

**Rule:** Max 30% drawdown from peak

**Actual:** 33% drawdown occurred without halt

**Reason:** State tracking failure (not risk system failure)

**Action Required:** Fix state tracking (see Software Engineering report)

### Daily Loss Limit (❓ UNKNOWN)

**Rule:** Max $30 or 20% daily loss

**Data Available:**
- No outcome data to calculate daily P&L
- Cannot determine if limit was exceeded

**Recommendation:** Add daily loss tracking with outcome logging

---

## Current Risk Parameters Review

### MAX_DRAWDOWN_PCT = 0.30 (30%)

**Assessment:** ✅ **APPROPRIATE**

Industry standard for algo trading:
- Conservative: 15-20%
- Moderate: 25-30%
- Aggressive: 35-40%

**Recommendation:** KEEP at 30%, but add:
- 25% soft warning
- 35% emergency halt
- Absolute dollar loss limit

### Position Sizing Tiers

**Assessment:** ✅ **APPROPRIATE**

Aggressive at low balance ($30), conservative at high balance ($150+).

**Recommendation:** KEEP current tiers, but consider:
- Lower tier 1 to 12% (was 15%)
- Add Kelly Criterion overlay (Week 3 optimization)

### MAX_SAME_DIRECTION_POSITIONS = 4

**Assessment:** ⚠️ **TOO LOOSE**

If all 4 positions are Up (or Down), that's 100% directional bias.

**Recommendation:** REDUCE to 3 max same direction

```python
MAX_SAME_DIRECTION_POSITIONS = 3  # Was 4
```

### DAILY_LOSS_LIMIT_USD = 30

**Assessment:** ⚠️ **TOO LOOSE** at high balance

At $300 balance:
- $30 loss = 10% daily loss
- After 3 bad days: -30% total

**Recommendation:** Make it percentage-based:

```python
DAILY_LOSS_LIMIT_PCT = 0.10  # 10% max daily loss
DAILY_LOSS_LIMIT_USD = max(30, balance * DAILY_LOSS_LIMIT_PCT)
```

---

## Enhanced Risk Controls Proposal

### Proposed Changes (P0 - CRITICAL)

#### 1. Multi-Tier Drawdown Protection

```python
# Current (single threshold):
MAX_DRAWDOWN_PCT = 0.30  # 30% = halt

# Proposed (multi-tier):
DRAWDOWN_WARNING = 0.20   # 20% = reduce sizing to 75%
DRAWDOWN_DEFENSIVE = 0.25 # 25% = reduce sizing to 50%
DRAWDOWN_HALT = 0.30      # 30% = full stop
DRAWDOWN_ABSOLUTE = 0.40  # 40% = emergency halt (failsafe)
```

**Rationale:** Gradual risk reduction as losses mount, instead of binary halt.

#### 2. Absolute Dollar Loss Limits

```python
# Add to risk checks:
ABSOLUTE_LOSS_LIMIT = 100  # Halt if down $100 from peak

if (peak_balance - current_balance) >= ABSOLUTE_LOSS_LIMIT:
    return True, f"Absolute loss ${peak_balance - current_balance:.2f} exceeds ${ABSOLUTE_LOSS_LIMIT}"
```

**Rationale:** $100 loss at $300 balance is catastrophic (33%). Absolute limit provides failsafe.

#### 3. Rapid Loss Detection

```python
# Track balance every 5 minutes:
balance_history = deque(maxlen=12)  # Last hour (12 x 5min)

# Check for rapid decline:
if len(balance_history) >= 4:  # 20 minutes of data
    loss_20min = balance_history[0] - balance_history[-1]
    if loss_20min > 30:  # >$30 in 20 minutes
        return True, "Rapid loss detected: $30+ in 20 minutes"
```

**Rationale:** Catch sudden cascades before daily limit reached.

#### 4. Win Rate Circuit Breaker

```python
# Add to risk checks (requires outcome logging):
if len(recent_trades) >= 10:
    win_rate = sum(1 for t in recent_trades if t.won) / len(recent_trades)
    if win_rate < 0.40:  # <40% win rate
        return True, f"Win rate {win_rate*100:.1f}% below 40% threshold"
```

**Rationale:** If strategy stops working, halt before major losses.

#### 5. Consecutive Loss Limit

```python
# Current:
if self.state.consecutive_losses >= 5:
    return True, "5 consecutive losses"

# Proposed:
if self.state.consecutive_losses >= 3:  # Tighter limit
    return True, "3 consecutive losses - strategy may be broken"
```

**Rationale:** With 6% fees, 3 losses = -18% without any wins. Tighten trigger.

---

## Risk Parameters Recommendation Summary

### APPROVE (No Changes)

- ✅ `MAX_DRAWDOWN_PCT = 0.30` (30% halt)
- ✅ Position sizing tiers
- ✅ `MAX_POSITION_USD = 15`

### MODIFY (Tighten)

- ⚠️ `MAX_SAME_DIRECTION_POSITIONS = 3` (was 4)
- ⚠️ `DAILY_LOSS_LIMIT_USD = max(30, balance * 0.10)` (percentage-based)
- ⚠️ `CONSECUTIVE_LOSS_LIMIT = 3` (was 5)

### ADD (New Protections)

- 🆕 `DRAWDOWN_WARNING = 0.20` (20% soft limit)
- 🆕 `DRAWDOWN_DEFENSIVE = 0.25` (25% defensive mode)
- 🆕 `ABSOLUTE_LOSS_LIMIT = 100` ($100 max loss)
- 🆕 `RAPID_LOSS_LIMIT = 30` ($30 in 20 min)
- 🆕 `WIN_RATE_THRESHOLD = 0.40` (40% min win rate)

---

## State Tracking Requirements (for Risk System)

### Current Dependencies

Risk system depends on:
1. `state.peak_balance` (for drawdown calc)
2. `state.current_balance` (for position sizing)
3. `state.consecutive_losses` (for loss limit)

All three were **incorrect** during incident.

### Required Improvements

1. **State Validation** (see Software Engineering report)
   - Verify state against blockchain every cycle
   - Auto-correct desyncs > 2%
   - Alert on desyncs > 10%

2. **Peak Balance Persistence**
   - Remove daily reset (Bug #1)
   - Persist peak across days
   - Only reset on manual command

3. **Redundant Balance Tracking**
   - Store balance in 3 places:
     - State file (fast)
     - Balance history file (audit trail)
     - Database snapshots (forensics)

4. **Real-time Validation**
   - Check state vs blockchain every 5 minutes
   - Alert if discrepancy > 5%
   - Auto-halt if discrepancy > 20%

---

## Monitoring & Alerting Recommendations

### Critical Alerts (Telegram)

1. **Drawdown Approaching Limit**
   - Alert at 20%, 25%, 27.5%, 30%
   - Include: current balance, peak, drawdown %

2. **State Desync Detected**
   - Alert if state != blockchain > 5%
   - Include: state balance, blockchain balance, diff

3. **Consecutive Losses**
   - Alert at 2, 3 losses
   - Include: loss streak cost, current mode

4. **Rapid Loss**
   - Alert if >$20 lost in 20 minutes
   - Include: balance 20min ago, current, rate

5. **Win Rate Degradation**
   - Alert if win rate <45% (last 10 trades)
   - Include: wins, losses, win rate

### Dashboard Enhancements

Add to live dashboard:
```
RISK METRICS:
  Peak Balance:        $300.00
  Current Balance:     $200.97
  Drawdown:            33.0% ⚠️ EXCEEDED
  Daily Loss:          $-99.03 (-33.0%)
  Consecutive Losses:  0 ✓

LIMITS:
  Drawdown Limit:      30.0% ❌ VIOLATED
  Daily Loss Limit:    $30.00 ❌ VIOLATED
  Position Limit:      4 ✓
  Same Direction:      3 ✓

ALERTS:
  🚨 Drawdown 33% exceeds 30% limit
  🚨 Daily loss $99 exceeds $30 limit
  ⚠️ State validation: last check 2s ago ✓
```

---

## Recommendations by Priority

### P0 - Deploy Immediately

1. ✅ Fix state tracking (Software Engineering team)
2. ✅ Add state validation on startup
3. ✅ Remove daily peak reset
4. ✅ Add Telegram alerts for drawdown warnings

### P1 - Deploy This Week

5. Add absolute dollar loss limit ($100)
6. Add rapid loss detection (20min window)
7. Tighten consecutive loss limit (3 instead of 5)
8. Add win rate circuit breaker (requires outcome logging)

### P2 - Deploy Next Month

9. Implement multi-tier drawdown (20/25/30%)
10. Add percentage-based daily loss limit
11. Build risk metrics dashboard
12. Implement Kelly Criterion sizing

---

## Risk Assessment of Changes

### Risk #1: Tighter Limits Halt Bot Prematurely

**Probability:** MEDIUM
**Impact:** LOW (manual restart required)

**Mitigation:**
- Monitor false positive rate
- Adjust thresholds if needed
- Add manual override command

### Risk #2: State Validation Triggers Halt

**Probability:** HIGH (if current drawdown > 30%)
**Impact:** MEDIUM (correct behavior, but disruptive)

**Mitigation:**
- Check actual drawdown before deploying
- Expect halt if drawdown > 30%
- This is **correct behavior** - should halt

### Risk #3: Monitoring Alerts Create Noise

**Probability:** MEDIUM
**Impact:** LOW (alert fatigue)

**Mitigation:**
- Tune alert thresholds based on data
- Add alert de-duplication
- Separate critical vs informational alerts

---

## Success Metrics

### Post-Fix Metrics to Track

1. **Drawdown Accuracy:** Should match manual calculation (100% match)
2. **False Halts:** Should be 0 (no halts when < 30%)
3. **Missed Halts:** Should be 0 (halts when > 30%)
4. **State Desyncs:** Should be 0 after validation added
5. **Alert Accuracy:** >95% (alerts are actionable)

### Performance Targets

- **Current:** 56% win rate, 33% max drawdown
- **Target:** 60%+ win rate, <25% max drawdown
- **Timeline:** 4 weeks (per optimization roadmap)

---

## Conclusion

The risk management system is **fundamentally sound**. The failure was caused by **bad input data** (state tracking bug), not flawed risk logic.

**Key Actions:**
1. Fix state tracking (P0)
2. Add enhanced protections (P1)
3. Improve monitoring (P1)
4. Continue optimization roadmap (P2)

With these changes, the bot will halt correctly at 30% drawdown and provide early warnings at 20% and 25%.

---

**Report Status:** ✅ **COMPLETE**
**Action Required:** Review and approve risk parameter changes
**Estimated Impact:** Fewer trades, lower risk, better protection
**Expected Outcome:** No more runaway losses
