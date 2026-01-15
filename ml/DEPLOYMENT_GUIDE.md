# ML Model Deployment Guide

**Date:** 2026-01-15
**Status:** ✅ Models Trained, ⚠️ Shadow Testing Required
**Best Model:** Random Forest (67.3% test accuracy, +17.3% edge)

---

## Executive Summary

We've successfully trained baseline ML models on 711 historical samples and are ready to deploy them in **shadow mode only** for validation. The Random Forest model shows a strong 17.3% edge over random baseline on the test set (67.3% vs 50.0%).

**CRITICAL:** Models are NOT deployed to live bot. All trading is virtual (shadow mode) with zero real money risk.

---

## What Was Built

### 1. Models Trained

**Random Forest (RECOMMENDED):**
- Test Accuracy: 67.3%
- Precision: 62.1%
- Recall: 73.5%
- ROC AUC: 0.713
- Edge: +17.3% over baseline
- Status: ✅ Ready for shadow testing

**Logistic Regression:**
- Test Accuracy: 56.1%
- Precision: 54.5%
- Recall: 24.5%
- ROC AUC: 0.617
- Edge: +6.1% over baseline
- Status: ⚠️ Underperforms Random Forest (low recall)

### 2. Data Leakage Fixed

**Critical Issue Resolved:**
- Original features.csv had 3 leaked features with perfect 1.0 correlation to target
- Removed: market_wide_direction, multi_crypto_agreement, btc_correlation
- Result: Realistic 67.3% accuracy (vs fake 100% before)

### 3. Shadow Trading Integration

**Files Created:**
- `simulation/ml_strategy.py` - ML prediction engine
- `ml/models/random_forest_baseline.pkl` - Trained RF model
- `ml/models/logistic_regression_baseline.pkl` - Trained LogReg model
- `ml/models/scaler.pkl` - Feature scaler for LogReg
- `ml/models/model_metadata.json` - Training metadata

**Shadow Strategies Added:**
- `ml_random_forest_50` - Trade all predictions (≥50% win prob)
- `ml_random_forest_55` - Selective trading (≥55% win prob)
- `ml_random_forest_60` - High confidence only (≥60% win prob)

### 4. Documentation

- `ml/feature_importance_clean.txt` - Feature analysis report
- `ml/training_report.txt` - Model training summary
- `ml/DEPLOYMENT_GUIDE.md` - This file

---

## Current Status: NOT Live

**Shadow Mode Only:**
- ✅ ML strategies configured in `config/agent_config.py`
- ✅ Strategy definitions added to `simulation/strategy_configs.py`
- ✅ ML prediction engine created (`simulation/ml_strategy.py`)
- ⚠️ **NOT deployed to VPS yet** (local integration only)
- ⚠️ **NOT making real trades** (shadow testing required)

**Next Step:** Deploy to VPS and let shadow system collect 50+ virtual trades over 24-48h.

---

## How Shadow Testing Works

### 1. Shadow Trading System Architecture

```
Live Bot (existing agent consensus)
       ↓
Market Data Broadcast
       ↓
Shadow Strategies (including ML models)
       ↓
Virtual Trades Executed
       ↓
Outcomes Resolved After Epoch
       ↓
SQLite Database Logging (trade_journal.db)
       ↓
Performance Comparison Reports
```

### 2. ML Strategy Flow

```
Market Data → Feature Extraction → ML Model Prediction → Trade Decision
                                   (win probability)     (if prob > threshold)
```

**Feature Extraction:**
- 10 clean features (no data leakage)
- Price features: RSI, volatility, momentum, spread, position_in_range, z_score
- Time features: day_of_week, minute_in_session, epoch_sequence, is_market_open

**Prediction:**
- Random Forest outputs win probability (0-1)
- Trade if probability ≥ threshold (50%, 55%, or 60%)
- Direction: Up or Down (based on cheaper side)

**Execution:**
- Virtual trade only (no real money)
- Logged to trade_journal.db
- Tracked alongside other shadow strategies

### 3. Monitoring

**Live Dashboard:**
```bash
python3 simulation/dashboard.py
```

**CLI Analysis:**
```bash
# Compare all strategies
python3 simulation/analyze.py compare

# View ML strategy details
python3 simulation/analyze.py details --strategy ml_random_forest_55

# Recent decisions
python3 simulation/analyze.py decisions --limit 50
```

