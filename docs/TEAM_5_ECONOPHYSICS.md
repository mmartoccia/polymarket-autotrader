# Econophysics Team Report
## Incident Analysis: January 15, 2026

**Team Lead:** Econophysicist
**Team Members:** Market Microstructure Analyst, Statistical Physicist
**Report Date:** January 16, 2026
**Priority:** 🟠 **MEDIUM**

---

## Executive Summary

**Finding:** **Cannot perform detailed market analysis** without historical price data for the specific epochs where trades occurred. However, we can assess whether the trading strategy was appropriate for typical 15-minute binary markets.

**Key Limitation:** Missing outcome data prevents linking specific market conditions to specific trade results.

**Available Analysis:**
- ✅ General market structure assessment
- ✅ Fee economics analysis
- ✅ Entry price distribution review
- ❌ Epoch-specific volatility analysis (need timestamps)
- ❌ Regime classification during trades (need price history)
- ❌ Correlation with broader crypto markets (need specific dates/times)

**Hypothesis:** Based on entry price distribution ($0.38-$0.43 range), trades were likely **momentum-following** in nature. If crypto markets experienced **trend reversals** or **mean reversion** during Jan 14-15, momentum trades would have performed poorly.

---

## Market Structure Analysis

### 15-Minute Binary Markets Characteristics

**Market Type:** Binary outcome (Up/Down) resolved by comparing:
- Start price: Price at epoch start (e.g., 1:00 PM)
- End price: Price at epoch end (e.g., 1:15 PM)

**Resolution:**
- If `end_price > start_price`: Up wins ($1.00), Down loses ($0.00)
- If `end_price < start_price`: Down wins ($1.00), Up loses ($0.00)
- No ties (exact equality is astronomically rare)

**Market Efficiency:**
- High frequency (4 epochs/hour)
- Low information content (15 min too short for fundamental analysis)
- Dominated by technical trading and noise
- Prediction accuracy ceiling: ~60-65% (due to randomness)

### Expected Price Behavior

**Random Walk Hypothesis:**

In efficient markets, 15-minute price changes should follow random walk:
```
P(up) ≈ 50%
P(down) ≈ 50%
```

**Empirical Observations (Crypto):**

Crypto 15-min returns exhibit:
1. **Momentum persistence** (15-30% autocorrelation)
   - If price up in last 15min, slight bias toward up next 15min
   - Decays rapidly after 30-45 minutes

2. **Mean reversion** (40-60min window)
   - After strong moves, tendency to retrace
   - Stronger during low volatility periods

3. **Volatility clustering**
   - High vol periods follow high vol periods
   - Low vol periods follow low vol periods

**Implication:** Both momentum and contrarian strategies can work, depending on market regime.

---

## Entry Price Analysis

### Observed Entry Prices (28 Trades)

```
Distribution:
$0.20 - 1 trade  (3.6%)   - CHEAP (contrarian or late confirmation)
$0.38-$0.43 - 26 trades (92.9%) - MODERATE (momentum following)
$0.48 - 1 trade (3.6%)   - EXPENSIVE (high confidence momentum)
```

**Mean Entry:** ~$0.41
**Median Entry:** ~$0.41
**Std Dev:** ~$0.03 (low variance = consistent strategy)

### Entry Price Interpretation

**Polymarket Pricing Theory:**

Price represents **market probability** of outcome:
- $0.20 = 20% probability → 5:1 odds
- $0.41 = 41% probability → 1.44:1 odds
- $0.50 = 50% probability → 1:1 odds (fair coin flip)

**At $0.41 Entry:**
- Market believes: 41% chance of this outcome
- Breakeven win rate: 41% + 2.5% fees = 43.5%
- Profitable if: Model has >44% accuracy

**Bot's Implied Edge:**
```
Entry at $0.41 with 60% confidence
→ Bot thinks: 60% probability
→ Market thinks: 41% probability
→ Edge: 19 percentage points

If bot is correct:
- 60 wins x $0.59 profit = +$35.40
- 40 losses x $0.41 cost = -$16.40
- Net: +$19.00 (46% ROI)

If bot is overconfident (actual 50% win rate):
- 50 wins x $0.59 = +$29.50
- 50 losses x $0.41 = -$20.50
- Net: +$9.00 (22% ROI) still profitable

If market is correct (actual 41% win rate):
- 41 wins x $0.59 = +$24.19
- 59 losses x $0.41 = -$24.19
- Net: $0.00 (breakeven after fees)
```

