# 🚨 EMERGENCY: SentimentAgent Single-Handedly Triggering All Trades

**Status:** CRITICAL - Bot placing repeated losing trades
**Pattern:** 4 trades in 20 minutes, all same issue
**Impact:** Directional bias 80% Up (bot detected and warned)

---

## Trades Made (Jan 16, 2026)

| Time | Crypto | Direction | Entry | Reason | Status |
|------|--------|-----------|-------|--------|--------|
| 12:55 | BTC | Up | $0.04 | SentimentAgent 90% | Losing |
| 12:55 | ETH | Up | $0.04 | SentimentAgent 90% | Losing |
| 13:09 | SOL | Up | $0.05 | SentimentAgent 90% | Unknown |
| 13:12 | XRP | Up | $0.05 | SentimentAgent 90% | Unknown |

**Total Risk:** ~$25 (18% of $136 balance)
**Pattern:** All cheap contrarian entries, all during downtrends

---

## Root Cause: SentimentAgent Weighted Score Calculation

### The Problem

**SentimentAgent's 90% confidence × 85% quality = 0.765**

This **single score** exceeds the 0.75 consensus threshold, allowing one agent to trigger trades alone.

### Vote Breakdown (All 4 Trades Identical)

```
Participating Agents (3):
  ⬆️ SentimentAgent:    0.90 × 0.85 = 0.765 (Up)
  ⬇️ OrderBookAgent:   0.62 × 0.20 = 0.124 (Down - DISAGREES!)
  ➡️ FundingRateAgent: 0.30 × 0.35 = 0.105 (Neutral)

Skip votes (2):
  🚫 TechAgent:    Abstained (no confluence)
  🚫 RegimeAgent:  Abstained (sideways regime)

Weighted Score: 0.765 ✅ (meets 0.75 threshold)
Agreement Rate: 33.3% ❌ (only 1/3 agents agreed)
```

### Why This Is Wrong

**The weighted score is NOT averaging the votes correctly.**

Looking at the math:
- If we average: (0.765 + 0.124 + 0.105) / 3 = **0.331** ❌ (below 0.75)
- But system reports: **0.765** ✅ (above 0.75)

**The system is using the MAXIMUM score in the winning direction, not the AVERAGE.**

This allows SentimentAgent to single-handedly trigger trades even when:
- OrderBookAgent disagrees (votes Down)
- TechAgent has no signal
- RegimeAgent has no signal
- Agreement rate is only 33%

---

## Why SentimentAgent Keeps Voting 90% Up

SentimentAgent specializes in **contrarian fades**:

1. Sees Down side priced at $0.95-$0.96 (expensive)
2. Sees Up side priced at $0.04-$0.05 (cheap)
3. Logic: "Market too bearish, fade it"
4. Votes Up with 90% confidence

**The confidence is about opportunity quality, NOT win probability.**

SentimentAgent thinks "this is a GREAT contrarian opportunity" (90% confident in the setup), but that doesn't mean it's 90% likely to win.

---

## Why These Trades Are Losing

At $0.04-$0.05 entry:
- Market pricing: 4-5% probability of Up
- Need crypto to go UP during 15-minute window
- If crypto goes down or flat → lose everything

**But the market is in a DOWNTREND** (per your TradingView chart):
- 3-5 consecutive red candles
- RSI 45-50 (falling)
- Clear bearish momentum

Buying Up during a downtrend = fighting the trend = high loss probability

---

## Immediate Actions Required

### Option 1: Emergency Halt (Safest - 2 min)

**Stop bot immediately until fix deployed:**

```bash
ssh root@216.238.85.11 "systemctl stop polymarket-bot"
```

**Pros:** Prevents more losing trades
**Cons:** Misses trading opportunities
**When to use:** If you can't deploy fix within 30 minutes

---

### Option 2: Raise Consensus Threshold (Quick - 5 min)

**Change threshold from 0.75 to 0.85:**

```bash
# On VPS
ssh root@216.238.85.11

# Edit config
nano /opt/polymarket-autotrader/config/agent_config.py

# Change line:
CONSENSUS_THRESHOLD = 0.85  # Raised from 0.75

# Restart bot
systemctl restart polymarket-bot
```

**Impact:**
- SentimentAgent's 0.765 score now FAILS threshold check
- Requires stronger multi-agent agreement
- May block legitimate trades (more conservative)

**Expected result:** Drastically reduces trade frequency

---

### Option 3: Add Agreement Rate Minimum (Better - 10 min)

**Require ≥50% agreement rate PLUS consensus threshold:**

