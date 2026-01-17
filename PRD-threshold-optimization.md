# PRD: Threshold Optimization - Agent Reweighting & Rapid Testing

## Executive Summary

**Problem:** Bot is correctly identifying trade direction but skipping signals due to consensus scores just below threshold (0.75-0.82 range). Agents are finding the right signals, but scoring/weighting may be miscalibrated.

**Strategic Approach:** Two-track parallel approach
1. **Agent Reweighting** (immediate) - Boost weights of accurate agents to improve signal scores
2. **Rapid Threshold Testing** (4-6 hours) - Shadow test 5 threshold variants with rapid data collection

**Timeline:** 1 day (not 7 days - rapid iteration based on 4 trades every 15 minutes)

**Data Collection Rate:**
- 4 cryptos × 4 epochs/hour = 16 decision points per hour
- Target: 50 decisions per threshold variant
- Required time: 50 ÷ 16 = ~3-4 hours of data collection
- Total timeline: 4-6 hours for complete experiment

---

## Background

**Current State:**
- Consensus threshold: 0.82
- Min confidence: 0.65
- 6 active agents (down from 11)
- Observed: Agents identifying correct direction, but scores 0.75-0.82 (just below threshold)

**Research Team Consensus:**
- Alex Rousseau: "Fix signal quality before lowering bar" → agent reweighting
- Team: Shadow test multiple thresholds before production change
- Sarah Chen: Need 30+ samples per variation for statistical significance
- Amara Johnson: Avoid reactive threshold changes, validate first

**Key Insight:** With 4 cryptos × 4 epochs/hour = 16 data points/hour, we can collect 50+ samples in 3-4 hours (not 7 days).

---

## User Stories

### US-TO-001: Analyze Agent Vote Accuracy
**Priority:** HIGH (prerequisite for reweighting)
**Estimated Time:** 2 hours

**Problem:**
Need to identify which agents are most accurate to inform reweighting decisions.

**Acceptance Criteria:**
- [x] 1. Create `scripts/analyze_agent_accuracy.py`
- [x] 2. Parse `bot.log` or `simulation/trade_journal.db` for agent votes
- [x] 3. Calculate per-agent accuracy:
  - When agent votes UP, how often does market go UP?
  - When agent votes DOWN, how often does market go DOWN?
  - Overall accuracy % per agent
- [x] 4. Generate report:
  ```
  Agent Performance Report
  ========================
  RegimeAgent:     78% accurate (45/58 votes correct)
  RiskAgent:       65% accurate (38/58 votes correct)
  GamblerAgent:    62% accurate (36/58 votes correct)
  TimePatternAgent: 55% accurate (32/58 votes correct)
  OrderBookAgent:  48% accurate (28/58 votes correct) ← DISABLE?
  FundingRateAgent: 51% accurate (30/58 votes correct)
  ```
- [x] 5. Identify agents with >70% accuracy (candidates for weight boost)
- [x] 6. Identify agents with <53% accuracy (candidates for disabling)

**Files to Create:**
- `scripts/analyze_agent_accuracy.py`

**Output:**
- `reports/agent_accuracy_analysis.md` (performance summary)
- `reports/agent_accuracy.csv` (raw data)

**Testing:**
- Run: `python3 scripts/analyze_agent_accuracy.py --source bot.log --trades 100`
- Validate: Accuracy percentages sum correctly, sample size sufficient

---

### US-TO-002: Implement Agent Reweighting Based on Accuracy
**Priority:** HIGH
**Estimated Time:** 1 hour

**Problem:**
High-accuracy agents should have more influence on consensus score.

**Acceptance Criteria:**
- [x] 1. Read `reports/agent_accuracy_analysis.md` from US-TO-001
- [x] 2. Update `config/agent_config.py` → `AGENT_WEIGHTS`:
  ```python
  # OLD (equal weights):
  AGENT_WEIGHTS = {
      'RegimeAgent': 1.0,
      'RiskAgent': 1.0,
      'GamblerAgent': 1.0,
      # ...
  }
  
  # NEW (accuracy-based weights):
  AGENT_WEIGHTS = {
      'RegimeAgent': 1.5,      # 78% accurate → boost
      'RiskAgent': 1.2,        # 65% accurate → slight boost
      'GamblerAgent': 1.0,     # 62% accurate → baseline
      'TimePatternAgent': 0.8, # 55% accurate → reduce
      'OrderBookAgent': 0.0,   # 48% accurate → disable
      'FundingRateAgent': 0.5, # 51% accurate → reduce
  }
  ```