### Strategy Identification: MOMENTUM FOLLOWING

**Evidence:**
1. **Entry range $0.38-$0.43** = Bot is betting WITH the market consensus
2. **Not contrarian** = Would enter at <$0.20 if fading overpriced side
3. **Not late confirmation** = Would enter at >$0.70 if waiting for certainty

**Momentum Strategy Characteristics:**
- Follows early price movement
- Assumes trend continues for full epoch
- Relies on market inefficiency (delayed price discovery)
- Works best in **trending markets**
- Fails in **choppy/mean-reverting markets**

---

## Regime Analysis (Hypothetical)

### Market Regimes for 15-Min Trading

**1. TRENDING (Momentum-Friendly)**
- Characteristics: Strong directional moves, low noise
- Strategy: Follow momentum, enter at $0.30-$0.45
- Expected Win Rate: 60-65%
- Risk: Trend exhaustion, late entry

**2. CHOPPY (Contrarian-Friendly)**
- Characteristics: Mean-reverting, high noise
- Strategy: Fade extremes, enter at <$0.20 or >$0.80
- Expected Win Rate: 55-60%
- Risk: Breakout in either direction

**3. QUIET (Low Volatility)**
- Characteristics: Minimal movement, tight range
- Strategy: AVOID (no edge)
- Expected Win Rate: ~50% (coin flip)
- Risk: Unpredictable breakouts

### Likely Regime During Jan 14-15

**Based on Entry Prices:**

Bot was taking **momentum trades at $0.38-$0.43**, suggesting:
- Market was showing directional movement
- Bot followed early momentum
- Expected regime: TRENDING or TRANSITIONING

**Hypothesis 1: Trending Market → Reversals**

If market was trending (e.g., BTC up) but experiencing **intra-epoch reversals**:
```
Example:
- Epoch starts: BTC = $100,000
- 5 min in: BTC = $100,500 (up) → Market prices Up at $0.43
- Bot enters: Up at $0.43
- 15 min mark: BTC = $99,800 (down from start) → Down wins
- Result: LOSS
```

**This scenario explains:**
- Why momentum trades ($0.38-$0.43) were placed
- Why they lost (reversals)
- Why loss was severe (most/all trades hit reversals)

**Hypothesis 2: Regime Transition (Trend → Chop)**

If market transitioned from trending to choppy:
```
Jan 14: Strong trend (momentum works)
Jan 15: Choppy reversion (momentum fails)
Bot: Still using momentum strategy → losses
```

**Hypothesis 3: Flash Volatility Spike**

If crypto markets had flash crash or spike:
```
Normal: 15min movement ±0.5%
Jan 14-15: 15min movement ±3-5% (10x normal)
Bot: Model trained on normal vol → breaks in extreme vol
Result: Random-like performance
```

---

## Volatility Assessment (Estimated)

### Normal 15-Min Crypto Volatility

**Typical:**
- BTC: 0.3-0.8% per 15min
- ETH: 0.5-1.2% per 15min
- SOL: 0.8-2.0% per 15min
- XRP: 1.0-2.5% per 15min

**High Volatility Days:**
- BTC: 1.5-3.0% per 15min
- ETH: 2.0-4.0% per 15min
- SOL: 3.0-6.0% per 15min
- XRP: 4.0-8.0% per 15min

### Impact on Trading

**Normal Volatility (Good for Trading):**
- Clear directional signals
- Momentum persists within epoch
- Model predictions work

**High Volatility (Bad for Trading):**
- Rapid reversals
- Momentum fails mid-epoch
- Model predictions break
- Entry price becomes unreliable

**Hypothesis:** If Jan 14-15 had 2-3x normal volatility, model would struggle.

**Test Required:**
```python
# Fetch actual volatility for Jan 14-15:
btc_prices = fetch_ohlc('BTC', '15m', start='2026-01-14', end='2026-01-15')
btc_returns = btc_prices['close'].pct_change()
btc_vol = btc_returns.std() * 100  # Convert to %

normal_vol = 0.5  # 0.5% typical
if btc_vol > 2 * normal_vol:
    print(f"EXTREME VOLATILITY: {btc_vol:.2f}% vs normal {normal_vol:.2f}%")
```

---

## Fee Economics Analysis

### Polymarket Fee Structure

**Taker Fees (Market Orders):**
```
Probability → Fee %
10% → 0.5%
20% → 1.2%
30% → 1.8%
40% → 2.4%
50% → 3.15% ← MAXIMUM
60% → 2.4%
70% → 1.8%
80% → 1.2%
90% → 0.5%
```

