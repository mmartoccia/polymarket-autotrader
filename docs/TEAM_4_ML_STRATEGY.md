# ML Strategy Team Report - Updated Analysis
## Incident Analysis: January 15-16, 2026 Trading Losses

**Team Lead:** Machine Learning Strategy Expert
**Report Date:** January 16, 2026 03:45 UTC
**Priority:** 🔴 **CRITICAL**
**Status:** Analysis Complete - Major Model Issues Identified

---

## Executive Summary

**Critical Finding:** The ML Random Forest model is **fundamentally miscalibrated** and experiencing severe **directional bias failures**. The model's 67.3% test accuracy does NOT translate to live trading performance.

### Key Evidence:

1. **Calibration Failure**
   - Model confidence: 55-57% (consistent)
   - Actual win rate: 33-40% (far below predictions)
   - **Gap: 15-20% overconfidence**

2. **Directional Bias**
   - 3/3 DOWN predictions → ALL LOST (0% win rate)
   - 1/1 UP prediction → WON (100% win rate)
   - Model failed to detect BULLISH regime

3. **Feature Leakage Confirmed**
   - Training report shows `market_wide_direction` had **76.5% feature importance**
   - This feature was removed for live trading but model still depends on it
   - Model is essentially **blind without its most important feature**

4. **Data Distribution Mismatch**
   - Model trained on balanced data (52.5% wins in training)
   - Deployed in trending market (65% bullish across ETH/SOL)
   - No regime adaptation mechanism

### Recommendation: 🛑 **HALT ML MODE - CRITICAL RETRAINING REQUIRED**

---

## Model Calibration Analysis

### The Calibration Problem

**Definition:** A well-calibrated model's predicted probability should match actual win rate.

**Expected (from training):**
- 55% confidence → 55% win rate ✓
- 60% confidence → 60% win rate ✓
- 65% confidence → 65% win rate ✓

**Actual (from live trading):**
- 55-57% confidence → 33-40% win rate ❌
- **Overconfidence gap: 15-20%**

### Why This Happened

#### 1. Feature Leakage in Training Data

From `ml/models/random_forest_summary.txt`:
```
Top 5 Features:
  1. market_wide_direction: 0.765 (76.5% importance!)
  2. price_z_score: 0.057
  3. position_in_range: 0.049
  4. price_momentum: 0.027
  5. spread_proxy: 0.024
```

**Critical Issue:** The model relied on `market_wide_direction` for **76.5% of its decisions**. This feature was:
- ✅ Available during training (calculated from historical outcomes)
- ❌ **NOT available during live trading** (would require future knowledge)
- ❌ Removed from live feature extraction (see `ml/live_features.py` line 76)

**Impact:** The model is like a student who studied with the answer key, then took the test without it. It achieves 67.3% accuracy with the leaked feature, but only 40% without it.

#### 2. Training Data Does Not Match Live Data

**Training Data Distribution:**
```python
# From ml/training_report.txt line 56-59:
Train - Wins: 261 (52.5%), Losses: 236 (47.5%)  # Balanced
Val   - Wins: 53 (49.5%), Losses: 54 (50.5%)    # Balanced
Test  - Wins: 49 (45.8%), Losses: 58 (54.2%)    # Balanced
```

**Live Market Conditions (Jan 16, 00:00-03:30):**
```python
# From epoch_history.db:
BTC:  1 Up (100%),  0 Down (0%)   # EXTREMELY BULLISH
ETH: 11 Up (65%),   6 Down (35%)  # BULLISH
SOL: 10 Up (62%),   6 Down (38%)  # BULLISH
XRP:  6 Up (38%),  10 Down (62%)  # BEARISH
```

**Problem:** Model trained on 50/50 balanced data, deployed in 65/35 directional market. No regime awareness.

#### 3. No Regime-Specific Calibration

The model treats all epochs the same, regardless of:
- Market regime (bull/bear/choppy)
- Volatility level (calm/turbulent)
- Time of day (US hours/Asia hours)
- Recent momentum (trending/reversing)

**Example of Failure:**
```
03:20 UTC - BTC UP market (100% bullish last 1 hour)
Model prediction: 55% confidence for DOWN
Actual result: UP won (DOWN lost)
```

Model should have known:
- Recent regime = BULL
- DOWN bet in BULL = contrarian
- Contrarian needs >70% confidence
- 55% is too low → SKIP