**Export Data:**
```bash
# Export performance metrics
python3 simulation/export.py performance -o ml_results.csv

# Export ML strategy trades
python3 simulation/export.py trades --strategy ml_random_forest_55 -o ml_trades.csv
```

---

## Deployment Steps (VPS)

### Step 1: Deploy Code to VPS

```bash
# Local: Commit and push changes
git add .
git commit -m "Add ML shadow strategies (Random Forest 67.3% test accuracy)"
git push origin main

# SSH to VPS
ssh root@216.238.85.11

# Pull latest code
cd /opt/polymarket-autotrader
git pull origin main

# Restart bot service (to reload config)
systemctl restart polymarket-bot
```

### Step 2: Verify ML Models Loaded

```bash
# Check if models exist
ls -lh ml/models/
# Should see:
#   random_forest_baseline.pkl (17KB)
#   logistic_regression_baseline.pkl (4KB)
#   scaler.pkl (2KB)
#   model_metadata.json (2KB)

# Test ML strategy
python3 simulation/ml_strategy.py
# Should output:
#   ✓ ML strategies loaded and tested successfully
```

### Step 3: Monitor Shadow Trading

```bash
# Check shadow database
sqlite3 simulation/trade_journal.db "SELECT COUNT(*) FROM trades WHERE strategy LIKE 'ml_%';"

# Live dashboard
python3 simulation/dashboard.py

# Check bot logs for ML activity
tail -f bot.log | grep -E "ML|ml_random"
```

### Step 4: Wait for Data (24-48h)

- Let bot run for 24-48 hours
- ML strategies will make virtual trades
- Target: 50+ resolved trades per strategy
- No user intervention needed

---

## Success Criteria (Shadow Testing)

### Minimum Requirements for Live Promotion

✅ **Win Rate:** >53% over 50+ shadow trades (breakeven after 6.3% fees)
✅ **Statistical Significance:** Chi-square p<0.05 vs random_baseline
✅ **ROI:** Positive after fees
✅ **Max Drawdown:** <25%
✅ **Consistency:** No 7+ consecutive losses
✅ **Beats Agents:** Outperforms default strategy by >3%

### Ideal Targets

🎯 **Win Rate:** 60-65% (sustained over 100+ trades)
🎯 **ROI:** +15-25% monthly
🎯 **Max Drawdown:** <20%
🎯 **Sharpe Ratio:** >1.0

### If ANY Minimum Fails

❌ **Do NOT promote to live**
❌ Keep in shadow mode for more data
❌ Re-train with additional features
❌ Consider model ensemble or hyperparameter tuning

---

## Analysis After 50+ Trades

### Compare Models

```bash
python3 simulation/analyze.py compare
```

**Expected Output:**
```
Rank   Strategy                  Trades   W/L      Win Rate   Total P&L
--------------------------------------------------------------------------------
1      ml_random_forest_55       52       35W/17L  67.3%      $+18.45
2      default (LIVE)            50       28W/22L  56.0%      $+8.20
3      random_baseline           48       20W/28L  41.7%      $-3.50
```

### Statistical Validation

```python
from scipy.stats import chi2_contingency

# ML strategy results
ml_wins = 35
ml_losses = 17

# Random baseline results
random_wins = 20
random_losses = 28

# Chi-square test
observed = [[ml_wins, ml_losses], [random_wins, random_losses]]
chi2, p_value = chi2_contingency(observed)[:2]

print(f"Chi-square: {chi2:.4f}")
print(f"P-value: {p_value:.4f}")

if p_value < 0.05:
    print("✅ Statistically significant improvement")
else:
    print("❌ Not statistically significant")
```

### Decision Tree

```
IF win_rate > 53% AND p_value < 0.05:
    → Promote to 25% of live bets
    → Monitor for 100 trades
    → If stable, increase to 50%, then 100%

ELIF win_rate > 50% AND p_value < 0.10:
    → Continue shadow testing (collect more data)
    → Need 100+ trades for stronger significance

ELSE:
    → Do NOT promote to live
    → Analyze failure modes
    → Consider retraining or feature engineering
```

---

## Troubleshooting

### Issue: ML Strategy Not Trading

**Check 1: Model loaded correctly**
```bash
python3 simulation/ml_strategy.py
# Should NOT show errors
```

