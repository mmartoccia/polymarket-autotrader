# Win Rate by Entry Price Bucket Analysis

**Generated:** 2026-01-16 13:44:57
**Persona:** James "Jimmy the Greek" Martinez (Market Microstructure Specialist)
**Data Source:** bot.log

---

## Executive Summary

**Total Trades Analyzed:** 0
**Overall Win Rate:** 0.0%
**Optimal Entry Range:** N/A (0.0% WR, n=0)
**Statistical Significance:** INSUFFICIENT_DATA (χ² = 0.00, p 1.0)

**⚠️ VERDICT:** Insufficient data for statistical testing. Need ≥5 trades per bucket.

---

## Win Rate by Entry Price Bucket

| Entry Price Bucket | Total Trades | Wins | Losses | Win Rate | Sample Entries |
|-------------------|--------------|------|--------|----------|----------------|

**Overall:** 0 trades, 0W/0L, 0.0% win rate

---

## Statistical Significance Test (Chi-Square)

**Hypothesis:**
- H0: Win rate is independent of entry price bucket
- H1: Win rate depends on entry price bucket

**Results:**
- Chi-square statistic: 0.00
- P-value: 1.0
- Conclusion: INSUFFICIENT_DATA

**Interpretation:** Insufficient sample size. Need ≥5 trades per bucket for chi-square test validity.

---

## Optimal Entry Range

**Best Performing Bucket:** N/A
**Win Rate:** 0.0%
**Sample Size:** 0 trades

**Recommendation:** Insufficient data. Need ≥10 trades per bucket for reliable recommendation.

---

## Recommendations

### Data Collection Phase
1. **Collect more data** - Need ≥50 trades per bucket for reliable analysis
2. **Re-run analysis monthly** - Statistical tests require adequate sample size

---

## Methodology

**Data Sources:**
- Trade log: bot.log
- Parsed trades: ORDER PLACED + WIN/LOSS messages (fuzzy matched)

**Analysis Steps:**
1. Extract all trades with entry price and outcome
2. Group trades by entry price bucket ($0.05 increments)
3. Calculate win rate per bucket
4. Perform chi-square test for statistical significance
5. Identify optimal entry range (highest win rate, n ≥ 10)

**Statistical Test:**
- Chi-square test for independence
- Significance level: α = 0.05
- Minimum sample size: 5 trades per bucket

**Limitations:**
- Assumes independence of trades (may not hold if markets are non-stationary)
- Chi-square requires adequate sample size (≥5 per bucket)
- Does not account for confounding variables (crypto type, strategy, regime)