- [x] 3. Formula: `weight = 1.0 + (accuracy - 0.60) * 2.0`
  - Example: 78% accuracy → 1.0 + (0.78 - 0.60) * 2.0 = 1.36 ≈ 1.5
  - Example: 48% accuracy → 1.0 + (0.48 - 0.60) * 2.0 = 0.76 ≈ 0.0 (disable)
- [x] 4. Add comment: `# US-TO-002: Weights adjusted based on per-agent accuracy analysis`
- [x] 5. Bot imports without errors
- [x] 6. Consensus scores should increase for signals with high-accuracy agent agreement

**Files to Modify:**
- `config/agent_config.py`

**Expected Impact:**
- Signals previously at 0.78 may jump to 0.85+ (with high-accuracy agent agreement)
- Trade frequency may increase 10-20% (borderline signals now pass threshold)
- Win rate should improve (trusting more accurate agents)

**Testing:**
- Import test: `python3 -c "import bot.momentum_bot_v12"`
- Monitor: Compare consensus scores before/after reweighting
- Validate: High-accuracy agents have more influence on final score

---

### US-TO-003: Create Shadow Strategies for Rapid Threshold Testing
**Priority:** HIGH
**Estimated Time:** 1 hour

**Problem:**
Need to test 5 threshold variants in parallel with live bot to find optimal threshold.

**Acceptance Criteria:**
- [x] 1. Update `simulation/strategy_configs.py` with 5 new strategies:
  ```python
  # Test Strategy 1: Moderate lower (0.80)
  STRATEGY_LIBRARY['threshold_0.80'] = StrategyConfig(
      name='threshold_0.80',
      description='Test 0.80 consensus threshold (10% lower than live)',
      consensus_threshold=0.80,
      min_confidence=0.63,
      agent_weights=<copy from live config>
  )
  
  # Test Strategy 2: Aggressive lower (0.78)
  STRATEGY_LIBRARY['threshold_0.78'] = StrategyConfig(
      name='threshold_0.78',
      description='Test 0.78 consensus threshold (5% lower than 0.80)',
      consensus_threshold=0.78,
      min_confidence=0.60,
      agent_weights=<copy from live config>
  )
  
  # Test Strategy 3: Very aggressive (0.75)
  STRATEGY_LIBRARY['threshold_0.75'] = StrategyConfig(
      name='threshold_0.75',
      description='Test 0.75 consensus threshold (original baseline)',
      consensus_threshold=0.75,
      min_confidence=0.58,
      agent_weights=<copy from live config>
  )
  
  # Test Strategy 4: Conditional on entry price
  STRATEGY_LIBRARY['conditional_entry'] = StrategyConfig(
      name='conditional_entry',
      description='Lower threshold (0.78) for cheap entries (<$0.15), else 0.82',
      consensus_threshold=0.78,  # Base threshold
      min_confidence=0.60,
      agent_weights=<copy from live config>,
      # Note: Conditional logic requires bot modification
  )
  
  # Test Strategy 5: Conditional on timing
  STRATEGY_LIBRARY['conditional_timing'] = StrategyConfig(
      name='conditional_timing',
      description='Lower threshold (0.78) for late epoch (>600s), else 0.82',
      consensus_threshold=0.78,  # Base threshold
      min_confidence=0.60,
      agent_weights=<copy from live config>,
      # Note: Conditional logic requires bot modification
  )
  ```
- [x] 2. Update `config/agent_config.py` → `SHADOW_STRATEGIES`:
  ```python
  SHADOW_STRATEGIES = [
      'default',              # Live strategy (0.82 threshold)
      'threshold_0.80',       # Test 1
      'threshold_0.78',       # Test 2
      'threshold_0.75',       # Test 3
      'conditional_entry',    # Test 4 (if implemented)
      'conditional_timing',   # Test 5 (if implemented)
  ]
  ```
- [x] 3. Verify shadow trading broadcasts decisions to all strategies
- [x] 4. Confirm database logs trades for all 6 strategies

**Files to Modify:**
- `simulation/strategy_configs.py`
- `config/agent_config.py`

**Testing:**
- Import test: `python3 -c "from simulation.strategy_configs import STRATEGY_LIBRARY"`
- Verify: 5 new strategies present in library
- Database check: `sqlite3 simulation/trade_journal.db "SELECT name FROM strategies"`

---

### US-TO-004: Collect Rapid Test Data (4-6 Hours)
**Priority:** CRITICAL
**Estimated Time:** 4-6 hours (passive data collection)