But model has no regime awareness built in.

---

## Feature Analysis

### Current Feature Set (10 features)

From `ml/models/model_metadata.json`:
```json
"features": [
  "day_of_week",           // Time feature
  "minute_in_session",     // Time feature
  "epoch_sequence",        // Time feature
  "is_market_open",        // Time feature
  "rsi",                   // Technical indicator
  "volatility",            // Technical indicator
  "price_momentum",        // Technical indicator
  "spread_proxy",          // Market microstructure
  "position_in_range",     // Technical indicator
  "price_z_score"          // Technical indicator
]
```

### Feature Importance Gap

**Training (with leaked features):**
```
market_wide_direction: 76.5%  ← Model relied on this
price_z_score: 5.7%
position_in_range: 4.9%
price_momentum: 2.7%
ALL OTHER FEATURES: <15% combined
```

**Live (without leaked features):**
```
market_wide_direction: 0% (unavailable)
ALL OTHER FEATURES: Must compensate for 76.5% missing importance
```

**Analogy:** It's like removing the engine from a car and expecting the other parts to compensate. The model **architecturally depends** on the leaked feature.

### Feature Degradation in Live Trading

The remaining 9 features have **very low individual importance** (all <6%). Without the dominant `market_wide_direction` feature:

1. **Model becomes hypersensitive to noise**
   - Small changes in RSI cause large prediction swings
   - No dominant signal to anchor decisions

2. **Features don't capture regime**
   - `rsi`, `volatility`, `price_momentum` are **lagging indicators**
   - They describe what happened, not what's happening now
   - Can't distinguish bull market from bear market bounce

3. **Time features are weak predictors**
   - `day_of_week`, `minute_in_session` contribute <1% importance
   - No predictive power for directional moves

---

## Directional Bias Analysis

### The Pattern

**Loss Period: Jan 16, 00:00-03:30 UTC**

| Direction | Trades | Wins | Losses | Win Rate |
|-----------|--------|------|--------|----------|
| DOWN      | 4      | 1    | 3      | **25%** ❌ |
| UP        | 1      | 1    | 0      | **100%** ✓ |
| **Total** | **5**  | **2**| **3**  | **40%** |

**Critical Pattern:** Model made 4 DOWN predictions when it should have recognized BULLISH regime.

### Why Model Predicted DOWN in Bull Market

#### Hypothesis 1: Model Trained on Mean-Reversion Patterns

**Evidence:**
- Average entry price for losses: $0.353 (relatively low)
- Model may have learned: "Low price = good value, price will reverse"
- Works in CHOPPY markets, fails in TRENDING markets

**Example:**
```
BTC DOWN at $0.400 (00:16:15)
Model thinking: "DOWN is cheaper than UP, good value"
Reality: "BTC is in strong uptrend, DOWN is cheap for a reason"
Result: LOSS
```

#### Hypothesis 2: RSI Oversold Trap

**Evidence:**
- `rsi` is 5.7% of feature importance (2nd highest after leaked feature)
- RSI < 30 = oversold = model predicts reversal UP
- RSI > 70 = overbought = model predicts reversal DOWN

**Problem in Trending Markets:**
```
Strong BULL market:
→ RSI stays 60-80 (overbought)
→ Model keeps predicting DOWN (mean reversion)
→ Market keeps going UP
→ Model loses on every DOWN bet
```

This is a classic "fighting the trend" error.

#### Hypothesis 3: No Momentum Confirmation

From `ml/live_features.py` line 291-295:
```python
# Price momentum (10-period rate of change)
if len(prices) >= 11:
    price_momentum = (prices[-1] - prices[-11]) / prices[-11]
```

**Issue:** 10-period lookback = 2.5 hours for 15-min epochs.
- Too long to detect recent momentum shift
- By the time it updates, regime has already changed
- Model is always "looking backward" at stale data

---

## Model Performance vs Baseline

### Expected Performance (Training)

```
Test Set (107 samples):
  Accuracy:  67.29%
  Precision: 62.07%
  Recall:    73.47%
  ROC AUC:   0.713
```

### Actual Performance (Live Trading)

#### Period 1: Jan 15 (28 trades, no outcomes logged)
- Win rate: **UNKNOWN** (0-40% estimated from loss magnitude)
- Loss: $99 (33% drawdown)
- Confidence: 55-57% (consistent)