**Check 2: Strategy enabled in config**
```bash
grep "ml_random_forest" config/agent_config.py
# Should be in SHADOW_STRATEGIES list
```

**Check 3: Feature extraction working**
```bash
# Check bot logs for feature errors
grep -i "feature" bot.log | tail -20
```

### Issue: 0% Win Rate

**Likely Cause:** Feature extraction timing issue (using future data)

**Fix:** Verify features extracted PRE-EPOCH:
- Check `ml/live_features.py` implementation
- Ensure no lookahead bias (peeking at outcomes)
- Compare training feature_extraction.py vs live_features.py

### Issue: Predictions Always Same Direction

**Likely Cause:** Feature values out of expected range

**Fix:** Log feature values during prediction:
```python
# In ml_strategy.py
log.info(f"Features: {features}")
log.info(f"Win Prob: {win_prob:.2f}")
```

Compare logged features to training data ranges in features.csv

---

## Model Retraining

### When to Retrain

- ⚠️ Win rate drops below 50% for 50+ trades
- ⚠️ Concept drift detected (market conditions changed)
- ⚠️ Weekly retraining recommended if deployed live

### Retraining Steps

1. **Collect new data:**
   ```bash
   # Export recent trade outcomes
   python3 ml/feature_extraction.py --update
   ```

2. **Re-run feature importance:**
   ```bash
   python3 ml/feature_importance.py --input ml/features_updated.csv
   ```

3. **Train new models:**
   ```bash
   # Backup old models
   mv ml/models ml/models_backup_$(date +%Y%m%d)

   # Train fresh models
   python3 ml/model_training.py --input ml/features_updated.csv
   ```

4. **Deploy and shadow test:**
   ```bash
   # Deploy to VPS
   ./scripts/deploy.sh

   # Monitor for 50+ trades before promoting
   ```

---

## Risk Management

### Guardrails in Place

1. **Shadow Testing Mandatory:**
   - All ML trades are virtual until validated
   - Zero real money risk during testing
   - Minimum 50 trades required for promotion

2. **Staged Rollout:**
   - Phase 1: Shadow only (0% live exposure)
   - Phase 2: 25% allocation if passing validation
   - Phase 3: 50% allocation after 50 trades
   - Phase 4: 100% allocation after 100 trades

3. **Automated Rollback:**
   - Win rate < 45% (rolling 20 trades) → alert
   - Win rate < 40% (rolling 20 trades) → auto-rollback
   - Drawdown > 25% → halt and alert
   - 7+ consecutive losses → reduce position sizing 50%

4. **Conservative Live Config:**
   - Keep existing agent consensus as primary
   - ML as secondary strategy (if promoted)
   - Never 100% ML without agent backup

### What Can Go Wrong

**Overfitting:**
- Test accuracy (67.3%) may not hold in live trading
- Real-world: expect 60-65% win rate (still profitable)

**Concept Drift:**
- Markets change over time
- Model trained on Jan 7-15 data may degrade
- Re-train weekly if live performance drops

**Execution Timing:**
- Features must be extracted PRE-EPOCH (no future data)
- Any timing mismatch = model will fail completely
- Test feature extraction timing carefully

**Fee Impact:**
- Round-trip fees ~6.3% at 50% probability
- 67.3% test accuracy → ~60% realized (after fees/slippage)
- Still profitable but lower than backtest

---

## Summary

### ✅ What's Ready

1. Random Forest model trained (67.3% test accuracy)
2. Data leakage fixed (realistic performance)
3. Shadow trading integration complete
4. ML strategies configured
5. Monitoring tools ready

### ⚠️ What's Pending

1. Deploy to VPS (git push + pull)
2. Collect 50+ shadow trades (24-48h wait)
3. Statistical validation
4. Decision on live promotion

### 🎯 Expected Outcome

If shadow testing validates 60-65% live win rate:
- Monthly ROI: +15-25%
- Edge over agents: +5-10%
- Breakeven after fees: Comfortably above 53%

**Next Action:** Deploy to VPS and monitor shadow performance for 24-48 hours.

---

## Questions & Support

**Slack:** #polymarket-autotrader
**GitHub:** https://github.com/mmartoccia/polymarket-autotrader/issues
**Docs:** This file + `ml/training_report.txt` + `ml/feature_importance_clean.txt`

---

**Generated:** 2026-01-15
**Author:** Claude Sonnet 4.5
**Version:** 1.0