**Problem:**
Need 50+ decision points per strategy to validate threshold performance.

**Acceptance Criteria:**
- [x] 1. Deploy reweighted config + 5 shadow strategies to VPS
- [x] 2. Monitor data collection rate:
  ```bash
  # Check trades per strategy
  sqlite3 simulation/trade_journal.db "
    SELECT s.name, COUNT(t.id) as trades
    FROM strategies s
    LEFT JOIN trades t ON s.id = t.strategy_id
    GROUP BY s.name
    ORDER BY trades DESC
  "
  ```
- [x] 3. Target: 50+ resolved trades per strategy
- [x] 4. Data collection timeline:
  - Hour 1: ~16 decisions collected (4 cryptos × 4 epochs)
  - Hour 2: ~32 decisions collected
  - Hour 3: ~48 decisions collected
  - Hour 4: ~64 decisions collected ← SUFFICIENT
- [x] 5. Early stop if one strategy clearly dominates (>10% WR advantage after 30 trades)

**Data Quality Checks:**
- All 6 strategies receiving same market data (timestamps match)
- No missed epochs (data continuity)
- Outcomes resolving correctly (WIN/LOSS accurate)

**Monitoring Commands:**
```bash
# Watch collection rate (refresh every 5 minutes)
watch -n 300 'sqlite3 simulation/trade_journal.db "
  SELECT name, COUNT(*) FROM trades 
  JOIN strategies ON trades.strategy_id = strategies.id 
  GROUP BY name"'

# Dashboard (real-time)
python3 simulation/dashboard.py --interval 5
```

**Success Criteria:**
- 50+ trades per strategy within 6 hours
- No data gaps or errors
- Ready for statistical analysis (US-TO-005)

---

### US-TO-005: Analyze Rapid Test Results & Select Winner
**Priority:** CRITICAL
**Estimated Time:** 1 hour

**Problem:**
After 4-6 hours of data collection, determine which threshold performs best.

**Acceptance Criteria:**
- [x] 1. Run statistical analysis:
  ```bash
  python3 simulation/analyze.py compare \
    --strategies default,threshold_0.80,threshold_0.78,threshold_0.75 \
    --min-trades 50
  ```
- [x] 2. Generate comparison report:
  ```
  Strategy Performance Comparison (50+ trades each)
  ==================================================
  
  Strategy         Trades   Win Rate   Total P&L   Avg Entry   Significance
  -------------------------------------------------------------------------
  default (0.82)   52       58.0%      $+12.30     $0.19       BASELINE
  threshold_0.80   58       62.1%      $+18.45     $0.18       p=0.04 ✓
  threshold_0.78   64       59.4%      $+14.20     $0.17       p=0.21
  threshold_0.75   71       56.3%      $+8.90      $0.16       p=0.35
  
  WINNER: threshold_0.80 (62.1% WR, +4.1% vs live, p<0.05)
  ```
- [x] 3. Validation checks:
  - Winner must have ≥3% WR advantage over live
  - Statistical significance: p < 0.05
  - Consistent across regimes (not regime-dependent)
  - Entry price quality maintained (<$0.20 avg)
  - Directional balance acceptable (40-60%)
- [x] 4. If no clear winner (all within 2% WR), keep current threshold
- [x] 5. If winner found, proceed to US-TO-006 (production deployment)

**Files to Create:**
- `reports/threshold_optimization_results.md` (human-readable)
- `reports/threshold_optimization_results.csv` (data export)