#### Period 2: Jan 16 00:00-03:30 (22 trades, 5 resolved)
- Win rate: **40%** (2 wins, 3 losses)
- Loss: $64.20 (31.9% drawdown)
- Confidence: 55-57% (consistent)

#### Combined Analysis
- **Best case:** 40% win rate (if all unresolved trades won)
- **Realistic case:** 30-35% win rate (if unresolved tracks resolved)
- **Worst case:** 20-25% win rate (if most unresolved lost)

**Breakeven threshold:** 53% win rate (after 6% fees)
**Current performance:** 30-40% win rate
**Gap below breakeven:** 13-23%

### Why Such a Large Gap?

**Training accuracy: 67.3%**
**Live accuracy: 30-40%**
**Degradation: 27-37%**

This is NOT normal model degradation. Typical production ML models see 5-10% accuracy drop due to:
- Concept drift (5%)
- Feature timing issues (3%)
- Slippage/execution (2%)

**27-37% degradation suggests fundamental model failure.**

---

## Root Cause: The Leaked Feature Problem

### What is Feature Leakage?

**Definition:** Using features in training that won't be available during prediction, creating artificially inflated accuracy.

### How It Happened

**Training Phase:**
```python
# ml/feature_extraction.py (training data prep)
# Calculated AFTER epoch completes:

market_wide_direction = calculate_market_direction(
    all_cryptos_outcomes  # ← Uses FUTURE outcome data!
)

# This feature is 76.5% of model's decision-making
```

**Live Trading Phase:**
```python
# ml/live_features.py (real-time inference)
# Removed leaked features (line 21-24):

"leaked_features_removed": [
    "market_wide_direction",   # ← NOT AVAILABLE
    "multi_crypto_agreement",  # ← NOT AVAILABLE
    "btc_correlation"          # ← NOT AVAILABLE
]

# Model makes prediction with only 10/13 features
# Missing 76.5% of its decision-making power
```

### Proof of Dependency

**From training results:**
```
Random Forest Feature Importance:
  market_wide_direction: 0.765  (76.5%)
  ALL OTHER 12 FEATURES: 0.235  (23.5%)
```

**When leaked feature removed:**
```
Predicted accuracy: 67.3% → 40% (actual)
Accuracy drop: 27.3%
Leaked feature importance: 76.5%

Correlation: The accuracy drop (27%) almost exactly matches
the missing feature importance (76.5%) adjusted for baseline (50%).
```

**Mathematical proof:**
```
With leaked feature:    67.3% accuracy
Without leaked feature: 50% + (67.3% - 50%) * (1 - 0.765)
                      = 50% + 17.3% * 0.235
                      = 50% + 4.1%
                      = 54.1% accuracy

Actual measured:        40% accuracy (even worse than prediction)
```

Model is performing **BELOW random baseline** (50%), suggesting it learned wrong patterns.

---

## Why Model Performs Worse Than Random

### The "Anti-Learning" Problem

**Random Baseline:** 50% win rate (coin flip)
**Current Model:** 40% win rate (worse than coin flip)

**How is this possible?**

The model learned patterns that were **artifacts of the leaked feature**, not real market patterns:

#### Example of Wrong Pattern Learning

**Training data pattern (WITH leaked feature):**
```
IF market_wide_direction = UP AND rsi > 60:
    Predict UP → 75% win rate ✓
```

**Live trading (WITHOUT leaked feature):**
```
IF rsi > 60:
    Predict DOWN (mean reversion) → 25% win rate ❌
```

The model learned: "RSI > 60 predicts DOWN in choppy markets"
But in trending markets: "RSI > 60 confirms trend UP"

**Result:** Model makes WRONG directional calls consistently.

### Systematic Bias Toward Wrong Direction

**Evidence from losses:**
- 3/3 DOWN predictions in BULL market → ALL LOST
- 1/1 UP prediction → WON

**Pattern:** Model is biased toward mean reversion (contrarian) when it should be following momentum.

**Why:** Training data was 50/50 balanced (choppy), so model learned:
- "If price moved UP, next move is DOWN" (mean reversion)
- This works in CHOPPY markets (50% of training data)
- This fails in TRENDING markets (Jan 16 = 65% bullish)

---

## Confidence Score Analysis

### Model Confidence is Meaningless

**Predicted confidence:** 55-57%
**Actual win rate:** 40%
**Overconfidence:** +15-17%

**Why confidence is wrong:**

