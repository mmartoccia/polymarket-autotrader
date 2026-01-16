# ML Feature Leakage Analysis

**Date:** 2026-01-16
**Issue:** ML Random Forest model showing 67.3% test accuracy but only 40% live trading win rate
**Root Cause:** Feature leakage - using future information during training that's unavailable at prediction time

---

## Problem Summary

The ML Random Forest model was trained with 67.3% test accuracy on 711 samples, but in live trading it achieves only 40% win rate - **worse than random chance (50%)**. This PRD correctly identifies "feature leakage" as the cause.

## Feature Leakage Identified

### Location: `analysis/ml_feature_engineering.py` Lines 148-169

The `add_cross_crypto_features()` function creates features that **leak future information**:

```python
def add_cross_crypto_features(self, df: pd.DataFrame) -> pd.DataFrame:
    """Add features based on correlations between cryptos."""
    df = df.copy()

    # For each epoch, calculate how many cryptos went up
    epoch_summary = df.groupby('epoch').agg({
        'target': ['sum', 'mean'],  # ← LEAKAGE: Uses target (outcome)
        'change_pct': ['mean', 'std']
    }).reset_index()

    epoch_summary.columns = ['epoch', 'num_ups', 'pct_ups', 'avg_change_pct', 'std_change_pct']

    # Merge back
    df = df.merge(epoch_summary, on='epoch', how='left')

    # Consensus direction (1 if 3+ cryptos went up, 0 otherwise)
    df['market_consensus_up'] = (df['num_ups'] >= 3).astype(int)  # ← LEAKAGE

    # Market divergence (is this crypto going against the flow?)
    df['divergence'] = (df['target'] != df['market_consensus_up']).astype(int)  # ← LEAKAGE

    return df
```

### Why This is Leakage

**During Training:**
- For epoch X, the model sees:
  - `num_ups` = How many cryptos went Up in epoch X (uses `target` = actual outcome)
  - `market_consensus_up` = Did 3+ cryptos go Up in epoch X (uses actual outcomes)
  - `divergence` = Did this crypto go against the consensus (uses actual outcome)