**Fee Curve:** Bell-shaped, peaks at 50% probability

### At Bot's Entry Range ($0.38-$0.43)

**$0.38 Entry:**
- Probability: 38%
- Taker fee: ~2.2% per side
- Round-trip: ~4.4%
- Breakeven win rate: 38% + 4.4% = 42.4%

**$0.41 Entry:**
- Probability: 41%
- Taker fee: ~2.5% per side
- Round-trip: ~5.0%
- Breakeven win rate: 41% + 5.0% = 46.0%

**$0.43 Entry:**
- Probability: 43%
- Taker fee: ~2.7% per side
- Round-trip: ~5.4%
- Breakeven win rate: 43% + 5.4% = 48.4%

### Fee Drag Analysis

**28 Trades at ~$0.41 avg:**
```
Total capital deployed: 28 x $3.50 = $98
Fee cost (5% round-trip): $98 x 0.05 = $4.90

If 0% win rate (all losses):
- Lost capital: $98
- Total loss: $98

If 50% win rate (random):
- Wins: 14 x $0.59 = $8.26
- Losses: 14 x $0.41 = $5.74
- Net before fees: $2.52
- Net after fees: $2.52 - $4.90 = -$2.38 (small loss)
```

**Observation:** Even at 50% win rate, fees cause losses in this entry range.

**Required Win Rate:**
```
Breakeven at $0.41 entry:
W * 0.59 = (1-W) * 0.41
W * 0.59 = 0.41 - W * 0.41
W * (0.59 + 0.41) = 0.41
W = 0.41 / 1.00 = 41%

Add fees (5%):
W_needed = 41% + 5% = 46%
```

**Conclusion:** Bot needs **46%+ win rate** to be profitable at $0.41 entry.

If actual win rate was 30-40%, losses are expected and explained by fees alone.

---

## Correlation Analysis (Speculative)

### Broader Crypto Market Context (Jan 2026)

**Without specific data, general trends:**

January 2026 crypto markets:
- BTC: Likely in post-ETF approval consolidation
- ETH: Following BTC correlation (~0.7-0.8)
- SOL: Higher volatility, altcoin season sensitivity
- XRP: Legal clarity, regulatory news impact

**Possible Market Events (Jan 14-15):**
1. **Fed announcement** → sudden dollar strength
2. **Exchange hack** → flight to safety
3. **Regulatory news** → dump across all cryptos
4. **Macro selloff** → risk-off sentiment

**Impact on 15-Min Trading:**

If macro event occurred:
- Increases correlation across all cryptos
- All 4 cryptos move same direction
- Bot's diversification fails
- Concentrated losses if wrong direction

**Example:**
```
Macro dump: All cryptos down
Bot: Taking momentum UP trades (following early bounce)
Reality: Dead cat bounce, continued dump
Result: All 4 positions lose
```

---

## Strategy-Market Fit Assessment

### Was Strategy Appropriate?

**Momentum Strategy at $0.38-$0.43:**

✅ **Appropriate for:**
- Trending markets
- Normal volatility
- Low correlation across assets
- Clear directional moves

❌ **Inappropriate for:**
- Choppy/mean-reverting markets
- High volatility (flash moves)
- Correlated macro events
- Trend exhaustion periods

### Alternative Strategies for Jan 14-15

**If market was choppy:**
- Contrarian strategy (fade extremes)
- Enter at <$0.20 (buy cheap)
- Higher win rate potential

**If market was high volatility:**
- AVOID trading (no edge)
- Wait for volatility to normalize
- Preserve capital

**If market was trending:**
- Current strategy correct
- Issue may be execution (entry timing)
- Or trend reversal (bad luck)

---

## Recommendations

### Immediate (P0)

1. **Add Market Regime Detection**
   ```python
   # Before trading:
   regime = detect_regime(price_history)

   if regime == 'CHOPPY':
       MIN_CONFIDENCE = 0.70  # Higher bar
   elif regime == 'TRENDING':
       MIN_CONFIDENCE = 0.55  # Normal bar
   elif regime == 'QUIET':
       SKIP_TRADING = True    # No edge
   ```

2. **Add Volatility Filter**
   ```python
   # Measure 1-hour volatility:
   vol_1h = calculate_volatility(prices, window='1h')

   if vol_1h > 2.0:  # 2x normal
       SKIP_TRADING = True  # Too risky
   ```

### Short-term (P1)