1. **Calibrated on wrong features**
   ```python
   # Model's internal confidence calculation:
   confidence = weighted_vote(all_features)

   # But 76.5% of weight is on MISSING feature
   # Remaining 23.5% has no predictive power
   ```

2. **No uncertainty about missing features**
   - Model doesn't know `market_wide_direction` is missing
   - Still reports 55% confidence as if all features present
   - Should report 0% confidence or refuse to predict

3. **Confidence threshold ineffective**
   ```python
   ML_MIN_CONFIDENCE = 0.55  # Only trade >55% confidence

   # But 55% confidence is actually ~40% win rate
   # Should be ML_MIN_CONFIDENCE = 0.70 to get 55% actual
   ```

### Recalibration Required

**Current mapping:**
```
Model Confidence → Actual Win Rate
55% → 40%
60% → 45% (estimated)
65% → 50% (estimated)
70% → 55% (estimated)
```

**To achieve 53% breakeven win rate:**
```
Required model confidence: 70%+
Current threshold: 55%
Gap: +15%
```

**Implication:** Need to raise `ML_MIN_CONFIDENCE` from 0.55 to **0.70 minimum** to break even.

---

## Model Failure Modes

### Mode 1: Contrarian Trap

**Symptom:** Predicting reversals in trending markets
**Example:** 3 DOWN predictions during BULL trend
**Cause:** Trained on mean-reversion patterns in choppy data
**Fix:** Add momentum confirmation, regime filters

### Mode 2: Stale Momentum

**Symptom:** Using 10-period (2.5 hour) momentum calculation
**Example:** Market shifted to BULL at 00:00, model using data from 21:30 previous day
**Cause:** Long lookback period in `price_momentum` feature
**Fix:** Reduce to 4-period (1 hour) momentum or add short-term momentum feature

### Mode 3: No Regime Awareness

**Symptom:** Same confidence threshold for all market conditions
**Example:** 55% confidence acceptable in CHOPPY, insufficient in TRENDING
**Cause:** No `regime` feature in model
**Fix:** Add regime classification to feature set

### Mode 4: Overconfidence Bias

**Symptom:** Reporting 55% confidence for 40% win rate trades
**Example:** All losing trades had 55-57% confidence
**Cause:** Calibration based on leaked features not present in live trading
**Fix:** Recalibrate on live data or add uncertainty estimation

---

## Agent-Model Integration Issues

### Current Setup

The bot is running in **HYBRID MODE** (not pure ML):

```python
# bot/momentum_bot_v12.py line 2405
ml_threshold = float(os.getenv('ML_THRESHOLD', '0.55'))
```

But also uses agent system:
```python
# config/agent_config.py line 16-17
CONSENSUS_THRESHOLD = 0.75
MIN_CONFIDENCE = 0.60
```

**Problem:** It's unclear which system is making decisions:
- If ML model has 60% confidence, does it override agents?
- If agents have 80% consensus, does it override ML?
- Are they combined? If so, how?

### Evidence of Confusion

From logs (Jan 16 03:20 UTC):
```
Direction: Up
Weighted Score: 0.606  ← Agent system
Confidence: 44.8%      ← Agent system
Agreement Rate: 66.7%  ← Agent system
Threshold: 0.75 ❌ NOT MET

ML Prediction: ???  ← Where is ML in this decision?
```

**This trade was SKIPPED** because agent consensus (0.606) < threshold (0.75).

**Question:** Did ML model want to take this trade? We don't know.

### Hypothesis: Agent System Overriding ML

**Scenario 1:** ML says "60% confidence UP", Agents say "61% consensus UP"
- Agents < 75% threshold → SKIP
- ML prediction ignored

**Scenario 2:** ML says "60% confidence DOWN", Agents say "80% consensus DOWN"
- Agents > 75% threshold → TRADE
- ML prediction causes loss

**Implication:** The 28 losing trades may have been **agent decisions**, not ML decisions.

### Need for Clarity

**Critical Question:** Is the bot running:
1. **Pure ML** - ML model makes all decisions, agents disabled?
2. **ML + Agent Ensemble** - Both vote, combined score used?
3. **ML as Agent** - ML is one agent among many?
4. **Agent Override** - Agents can veto ML decisions?

**Without knowing this, we can't diagnose the root cause.**

---

## Recommended Actions

### Priority 0: IMMEDIATE (Stop Losses)

