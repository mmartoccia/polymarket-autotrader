# ML Feature Documentation

**Version:** 1.0
**Last Updated:** 2026-01-15
**Source:** `ml/feature_extraction.py`
**Historical Data:** 2,884 epochs (Jan 7-14, 2026) → 711 usable samples after rolling calculations

---

## Overview

This document describes all 14 features extracted from historical epoch data for training ML models. Features are derived from `analysis/epoch_history.db` which tracks 15-minute crypto market outcomes.

**Feature Categories:**
- **Time Features (5):** Temporal patterns and market timing
- **Price Features (6):** Technical indicators and price dynamics
- **Cross-Asset Features (3):** Multi-crypto correlation and agreement

**Target Variable:**
- `target`: Binary classification (1 = UP, 0 = DOWN)
- Distribution: 51% UP, 49% DOWN (balanced)

---

## Time Features (5 features)

### 1. `hour`
**Type:** Integer (0-23)
**Category:** Time
**Description:** Hour of day when epoch occurred
**Purpose:** Capture time-of-day trading patterns
**Example:** 14 (2:00 PM UTC)
**Importance Rank:** Not shown in top 13 (likely <0.0001 or missing from report)
**Notes:** Market activity varies by hour (e.g., US market hours vs Asia hours)

### 2. `day_of_week`
**Type:** Integer (0-6)
**Category:** Time
**Description:** Day of week (Monday=0, Sunday=6)
**Purpose:** Capture weekly seasonality patterns
**Example:** 2 (Wednesday)
**Importance Rank:** 11/13 (0.0000 - negligible)
**Notes:** Crypto markets are 24/7, but traditional market days may influence behavior

### 3. `minute_in_session`
**Type:** Integer (0-1440)
**Category:** Time
**Description:** Minutes elapsed since midnight (start of trading session)
**Purpose:** Intra-day position tracking
**Example:** 840 (14:00 = 14*60)
**Importance Rank:** 9/13 (0.0088 = 0.88%)
**Notes:** Overlaps with `hour` feature; may be redundant

### 4. `epoch_sequence`
**Type:** Integer (0-N)
**Category:** Time
**Description:** Sequential epoch number per crypto (chronological ordering)
**Purpose:** Capture long-term trends and drift
**Example:** 721 (721st epoch for BTC)
**Importance Rank:** 8/13 (0.0101 = 1.01%)
**Notes:** Increases monotonically; may capture market regime changes over time

### 5. `is_market_open`
**Type:** Binary (0 or 1)
**Category:** Time
**Description:** Whether traditional US stock market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
**Purpose:** Detect periods with higher institutional activity
**Example:** 1 (market open)
**Importance Rank:** 10/13 (0.0019 = 0.19%)
**Calculation:**
```python
# Convert UTC to US Eastern Time
us_eastern = datetime.utcnow().astimezone(pytz.timezone('US/Eastern'))
is_market_open = (
    us_eastern.weekday() < 5 and  # Monday-Friday
    time(9, 30) <= us_eastern.time() <= time(16, 0)  # 9:30 AM - 4:00 PM
)
```

**Insight:** Time features contribute only **2.1%** total importance. Market dynamics (price/cross-asset) matter far more than timing.

---

## Price Features (6 features)

### 6. `rsi`
**Type:** Float (0-100)
**Category:** Price
**Description:** Relative Strength Index (14-period rolling average)
**Purpose:** Measure overbought/oversold conditions
**Example:** 68.5 (approaching overbought at 70)
**Importance Rank:** 4/13 (0.0277 = 2.77%)
**Calculation:**
```python
# Calculate gains and losses
delta = df['start_price'].diff()
gain = delta.where(delta > 0, 0).rolling(window=14).mean()
loss = -delta.where(delta < 0, 0).rolling(window=14).mean()

# Relative Strength
rs = gain / loss

# RSI formula
rsi = 100 - (100 / (1 + rs))
```
**Interpretation:**
- RSI > 70: Overbought (potential reversal to DOWN)
- RSI < 30: Oversold (potential reversal to UP)
- RSI 40-60: Neutral zone

### 7. `volatility`
**Type:** Float (0-1+)
**Category:** Price
**Description:** Rolling standard deviation of price returns (20-period)
**Purpose:** Measure market uncertainty and risk
**Example:** 0.015 (1.5% volatility)
**Importance Rank:** 7/13 (0.0145 = 1.45%)
**Calculation:**
```python
# Calculate percentage changes
returns = df['start_price'].pct_change()

# Rolling standard deviation
volatility = returns.rolling(window=20).std()
```
**Notes:** High volatility often precedes trend changes