**During Live Trading:**
- For epoch X, the bot tries to predict:
  - Will BTC go Up or Down? (outcome unknown)
  - How many cryptos will go Up? (unknown - we're predicting the FIRST crypto!)
  - What will the market consensus be? (unknown - outcomes haven't happened yet)

**The Problem:**
When predicting BTC at the START of epoch X, we don't know yet if ETH, SOL, XRP went Up or Down in epoch X. The model was trained thinking it would have access to this information (from the training data), but at prediction time this data doesn't exist yet.

### Why Training Accuracy is High (67.3%)

The model learned patterns like:
- "If 3+ cryptos went Up this epoch, predict Up" → This is circular logic!
- "If this crypto diverges from consensus, predict against the flow" → Uses the answer to predict the answer!

These features are **highly predictive in training** because they directly encode the outcome, but they're **completely unavailable during live trading**.

### Why Live Accuracy is Low (40%)

Without the leaked features, the model falls back on the remaining features:
- Time-based features (hour, day of week)
- RSI
- Volatility
- Rolling statistics

These features alone have weak predictive power (likely ~45-50% accuracy), but the model's decision boundaries were optimized assuming it would have the leaked features. When those features are missing or defaulted to 0, the model makes systematically worse decisions than random.

---

## Features Used in Live Trading

From `simulation/ml_strategy.py` lines 76-87, the live bot uses:

```python
self.feature_names = [
    'day_of_week',
    'minute_in_session',
    'epoch_sequence',
    'is_market_open',
    'rsi',
    'volatility',
    'price_momentum',
    'spread_proxy',
    'position_in_range',
    'price_z_score'
]
```

**Good News:** The live strategy correctly **excludes the leaked features**:
- ✅ Comment says: "Exclude leaked features (market_wide_direction, multi_crypto_agreement, btc_correlation)"
- ✅ Does NOT include `num_ups`, `market_consensus_up`, `divergence`

**Bad News:** The model was already trained WITH these features, so:
1. The model's decision boundaries are wrong
2. The model expects 10 features but was trained with ~30+ features
3. The feature importance/weights are calibrated for a different feature set

---

## Why Test Accuracy Was Misleading

The 67.3% test accuracy came from **time-series split validation** in training:

```python
# From ml_supervised_learning.py line 109
split_idx = int(len(X) * (1 - test_size))
X_train = X[:split_idx]
X_test = X[split_idx:]
```

Even though the split was time-based (not shuffled), **both train and test sets had the leaked features**. The model learned to rely on these features, which boosted test accuracy but doesn't transfer to live trading.

---

## Fix Options

### Option 1: Retrain Model Without Leaked Features (RECOMMENDED)

**Pros:**
- Clean solution - removes the root cause
- Model will be properly calibrated
- Test accuracy will reflect true live performance

**Cons:**
- Accuracy may drop to 52-55% (but this is REAL accuracy)
- Need to retrain, re-validate, re-deploy

**Steps:**
1. Modify `add_cross_crypto_features()` to remove:
   - `num_ups` (uses `target`)
   - `pct_ups` (uses `target`)
   - `market_consensus_up` (uses `target`)
   - `divergence` (uses `target`)
2. Keep only non-leaked cross-crypto features:
   - `avg_change_pct` (uses price changes, not outcomes)
   - `std_change_pct` (uses price changes, not outcomes)
3. Retrain Random Forest with clean feature set
4. Validate on holdout data (last 20% of epochs)
5. Shadow test for 24-48 hours before going live

**Expected Results:**
- Test accuracy: 52-56% (realistic)
- Live accuracy: 52-56% (matches test)
- Profitability: Marginal (need 53%+ to overcome fees)

### Option 2: Replace Cross-Crypto Features with Lagged Versions

**Pros:**
- Uses cross-crypto information (can be predictive)
- No leakage - uses only past epochs

**Cons:**
- More complex feature engineering
- Requires historical data for each prediction

**Implementation:**
```python
def add_lagged_cross_crypto_features(self, df: pd.DataFrame) -> pd.DataFrame:
    """Add cross-crypto features from PREVIOUS epochs only."""
    df = df.copy()

    # For each epoch, use data from PREVIOUS epoch
    epoch_summary = df.groupby('epoch').agg({
        'target': ['sum', 'mean'],
        'change_pct': ['mean', 'std']
    }).reset_index()

    # Shift forward by 1 epoch (so epoch X sees data from epoch X-1)
    epoch_summary[['num_ups', 'pct_ups', 'avg_change', 'std_change']] = \
        epoch_summary.groupby(df['crypto'])[['sum', 'mean', 'mean', 'std']].shift(1)

    # Now merge - each row sees ONLY previous epoch's data
    df = df.merge(epoch_summary[['epoch', 'num_ups', 'pct_ups', 'avg_change', 'std_change']],
                  on='epoch', how='left')

    return df
```

### Option 3: Use Agent System Instead (CURRENT APPROACH)

**Pros:**
- No retraining needed
- Agents have been debugged (16 bug fixes just applied)
- Agent system is explainable (ML is a black box)

**Cons:**
- Abandons ML work
- Agent win rate unknown (needs live testing)

**Status:** This is what US-BF-013 implemented:
```python
# config/agent_config.py
USE_ML_MODEL = False  # Disable broken ML model
```

---

## Recommendation

### Short-term (Immediate):
✅ **Keep ML disabled** (current state via US-BF-013)
- Agent system has been heavily debugged
- 16 critical fixes applied (bias removal, scoring fixes, Skip votes, etc.)
- Needs live validation before comparing to ML

### Medium-term (1-2 weeks):
📊 **Validate agent system performance**
- Shadow trading shows 27 strategies running
- Compare fixed agent system vs. pre-fix performance
- Target: 55-65% win rate (agent system)

### Long-term (2-4 weeks):
🔄 **Retrain ML model without leakage** (Option 1)
- If agent system underperforms (< 53% WR): ML worth retrying
- If agent system succeeds (> 55% WR): ML is lower priority
- Clean training data is valuable regardless (for future experiments)

**Why this order:**
1. Agent system already debugged and ready
2. ML model needs work (retraining, validation)
3. Better to have ONE working system than two broken systems
4. Can always add clean ML later if agent system succeeds

---

## Technical Details

### Feature Counts
- **Training:** ~30-40 features (varies by config)
- **Live:** 10 features (excludes leaked + other unavailable features)
- **Mismatch:** Model expects features in positions that don't exist

### Model Behavior
When the model receives 10 features but was trained on 30:
- Missing features are treated as 0 or default values
- Decision boundaries are in wrong feature space
- Predictions are effectively random or worse

### Confidence Calibration
Even if the model predicts "Up" with 67% confidence, this confidence was calibrated WITH leaked features. Without them, the true confidence might be 48% (below random).

---

## Verification Test

To confirm this diagnosis, try this experiment:

```python
# Load trained model
model = pickle.load('models/random_forest.pkl')

# Get feature importances
importances = model.feature_importances_
feature_names = [...]  # From training

# Check if leaked features are important
leaked_features = ['num_ups', 'market_consensus_up', 'divergence', 'pct_ups']
for name, importance in zip(feature_names, importances):
    if name in leaked_features:
        print(f"LEAKED: {name} = {importance:.3f}")
```

**Expected Result:**
Leaked features will show HIGH importance (> 0.10), confirming the model relies on them.

---

## Conclusion

**Feature leakage is confirmed** - the ML model cannot achieve 67.3% accuracy in live trading because it was trained with access to information (other cryptos' outcomes in the same epoch) that doesn't exist at prediction time.

**Current action (disabling ML) is correct.** Retraining with clean features is the proper fix, but should be prioritized based on agent system performance.

The good news: The code that **uses** the model (`ml_strategy.py`) already excludes the leaked features. The problem is the model itself was trained incorrectly. This is a **training data issue**, not a deployment issue.