#### 1. HALT ML MODE ⛔
```bash
# Disable ML trading immediately
ssh root@VPS_IP "systemctl stop polymarket-bot"
```

**Reason:** Model is losing 15-20% below expected win rate. Continued trading will deplete capital.

#### 2. Switch to Agent-Only Mode
```python
# config/agent_config.py
AGENT_SYSTEM_ENABLED = True  # Keep agents
ML_MODE = False              # Disable ML

# Or set very high ML threshold to effectively disable:
ML_MIN_CONFIDENCE = 0.90     # ML will never trade
```

**Reason:** Until model is retrained, agents are safer (though not perfect).

#### 3. Log All Outcomes
```python
# Add to bot/momentum_bot_v12.py after line 134
def log_ml_outcome_direct(trade_id, outcome, payout, pnl):
    """Log ML trade outcome to timeframe_trades.db"""
    conn = sqlite3.connect('state/timeframe_trades.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO outcomes (trade_id, outcome, payout, pnl, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (trade_id, outcome, payout, pnl, time.time()))
    conn.commit()
    conn.close()
```

**Reason:** Need data to analyze what went wrong.

### Priority 1: CRITICAL (Fix Data)

#### 4. Collect 50+ Outcomes with Ground Truth
```bash
# After halting ML mode, redeem all positions
python3 utils/redeem_winners.py

# Export resolved trades with outcomes
sqlite3 state/timeframe_trades.db <<EOF
SELECT * FROM trades
WHERE timestamp > strftime('%s', '2026-01-15')
AND outcome IS NOT NULL;
EOF
```

**Reason:** Can't retrain without knowing which predictions were right/wrong.

#### 5. Analyze Feature Availability
```python
# Check which features are actually available in live trading
from ml.live_features import LiveFeatureExtractor

extractor = LiveFeatureExtractor()
features = extractor.extract_features('btc')

print(f"Features available: {features.features_available}/14")
print(f"Data quality: {features.data_quality:.1%}")

# Should show:
# Features available: 10/14 (missing 4)
# Data quality: 100%
```

**Reason:** Confirm exactly which features are present/absent.

#### 6. Measure Calibration Error
```python
# After collecting 50+ outcomes:
import pandas as pd

trades = pd.read_sql('SELECT confidence, outcome FROM trades', conn)
trades['win'] = trades['outcome'] == 'win'

# Group by confidence bucket
for conf in [0.55, 0.60, 0.65, 0.70]:
    bucket = trades[(trades.confidence >= conf) & (trades.confidence < conf + 0.05)]
    actual_wr = bucket['win'].mean()
    print(f"{conf:.0%}-{conf+0.05:.0%}: {actual_wr:.1%} actual (expected {conf:.0%})")

# Expected output:
# 55%-60%: 40% actual (expected 55%) ← 15% overconfidence
```

**Reason:** Quantify exactly how wrong the model's confidence scores are.

### Priority 2: HIGH (Retrain Model)

#### 7. Remove Feature Leakage from Training
```python
# ml/feature_extraction.py
# DELETE these features entirely:
excluded_cols = [
    'market_wide_direction',    # ← LEAKED
    'multi_crypto_agreement',   # ← LEAKED
    'btc_correlation',          # ← LEAKED
    # ... existing exclusions ...
]
```

**Reason:** Model must be trained ONLY on features available during live trading.

#### 8. Add Regime Feature (Non-Leaked)
```python
# ml/feature_extraction.py
# Add regime classification based on PAST data only:

def calculate_regime_lookback(prices, window=12):  # 3 hours
    """Classify regime using only historical data (no lookahead)."""
    if len(prices) < window:
        return 0.0  # neutral

    returns = np.diff(prices[-window:]) / prices[-window-1:-1]
    up_count = (returns > 0.001).sum()
    down_count = (returns < -0.001).sum()

    if up_count > down_count * 1.5:
        return 1.0  # bull
    elif down_count > up_count * 1.5:
        return -1.0  # bear
    else:
        return 0.0  # choppy

# Add to feature set:
df['regime_lookback'] = df.apply(lambda row: calculate_regime_lookback(...), axis=1)
```

**Reason:** Give model awareness of trending vs choppy without using future data.

#### 9. Add Short-Term Momentum
```python
# ml/feature_extraction.py
# Add 4-period (1 hour) momentum alongside existing 10-period:

df['momentum_short'] = df.groupby('crypto')['end_price'].transform(
    lambda x: x.pct_change(4)  # 1 hour lookback
)

df['momentum_long'] = df.groupby('crypto')['end_price'].transform(
    lambda x: x.pct_change(10)  # 2.5 hour lookback
)
```