### 8. `price_momentum`
**Type:** Float (-inf to +inf)
**Category:** Price
**Description:** Rate of change in price over 5 periods
**Purpose:** Detect acceleration/deceleration in price movement
**Example:** 0.025 (2.5% momentum)
**Importance Rank:** 5/13 (0.0253 = 2.53%)
**Calculation:**
```python
# Percentage change from 5 epochs ago
price_momentum = df['start_price'].pct_change(periods=5)
```
**Interpretation:**
- Positive momentum: Upward trend (potential UP continuation)
- Negative momentum: Downward trend (potential DOWN continuation)

### 9. `spread_proxy`
**Type:** Float (0-1)
**Category:** Price
**Description:** Proxy for bid-ask spread (approximated from price range)
**Purpose:** Estimate market liquidity and friction
**Example:** 0.012 (1.2% spread)
**Importance Rank:** 6/13 (0.0201 = 2.01%)
**Calculation:**
```python
# Use rolling price range as spread proxy
rolling_max = df['start_price'].rolling(window=10).max()
rolling_min = df['start_price'].rolling(window=10).min()

spread_proxy = (rolling_max - rolling_min) / df['start_price']
```
**Notes:** Wide spreads indicate low liquidity; narrow spreads indicate high liquidity

### 10. `position_in_range`
**Type:** Float (0-1)
**Category:** Price
**Description:** Current price position within 50-period high-low range
**Purpose:** Identify support/resistance levels
**Example:** 0.85 (price near top of range)
**Importance Rank:** 2/13 (0.0574 = 5.74%)
**Calculation:**
```python
# Rolling 50-period high and low
rolling_max = df['start_price'].rolling(window=50).max()
rolling_min = df['start_price'].rolling(window=50).min()

# Normalize position (0 = at low, 1 = at high)
position_in_range = (df['start_price'] - rolling_min) / (rolling_max - rolling_min)
```
**Interpretation:**
- Position > 0.8: Near resistance (potential reversal to DOWN)
- Position < 0.2: Near support (potential reversal to UP)
- Position ~0.5: Mid-range (neutral)

### 11. `price_z_score`
**Type:** Float (-inf to +inf)
**Category:** Price
**Description:** Z-score of price relative to 50-period mean/std
**Purpose:** Identify extreme price deviations (mean reversion opportunities)
**Example:** 2.1 (price is 2.1 standard deviations above mean)
**Importance Rank:** 3/13 (0.0355 = 3.55%)
**Calculation:**
```python
# Rolling 50-period mean and standard deviation
rolling_mean = df['start_price'].rolling(window=50).mean()
rolling_std = df['start_price'].rolling(window=50).std()

# Z-score formula
price_z_score = (df['start_price'] - rolling_mean) / rolling_std
```
**Interpretation:**
- Z-score > 2: Price extremely high (potential DOWN reversal)
- Z-score < -2: Price extremely low (potential UP reversal)
- Z-score near 0: Price at mean (neutral)

**Insight:** Price features contribute **18.1%** total importance. `position_in_range` and `price_z_score` are most predictive.

---

## Cross-Asset Features (3 features)

### 12. `btc_correlation`
**Type:** Float (-1 to +1)
**Category:** Cross-Asset
**Description:** Rolling 20-period correlation between crypto's price and BTC price
**Purpose:** Measure dependence on BTC movements
**Example:** 0.75 (strong positive correlation with BTC)
**Importance Rank:** 12/13 (0.0000 - negligible)
**Calculation:**
```python
# Pivot data to have each crypto as column
price_pivot = df.pivot_table(index='timestamp', columns='crypto', values='start_price')

# Calculate rolling correlation with BTC
for crypto in price_pivot.columns:
    if crypto != 'BTC':
        btc_correlation[crypto] = price_pivot[crypto].rolling(window=20).corr(price_pivot['BTC'])
    else:
        btc_correlation[crypto] = 1.0  # BTC always has 1.0 correlation with itself
```
**Notes:** BTC is the dominant crypto; altcoins often follow BTC trends