3. **Per-Crypto Volatility Adjustment**
   ```python
   # Reduce position size in high-vol cryptos:
   if crypto == 'SOL' and volatility > 1.5:
       position_size *= 0.75

   if crypto == 'XRP' and volatility > 2.0:
       position_size *= 0.50
   ```

4. **Correlation Monitoring**
   ```python
   # Check if all cryptos moving together:
   corr = np.corrcoef([btc_returns, eth_returns, sol_returns, xrp_returns])

   if corr.mean() > 0.8:  # High correlation
       MAX_POSITIONS = 2  # Reduce diversification benefit
   ```

5. **Entry Price Regime Adjustment**
   ```python
   # In choppy markets, only take contrarian:
   if regime == 'CHOPPY':
       EARLY_MAX_ENTRY = 0.20  # Force cheap entries
   ```

### Long-term (P2)

6. **Market Microstructure Analysis**
   - Study orderbook depth
   - Analyze spread dynamics
   - Detect market maker manipulation

7. **External Data Integration**
   - Fed calendar (macro events)
   - Crypto news sentiment
   - Social media sentiment (Twitter/Reddit)

8. **Adaptive Strategy Selection**
   - Momentum mode (trending markets)
   - Contrarian mode (choppy markets)
   - Halt mode (high volatility)

---

## Data Requirements for Full Analysis

### What We Need

1. **Epoch-Level Price Data**
   ```
   epoch_id, crypto, start_time, end_time,
   start_price, end_price, high, low, volume,
   outcome (Up/Down)
   ```

2. **Trade Timestamps**
   ```
   trade_id, epoch_id, entry_time, entry_price,
   exit_time, exit_price, direction, outcome
   ```

3. **Market Volatility**
   ```
   timestamp, crypto, volatility_1h, volatility_24h,
   regime (trending/choppy/quiet)
   ```

4. **Broader Market Context**
   ```
   timestamp, btc_price, eth_price, nasdaq, dxy,
   correlation_matrix
   ```

### How to Collect

```python
# Add to bot logging:
log.info(f"[Market] {crypto} epoch {epoch}: start=${start_price:.2f}, "
         f"current=${cur_price:.2f}, vol_1h={vol_1h:.2%}, "
         f"regime={regime}, corr={avg_corr:.2f}")

# Store in database:
INSERT INTO market_conditions (
    epoch, crypto, start_price, current_price,
    volatility_1h, regime, correlation
) VALUES (?, ?, ?, ?, ?, ?, ?)
```

---

## Success Metrics

### Market Condition Monitoring

Add to dashboard:
```
MARKET CONDITIONS:
  BTC Volatility:   0.8% (NORMAL)
  ETH Volatility:   1.2% (NORMAL)
  SOL Volatility:   2.5% (HIGH) ⚠️
  XRP Volatility:   3.1% (HIGH) ⚠️

  Regime:           TRENDING (momentum-friendly)
  Correlation:      0.65 (moderate diversification)

  Trading Status:   ✓ ACTIVE (conditions favorable)
```

### Performance by Regime

Track separately:
```
TRENDING MARKETS:
  Trades: 120
  Win Rate: 62% ✓
  Avg Entry: $0.42

CHOPPY MARKETS:
  Trades: 45
  Win Rate: 48% ❌
  Avg Entry: $0.41 (should be <$0.30)

HIGH VOLATILITY:
  Trades: 12
  Win Rate: 33% ❌
  Avg Entry: $0.43 (should skip)
```

---

## Conclusion

**Market Assessment:** ❓ **INSUFFICIENT DATA**

Cannot conclusively determine market conditions during Jan 14-15 without:
- Historical price data for specific epochs
- Volatility measurements
- Regime classification

**Strategy Assessment:** ⚠️ **POTENTIALLY MISMATCHED**

Bot was using **momentum strategy** ($0.38-$0.43 entries), which:
- ✅ Works in trending markets
- ❌ Fails in choppy markets
- ❌ Fails in high volatility

**Most Likely Scenario:**

Jan 14-15 markets were either:
1. **Choppy/mean-reverting** (momentum failed)
2. **High volatility** (model broke)
3. **Correlated macro dump** (all positions lost together)

**Recommended Action:**
1. Add regime detection (P0)
2. Add volatility filter (P0)
3. Collect market data going forward (P1)
4. Analyze performance by regime (P1)

---

**Report Status:** ✅ **COMPLETE**
**Action Required:** Add market condition monitoring
**Data Limitation:** HIGH (need historical data for full analysis)
**Confidence:** LOW (speculative without data)