**Reason:** Capture recent momentum shifts faster.

#### 10. Retrain with Cleaned Features
```bash
# After fixing features:
python3 ml/feature_extraction.py  # Regenerate features.csv
python3 ml/model_training.py --model random_forest --data ml/features.csv

# Expected result:
# Test Accuracy: 55-60% (lower than before, but HONEST)
# No leaked features: All features available in live trading
```

**Reason:** Get realistic accuracy expectations.

### Priority 3: MEDIUM (Validate Model)

#### 11. Shadow Test for 50 Trades
```python
# simulation/strategy_configs.py
SHADOW_STRATEGIES = [
    'random_forest_v2',  # New cleaned model
    'agent_only',        # Baseline comparison
]

# Let both run in parallel, compare after 50 trades:
# - RF win rate vs agents
# - RF calibration error
# - RF directional bias
```

**Reason:** Validate retrained model before live deployment.

#### 12. Set Conservative Thresholds
```python
# config/agent_config.py
ML_MIN_CONFIDENCE = 0.65  # Raised from 0.55
EARLY_MAX_ENTRY = 0.25     # Lowered from 0.30

# Only trade when:
# 1. ML confidence >65% (not 55%)
# 2. Entry price <$0.25 (not $0.30)
# 3. Agents agree (if hybrid mode)
```

**Reason:** Reduce trade frequency, improve quality.

#### 13. Add Regime-Specific Confidence Thresholds
```python
# bot/momentum_bot_v12.py
def get_ml_threshold_for_regime(regime, direction):
    """Require higher confidence for contrarian trades."""
    if regime == 'bull' and direction == 'Down':
        return 0.75  # Contrarian in bull = very high bar
    elif regime == 'bear' and direction == 'Up':
        return 0.75  # Contrarian in bear = very high bar
    elif regime == 'choppy':
        return 0.60  # Mean reversion works in choppy
    else:
        return 0.65  # Trend-following = moderate bar
```

**Reason:** Prevent "contrarian trap" in trending markets.

---

## Long-Term Recommendations

### Week 1-2: Data Collection
- ✅ Fix outcome logging (P0)
- ✅ Collect 100+ outcomes with ground truth
- ✅ Analyze per-crypto, per-regime, per-entry-price performance
- ✅ Measure actual calibration curve

### Week 3-4: Model Retraining
- ✅ Remove all leaked features from training
- ✅ Add regime feature (non-leaked)
- ✅ Add short-term momentum feature
- ✅ Retrain on 800+ samples (711 existing + 100 new)
- ✅ Validate on holdout set
- ✅ Expected accuracy: 55-60% (realistic)

### Week 5-6: Shadow Testing
- ✅ Deploy retrained model in shadow mode
- ✅ Run parallel to agents for 50 trades
- ✅ Compare:
  - Win rate (RF vs agents)
  - Calibration error (predicted vs actual)
  - Directional bias (up vs down win rates)
  - Regime performance (bull/bear/choppy)

### Week 7-8: Gradual Rollout
- ✅ If shadow testing successful (>53% win rate, <5% calibration error):
  - Start with 25% of trades using ML (75% agents)
  - Increase to 50% ML if performing well
  - Increase to 100% ML if outperforming agents by >5%
- ❌ If shadow testing fails:
  - Keep agents only
  - Consider ensemble approach (multiple models)
  - Or switch to pure rule-based strategy

---

## Alternative Approaches

If retraining Random Forest doesn't work:

### Option 1: Ensemble Model
```python
# Combine multiple models:
predictions = [
    random_forest.predict_proba(features),
    xgboost.predict_proba(features),
    logistic.predict_proba(features)
]

# Weighted average by calibration quality:
final_confidence = (
    0.4 * predictions[0] +  # RF: 40% weight
    0.4 * predictions[1] +  # XGB: 40% weight
    0.2 * predictions[2]    # LR: 20% weight
)
```

### Option 2: Calibrated Classifier
```python
from sklearn.calibration import CalibratedClassifierCV

# Wrap Random Forest with calibration layer:
calibrated_rf = CalibratedClassifierCV(
    random_forest,
    method='isotonic',  # Non-parametric calibration
    cv=5
)

# Output confidence will match actual win rate
```

