# Performance Optimization PRD - Polymarket AutoTrader

## Executive Summary

**Current State (Jan 15, 2026):**
- Balance: $254.61
- Win Rate: 56-60% (above 53% breakeven)
- ML Random Forest bot operational
- 7 agents deployed: Tech, Sentiment, Regime, Candlestick, TimePattern, OrderBook, FundingRate
- Shadow testing: 27 strategies running in parallel

**Goal:** Optimize existing system performance through data-driven improvements

**Timeline:** 4 weeks (4 phases)

**Target Metrics:**
- Win Rate: 60-65% (from 56%)
- Monthly ROI: +20-30% (from +10-20%)
- Automated optimization: Continuous

---

## Current Architecture

### ML Bot
- Algorithm: Random Forest Classifier
- Test Accuracy: 67.3%
- Live Win Rate: 56-60%
- Features: 14 engineered features (price momentum, volatility, orderbook, regime)

### Agent System
- **TechAgent:** Price confluence across exchanges (Binance, Kraken, Coinbase)
- **SentimentAgent:** Contrarian fade on overpriced sides (>70%)
- **RegimeAgent:** Market regime detection (BULL/BEAR/CHOPPY)
- **CandlestickAgent:** 15-minute candlestick patterns
- **TimePatternAgent:** Intra-epoch timing signals
- **OrderBookAgent:** Bid/ask spread and depth analysis
- **FundingRateAgent:** Perpetual swap funding rates

### Shadow Testing System
- 27 parallel strategies running
- Virtual trading (no real money risk)
- Real-time performance comparison
- Database: `simulation/trade_journal.db` (SQLite)

### Position Sizing
- Current: Fixed tiers (5-15% based on balance)
- Next: Kelly Criterion (mathematically optimal)

### Trading Thresholds
- Current: 0.75 consensus, 0.60 confidence
- Next: Test 0.80/0.70 for higher selectivity

---

## Phase 1: Per-Agent Performance Tracking (Week 1)

### Goal
Identify which of the 7 agents contribute positively vs negatively to win rate.

### Tasks
1. Create `analytics/agent_performance_tracker.py`
2. Extend `simulation/trade_journal.py` schema
3. Add agent enable/disable flags to `config/agent_config.py`
4. Query and analyze agent performance
5. Disable underperforming agents (<50% win rate)

### Success Metrics
- [ ] Tracking system operational (100+ trades logged)
- [ ] 1-2 underperforming agents identified and disabled
- [ ] Win rate improves by 1-2% after disabling bad agents

### Expected Impact
+2-3% win rate improvement by removing low-performing agents.

---

## Phase 2: Selective Trading Enhancement (Week 2)

### Goal
Test higher thresholds (0.80/0.70) to reduce trade frequency but increase win rate.

### Tasks
1. Add "ultra_selective" strategy to `simulation/strategy_configs.py`
2. Shadow test over 100+ trades
3. Compare metrics: win rate, trade frequency, Sharpe ratio, drawdown
4. If validated (win rate ≥65%, Sharpe ≥1.5): promote to live (staged 25% → 50% → 100%)
5. If not validated: keep current thresholds, document learnings

### Success Metrics
- [ ] Shadow strategy tested (100+ trades)
- [ ] If validated: win rate 65%+, 5-10 trades/day
- [ ] If not: keep current thresholds

### Expected Impact
5-10 trades/day at 65%+ win rate (vs 15-20 trades/day at 56-60%).

---

## Phase 3: Kelly Criterion Position Sizing (Week 3)

### Goal
Implement mathematically optimal position sizing based on edge.

### Tasks
1. Create `bot/position_sizer.py` with Kelly Criterion logic
2. Integrate into `Guardian.calculate_position_size()` in `bot/momentum_bot_v12.py`
3. Shadow test Kelly sizing vs fixed sizing (100+ trades)
4. Compare: ROI, Sharpe ratio, max drawdown, bankroll growth
5. If validated (20-30% higher ROI, same drawdown): promote to live

### Success Metrics
- [ ] Kelly sizing implemented and shadow tested (100+ trades)
- [ ] If validated: 20-30% higher ROI with same drawdown
- [ ] If not: keep fixed sizing, document learnings

### Expected Impact
+10-20% ROI improvement by betting more on high-confidence trades, less on low-confidence.

---

## Phase 4: Automated Optimization Infrastructure (Week 4)

### Goal
Build automated strategy promotion workflow + alert system for degradation.

### Tasks

#### 4A: Automated Strategy Promotion
1. Create `simulation/auto_promoter.py`
2. Logic: Auto-promote shadow strategies that beat live by 5%+ over 100 trades
3. Staged rollout: 25% → 50% → 100% allocation
4. Auto-rollback if win rate drops below 50%

#### 4B: Alert System
1. Create `analytics/alert_system.py`
2. Alerts:
   - Win rate drops below 50% (20-trade window)
   - Balance drops 20%+ from peak
   - Shadow strategy outperforms by 10%+ (100+ trades)
   - Daily loss exceeds $30 or 20% of balance
   - Agent consensus fails (all agents <30% confidence)
3. Notifications: Log to file + optional email/Slack webhook

### Success Metrics
- [ ] Auto-promotion logic operational
- [ ] Alert system preventing losses (caught ≥1 degradation event)
- [ ] Continuous optimization running (no manual intervention)
- [ ] Overall win rate: 60-65%
- [ ] Monthly ROI: +20-30%

### Expected Impact
Continuous optimization without manual work. Early warnings prevent catastrophic losses.

---

## Risk Management

### Shadow Testing Protocol
- All changes shadow tested first (100+ trades minimum)
- Statistical significance required (chi-square p<0.05)
- Staged rollout: 25% → 50% → 100%
- Auto-rollback if win rate drops below 50%

### Monitoring
- Daily win rate checks (20-trade rolling window)
- Balance tracking (alert on 20%+ drawdown)
- Shadow strategy performance comparison
- Per-agent contribution analysis

### Rollback Plan
- Keep old PRDs archived (can reference historical decisions)
- Git history preserves all iterations
- Config-driven changes (easy to revert via flags)
- Shadow testing prevents production breakage

---

## Success Criteria

### Week 1
- [ ] Per-agent tracking operational
- [ ] 100+ trades logged with agent attribution
- [ ] 1-2 underperforming agents identified and disabled
- [ ] Win rate improves by 1-2%

### Week 2
- [ ] Higher threshold strategy tested (100+ trades)
- [ ] If validated: win rate 65%+, fewer trades
- [ ] If not: keep current thresholds

### Week 3
- [ ] Kelly sizing tested (100+ trades)
- [ ] If validated: 20-30% higher ROI
- [ ] If not: keep fixed sizing

### Month End
- [ ] Overall win rate: 60-65% (from 56%)
- [ ] Monthly ROI: +20-30% (from +10-20%)
- [ ] Automated promotion working
- [ ] Alert system operational
- [ ] Shadow testing continuous (5-10 strategies)

---

## Open Questions (For Later)

1. Should we enable OnChain/Social agents after validating existing 7?
2. Are per-regime ML models worth the complexity?
3. What's the optimal shadow strategy count (27 now)?
4. Trade frequency vs quality - what's the optimal balance?

**Decision:** Address these AFTER completing 4-week optimization roadmap.