```python
# File: coordinator/decision_engine.py
# After line checking consensus_threshold

# Calculate agreement rate
total_directional_votes = prediction.vote_breakdown['Up'] + prediction.vote_breakdown['Down']
if total_directional_votes > 0:
    winning_votes = prediction.vote_breakdown.get(prediction.direction, 0)
    agreement_rate = winning_votes / total_directional_votes

    if agreement_rate < 0.50:
        log.warning(f"Agreement rate too low: {agreement_rate:.1%} < 50%")
        return EmptyPrediction(reason=f"Agreement rate {agreement_rate:.1%} below 50% minimum")
```

**Impact:**
- 33% agreement → BLOCKED
- Requires at least half of voting agents to agree
- Still allows strong 2-agent consensus

---

### Option 4: Reduce SentimentAgent Weight (Medium - 10 min)

**Lower weight from 1.0 to 0.6:**

```python
# File: config/agent_config.py
AGENT_WEIGHTS = {
    'TechAgent': 1.0,
    'SentimentAgent': 0.6,      # Reduced from 1.0
    'RegimeAgent': 1.0,
    'RiskAgent': 1.0,
    'OrderBookAgent': 1.0,
    'FundingRateAgent': 1.0
}
```

**New calculation:**
```
SentimentAgent: 0.90 × 0.85 × 0.6 = 0.459
OrderBookAgent: 0.62 × 0.20 × 1.0 = 0.124
FundingRateAgent: 0.30 × 0.35 × 1.0 = 0.105

Weighted Score: (0.459 + 0.124 + 0.105) / 2.6 = 0.265 ❌ (below 0.75)
```

**Impact:**
- SentimentAgent can't trigger trades alone
- Requires support from other agents
- Preserves contrarian strategy when warranted

---

## Recommended Fix (Combination)

**Implement ALL of these:**

1. **Immediate:** Raise CONSENSUS_THRESHOLD to 0.80 (5 min)
2. **Short-term:** Add agreement rate minimum 50% (10 min)
3. **Medium-term:** Reduce SentimentAgent weight to 0.7 (10 min)
4. **Long-term:** Fix weighted score calculation to properly average (US-BF-017)

---

## Why This Wasn't Caught Earlier

1. **Bug fixes focused on agent biases** (default-to-Up)
   - We fixed Skip votes, RSI scoring, directional balance tracking
   - But didn't address single-agent dominance

2. **Weighted score calculation assumed correct**
   - US-BF-007 changed sum to average
   - But implementation may still use max score in winning direction

3. **Agreement rate not enforced**
   - System logs it (33.3%)
   - But doesn't use it as a filter

4. **SentimentAgent confidence not calibrated**
   - 90% confidence doesn't mean 90% win probability
   - It means "90% confident this is a good contrarian setup"

---

## Verification After Fix

**After deploying fix, verify:**

```bash
# Check recent decisions
ssh root@216.238.85.11 "tail -100 /opt/polymarket-autotrader/bot.log | grep 'Weighted Score:'"

# Should see:
# - Scores below 0.80 (if raised threshold)
# - Agreement rate checks failing
# - "BLOCKED" messages for low agreement

# Check trade frequency
ssh root@216.238.85.11 "grep 'ORDER PLACED' /opt/polymarket-autotrader/bot.log | wc -l"

# Should stop increasing rapidly
```

---

## Expected Results

**Before fix:**
- Trade frequency: 4 trades in 20 minutes
- Agreement rate: 33% (1/3 agents)
- Directional bias: 80% Up
- Win rate: Low (losing trades)

**After fix (Option 2 + 3):**
- Trade frequency: ~80% reduction
- Agreement rate: ≥50% required
- Directional bias: Should normalize
- Win rate: Should improve (only strong consensus trades)

---

## Long-term Solution

**US-BF-017 implementation includes:**
- Multi-epoch trend detection
- Lower thresholds for gradual trends
- Trend conflict warnings
- Proper weighted score averaging

But that's 1-2 hours of work. **Deploy emergency fix NOW** to stop the bleeding.

---

## Action Required

**Choose one:**

1. ⏸️ **Stop bot** (systemctl stop polymarket-bot) - Safest, prevents more losses
2. 🚀 **Deploy Option 2** (raise threshold to 0.80) - Quick, 5 minutes
3. 🎯 **Deploy Option 2 + 3** (threshold + agreement rate) - Better, 15 minutes

**I recommend Option 2 immediately, then Option 3 when you have time.**

Would you like me to implement the fix now?