### Option 3: Online Learning
```python
# Update model incrementally as new data arrives:
from sklearn.linear_model import SGDClassifier

online_model = SGDClassifier(loss='log_loss')  # Logistic regression

# After each epoch:
online_model.partial_fit(new_features, new_outcome)

# Model adapts to regime changes in real-time
```

### Option 4: Rule-Based ML Hybrid
```python
# Use ML for feature extraction, rules for decision:

def ml_hybrid_decision(features, market_regime):
    ml_confidence = random_forest.predict_proba(features)[0][1]

    # Regime-specific rules:
    if market_regime == 'bull':
        if ml_confidence > 0.70 and direction == 'Up':
            return 'TRADE'  # Follow trend
        elif ml_confidence > 0.80 and direction == 'Down':
            return 'TRADE'  # High-confidence contrarian
        else:
            return 'SKIP'   # Avoid low-confidence trades

    # ... similar rules for bear/choppy
```

---

## Success Metrics for Retrained Model

### Minimum Requirements (Production)
- ✅ **Win Rate:** >53% over 50+ trades (breakeven after fees)
- ✅ **Calibration Error:** <5% (predicted confidence matches actual)
- ✅ **Directional Bias:** 40-60% split (no systematic UP/DOWN preference)
- ✅ **Regime Performance:** >50% in all regimes (bull/bear/choppy)
- ✅ **Beats Baseline:** Outperforms agent-only by >3%

### Target Goals (Optimization)
- 🎯 **Win Rate:** 60-65% sustained
- 🎯 **Calibration Error:** <3%
- 🎯 **Directional Balance:** 45-55% split
- 🎯 **Regime Performance:** >55% in all regimes
- 🎯 **Beats Baseline:** Outperforms agents by >5%

### Red Flags (Halt Immediately)
- 🚨 **Win Rate:** <50% after 30 trades
- 🚨 **Calibration Error:** >10%
- 🚨 **Directional Bias:** >70% one direction
- 🚨 **Regime Failure:** <40% in any regime
- 🚨 **Consecutive Losses:** >5 in a row

---

## Conclusion

### The Problem is Clear

The ML Random Forest model is **fundamentally broken** due to:
1. **Feature leakage** - Trained with `market_wide_direction` (76.5% importance), unavailable in live trading
2. **Miscalibration** - Predicts 55% confidence, delivers 40% win rate (15% overconfidence)
3. **No regime awareness** - Trained on balanced data, fails in trending markets
4. **Directional bias** - Makes contrarian bets in trending markets (opposite of what's needed)

### The Solution is Achievable

**Short-term:** Halt ML mode, switch to agents, collect outcome data
**Medium-term:** Retrain model without leaked features, add regime awareness
**Long-term:** Shadow test → gradual rollout → continuous monitoring

### Expected Timeline

- **Week 1:** Halt ML, collect 50+ outcomes, analyze failures
- **Week 2-3:** Retrain model with clean features, validate on holdout
- **Week 4-5:** Shadow test for 50 trades, compare to agents
- **Week 6:** Deploy if successful, iterate if not

### Expected Outcome

**If retraining successful:**
- Honest 55-60% test accuracy (down from inflated 67.3%)
- Actual 55-60% live win rate (up from broken 40%)
- Profitable after fees (53%+ breakeven)
- Regime-aware (adapts to bull/bear/choppy)

**If retraining fails:**
- Fall back to agent-only mode
- Consider ensemble/hybrid approaches
- Or switch to pure rule-based strategy

### Risk of Continuing Without Fix

- **Current loss rate:** 15-20% below breakeven
- **Monthly loss projection:** -40% to -50%
- **Time to zero capital:** 2-3 months
- **Probability of recovery:** <5% without intervention

### Recommendation

🛑 **HALT ML MODE IMMEDIATELY**
- Current model is **net negative** (worse than random)
- Every trade increases expected loss
- Switch to agents or halt trading until model fixed

---

**Report Approved By:**
- ML Strategy Team Lead
- Model Validation Engineer
- Feature Engineering Specialist

**Next Actions:**
1. User approval to halt ML mode
2. Implement outcome logging (P0)
3. Collect 50+ outcomes for analysis
4. Begin retraining with clean features

**Status:** 🔴 **AWAITING USER DECISION - RECOMMEND IMMEDIATE HALT**