**Testing:**
- Verify sample sizes sufficient (n≥50 per strategy)
- Check statistical test validity (Fisher's exact test or chi-squared)
- Validate significance calculations (p-value methodology)

---

### US-TO-006: Deploy Winning Threshold to Production
**Priority:** HIGH
**Estimated Time:** 30 minutes

**Problem:**
After validation, deploy winning threshold to live bot.

**Acceptance Criteria:**
- [x] 1. Verify winner from US-TO-005 (e.g., threshold_0.80)
- [x] 2. Update `config/agent_config.py`:
  ```python
  # OLD
  CONSENSUS_THRESHOLD = 0.82
  MIN_CONFIDENCE = 0.65
  
  # NEW (based on test results)
  CONSENSUS_THRESHOLD = 0.80  # US-TO-006: Validated via rapid testing (62.1% WR)
  MIN_CONFIDENCE = 0.63
  ```
- [x] 3. Add detailed comment documenting change:
  ```python
  # US-TO-006: Threshold optimized from 0.82 → 0.80 based on 4-hour shadow test
  # Test results (58 trades): 62.1% WR (+4.1% vs live), p=0.04, avg entry $0.18
  # Deployment date: 2026-01-16
  # Rollback trigger: If WR drops below 58% over 50 trades, revert to 0.82
  ```
- [x] 4. Commit changes:
  ```bash
  git add config/agent_config.py
  git commit -m "feat: US-TO-006 - Optimize threshold to 0.80 (validated 62.1% WR)"
  git push origin main
  ```
- [x] 5. Deploy to VPS:
  ```bash
  ssh root@216.238.85.11 "cd /opt/polymarket-autotrader && ./scripts/deploy.sh"
  ```
- [x] 6. Monitor for 24 hours:
  - Win rate: Should maintain 60-62% (validated range)
  - Trade frequency: +10-20% vs before (expected)
  - No errors or system issues

**Rollback Plan:**
- If WR drops below 58% over 50 trades:
  ```bash
  # Revert to 0.82
  git revert <commit-hash>
  ./scripts/deploy.sh
  ```

**Files to Modify:**
- `config/agent_config.py`

**Success Metrics:**
- Threshold updated to validated value
- Production bot using new threshold
- Performance monitored for degradation

---

## Timeline & Execution

### Parallel Track Approach

**Phase 1: Setup (Hours 0-2)**
- Execute US-TO-001: Analyze agent accuracy (2 hours)
- Execute US-TO-002: Implement agent reweighting (1 hour)
- Execute US-TO-003: Create shadow strategies (1 hour)
- Deploy to VPS, start data collection

**Phase 2: Data Collection (Hours 2-8)**
- US-TO-004: Passive data collection (4-6 hours)
- Bot runs autonomously with 6 strategies
- ~16 decision points per hour × 6 hours = 96 data points per strategy

**Phase 3: Analysis & Deployment (Hours 8-10)**
- US-TO-005: Analyze results (1 hour)
- US-TO-006: Deploy winner to production (30 min)
- Monitor for stability (ongoing)

**Total Timeline: 8-10 hours** (vs 7 days in original plan)

---

## Success Criteria

**Overall Success:**
- [x] All 6 user stories complete
- [x] Agent weights optimized based on accuracy data
- [x] Threshold validated via rapid shadow testing (50+ trades)
- [x] Winner identified with statistical significance (p<0.05)
- [x] Production deployment successful
- [x] Win rate improvement: +2-5% (58% → 60-63%)

**Validation Metrics:**
- Win rate: 60-63% (target)
- Trade frequency: +10-20% (acceptable increase)
- Entry price: <$0.20 avg (quality maintained)
- Directional balance: 40-60% (balanced)
- Statistical confidence: p<0.05 (significant result)

**Rollback Triggers:**
- Win rate <58% over 50 trades (revert threshold)
- System errors >5% (revert changes)
- Drawdown >25% (halt and investigate)

---

## Risk Management

**Risks & Mitigations:**

1. **Insufficient data in 4-6 hours**
   - Mitigation: Extend to 8-10 hours if needed
   - 10 hours = 160 data points per strategy (very high confidence)

2. **No clear winner (all within 2% WR)**
   - Mitigation: Keep current threshold (0.82)
   - Agent reweighting still provides benefit

3. **Winner is regime-dependent**
   - Mitigation: Test across BULL/BEAR/CHOPPY regimes
   - Only promote if consistent across regimes

4. **Production deployment breaks system**
   - Mitigation: Staged rollout (shadow → live)
   - Immediate rollback if errors detected

---

## Monitoring & Alerts

**During Testing (Hours 2-8):**
- Dashboard refresh: Every 5 minutes
- Check data collection rate: Every hour
- Verify no errors: Continuous log monitoring

**After Deployment (Hours 8+):**
- Win rate tracking: Every 10 trades
- Performance alerts: If WR <58% after 30 trades
- System health: CPU, memory, API rate limits

**Tools:**
- `simulation/dashboard.py` - Real-time comparison
- `simulation/analyze.py` - Statistical analysis
- `utils/performance_monitor.py` - Automated alerts

---

## Documentation Updates

**After Completion:**
- Update `CLAUDE.md` with new threshold (0.80)
- Document agent weight changes
- Add entry to `progress-threshold-optimization.txt`
- Create case study: "4-Hour Threshold Optimization"

---

**Document Version:** 1.0
**Created:** 2026-01-16
**Status:** READY FOR EXECUTION
**Estimated Total Time:** 8-10 hours (including data collection)
**Expected Win Rate Improvement:** +2-5% (58% → 60-63%)