### 13. `multi_crypto_agreement`
**Type:** Float (0-1)
**Category:** Cross-Asset
**Description:** Percentage of cryptos moving in same direction
**Purpose:** Detect market-wide consensus
**Example:** 0.75 (75% of cryptos moving together)
**Importance Rank:** 13/13 (0.0000 - negligible)
**Calculation:**
```python
# For each timestamp, count how many cryptos moved UP vs DOWN
grouped = df.groupby('timestamp').agg({
    'direction': lambda x: (x == 'Up').sum() / len(x)  # % moving UP
})

# Map back to original dataframe
multi_crypto_agreement = df['timestamp'].map(grouped['direction'])
```
**Interpretation:**
- Agreement > 0.75: Strong market-wide trend
- Agreement < 0.25: Strong market-wide reversal
- Agreement ~0.5: Mixed/choppy market

### 14. `market_wide_direction`
**Type:** Integer (-1, 0, or 1)
**Category:** Cross-Asset
**Description:** Consensus direction across all cryptos
**Purpose:** Identify strong market-wide trends
**Example:** 1 (strong UP trend across all cryptos)
**Importance Rank:** 1/13 (0.7987 = **79.87%** - DOMINANT FEATURE)
**Calculation:**
```python
# Calculate agreement threshold (>75% = strong consensus)
agreement_threshold = 0.75

# Map multi_crypto_agreement to discrete direction
def classify_direction(agreement):
    if agreement >= agreement_threshold:
        return 1   # Strong UP consensus
    elif agreement <= (1 - agreement_threshold):
        return -1  # Strong DOWN consensus
    else:
        return 0   # Mixed/neutral

market_wide_direction = df['multi_crypto_agreement'].apply(classify_direction)
```
**Interpretation:**
- +1: 75%+ of cryptos moving UP (strong bull trend)
- -1: 75%+ of cryptos moving DOWN (strong bear trend)
- 0: Mixed market (no clear consensus)

**Critical Insight:** `market_wide_direction` alone accounts for **79.9%** of predictive power. When all cryptos move together, the trend is highly predictive. This suggests **cross-asset momentum** is the strongest signal.

---

## Feature Importance Summary

**Top 5 Features (97% of predictive power):**
1. `market_wide_direction` (79.87%) - Market-wide consensus
2. `position_in_range` (5.74%) - Price within support/resistance range
3. `price_z_score` (3.55%) - Mean reversion signal
4. `rsi` (2.77%) - Overbought/oversold indicator
5. `price_momentum` (2.53%) - Trend acceleration

**Category Breakdown:**
- **Cross-Asset:** 79.9% (dominated by market_wide_direction)
- **Price:** 18.1% (technical indicators)
- **Time:** 2.1% (minimal impact)

**Low-Importance Features (<2%):**
- `volatility` (1.45%)
- `epoch_sequence` (1.01%)
- `minute_in_session` (0.88%)
- `is_market_open` (0.19%)
- `day_of_week` (0.00%)
- `btc_correlation` (0.00%)
- `multi_crypto_agreement` (0.00%)

---

## Data Pipeline

### Source Data
- **Database:** `analysis/epoch_history.db`
- **Table:** `epoch_outcomes`
- **Columns:** id, crypto, epoch, date, hour, direction, start_price, end_price, change_pct, change_abs, timestamp
- **Raw Count:** 2,884 epochs (Jan 7-14, 2026)
- **Cryptos:** BTC, ETH, SOL, XRP

### Feature Engineering Steps
1. **Load raw epochs** from database (2,884 rows)
2. **Add time features** (5 features)
3. **Add price features** (6 features with rolling windows)
4. **Add cross-asset features** (3 features requiring pivot/merge)
5. **Drop NaN rows** (rolling windows create initial NaN values)
6. **Final output:** 711 usable samples (75% data loss from 50-period lookback)

### Train/Val/Test Split
- **Method:** Time-based split (no random shuffling to avoid lookahead bias)
- **Split Ratios:** 70% train / 15% validation / 15% test
- **Train:** 497 samples
- **Validation:** 107 samples
- **Test:** 107 samples

### Output Format
**CSV file:** `ml/training_data.csv`

**Columns:**
- Metadata: `id`, `crypto`, `date`, `direction`, `timestamp`
- Features: 14 feature columns (hour, day_of_week, ..., market_wide_direction)
- Target: `target` (1=UP, 0=DOWN)

---

## Known Issues & Future Improvements

### Current Issues
1. **Overfitting:** Random Forest achieves 100% accuracy on training data (memorizing patterns)
2. **Data Loss:** 75% of epochs lost due to 50-period rolling windows (2,884 → 711 samples)
3. **Feature Redundancy:** `multi_crypto_agreement` and `btc_correlation` have 0% importance
4. **Single Dominant Feature:** `market_wide_direction` accounts for 80% of predictions (model relies too heavily on one signal)

### Recommended Improvements
1. **Reduce lookback windows:** 50 → 20 periods to preserve more data
2. **Use min_periods in rolling():** Allow shorter windows initially (e.g., min_periods=10)
3. **Remove low-importance features:** Drop features with <1% importance to reduce noise
4. **Add agent vote features:** Integrate votes from 7 deployed agents (20+ features)
5. **Add regime features:** Current regime, regime stability, transitions (4 features)
6. **Add historical pattern features:** Recent win rate, streaks, time-of-day performance (10+ features)
7. **Regularization:** Use max_depth=6, min_samples_split=20 to prevent overfitting
8. **Walk-forward validation:** Time-series cross-validation instead of single train/val/test split
9. **Feature engineering:** Create interaction features (e.g., RSI * position_in_range)
10. **Target engineering:** Consider probability targets (0-1) instead of binary (0/1)

### Future Feature Expansions
**Goal:** Expand from 14 → 50+ features as outlined in PRD

**Phase 1 Agent Features (8 features):**
- `orderbook_confidence`, `orderbook_quality`
- `funding_rate_confidence`, `funding_rate_quality`
- `onchain_confidence`, `onchain_quality`
- `social_sentiment_confidence`, `social_sentiment_quality`

**Existing Agent Features (10 features):**
- `tech_confidence`, `tech_quality`
- `sentiment_confidence`, `sentiment_quality`
- `regime_confidence`, `regime_quality`
- `candlestick_confidence`, `candlestick_quality`
- `time_pattern_confidence`, `time_pattern_quality`

**Agent Agreement Features (3 features):**
- `agent_consensus` (% of agents agreeing on direction)
- `avg_agent_confidence` (mean confidence across all agents)
- `avg_agent_quality` (mean quality across all agents)

**Regime Features (4 features):**
- `current_regime` (bull/bear/sideways/volatile)
- `regime_stability` (how long in current regime)
- `regime_transition_recent` (recent regime change)
- `regime_confidence` (how certain about regime classification)

**Historical Performance Features (10 features):**
- `recent_win_rate_10`, `recent_win_rate_50` (rolling win rates)
- `consecutive_wins`, `consecutive_losses` (streak tracking)
- `hour_win_rate` (performance at this hour historically)
- `crypto_win_rate` (performance for this crypto)
- `regime_win_rate` (performance in this regime)
- `entry_price_bracket_win_rate` (performance at this entry price range)
- `drawdown_level` (current drawdown percentage)
- `recovery_mode` (normal/conservative/defensive)

---

## Usage Examples

### Load Features for Training
```python
from ml.feature_extraction import FeatureExtractor, FeatureConfig

# Initialize extractor
config = FeatureConfig(
    epoch_db_path='analysis/epoch_history.db',
    lookback_window=50
)
extractor = FeatureExtractor(config)

# Extract and engineer features
df = extractor.extract_all_epochs()
df = extractor.add_time_features(df)
df = extractor.add_price_features(df)
df = extractor.add_cross_asset_features(df)
df = extractor.add_target(df)
df = extractor.drop_nan(df)

# Save to CSV
df.to_csv('ml/training_data.csv', index=False)
```

### Load Features for Live Trading
```python
import pandas as pd

# Load trained feature engineering pipeline
df_train = pd.read_csv('ml/training_data.csv')

# For live trading, compute same features on current epoch
# Use same rolling windows, same calculations
# Ensure no lookahead bias (only use data available before epoch start)
```

### Get Feature Metadata
```python
from ml.feature_extraction import get_feature_columns

# Get list of feature columns (excludes metadata and target)
feature_cols = get_feature_columns()
# Returns: ['hour', 'day_of_week', ..., 'market_wide_direction']

# Use for model training
X = df[feature_cols]
y = df['target']
```

---

## References

- **PRD:** `PRD.md` - Product Requirements Document
- **Source Code:** `ml/feature_extraction.py`
- **Test Suite:** `tests/test_feature_extraction.py`
- **Feature Importance:** `ml/importance_report.txt`
- **Training Data:** `ml/training_data.csv` (711 samples)
- **Historical Epochs:** `analysis/epoch_history.db` (2,884 epochs)

---

**Document Status:** Complete
**Next Steps:** Create live trading feature extraction module, train ML models with regularization
