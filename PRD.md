# PRD: Bug Fixes - Directional Bias & Signal Quality

## Introduction

Fix 10 critical bugs causing systematic directional prediction failures that led to a $154 loss (53% drawdown from $290 to $136). The bot's predictions flipped from 100% UP-biased to 80% DOWN-biased while the market stayed neutral/choppy, causing losses in both directions. Root causes include default-to-Up biases in three agents, RSI neutral zone scoring errors, weak signal stacking through additive scoring, and ML model feature leakage causing 40% win rate versus 50% random chance.

This PRD addresses both the underlying bugs AND profitability restoration through strategic configuration changes.

## Goals

**Eliminate Systematic Biases:**
- Remove default-to-Up biases from TechAgent, SentimentAgent, and RegimeAgent
- Fix RSI neutral zone scoring (returning 1.0 confidence instead of 0.5 for neutral readings)
- Implement "Skip" vote type allowing agents to abstain when uncertain
- Change weighted score aggregation from sum to average (prevents weak signal stacking)
- Add directional balance tracker to detect cascading bias (>70% same direction alerts)
- Raise confluence threshold from 0.15% to 0.30% (filters random walk noise)
- Verify consensus threshold is enforced as configured (0.75)

**Restore Profitability:**
- Disable ML model temporarily (feature leakage causing 40% WR vs 67.3% test accuracy)
- Lower entry price thresholds (MAX_ENTRY: 0.40 → 0.25 reduces breakeven WR from 52% to 51%)
- Check and disable bull market overrides if active (inappropriate for neutral markets)
- Shadow test all fixes before live deployment (validate with 24hr monitoring)

**Success Metrics:**
- Win rate: 55-65% sustained (above 53% breakeven)
- Directional balance: 40-60% in neutral markets (no cascades)
- Entry prices: <$0.30 average (lower fee drag)
- Trade frequency: Fewer but higher quality trades

## User Stories

### US-BF-013: Disable ML mode temporarily
**Description:** As a developer, I need to disable the broken ML model (40% WR due to feature leakage) and switch to agent-only mode to restore profitability.

**Acceptance Criteria:**
- [x] Set USE_ML_MODEL=False in config/agent_config.py
- [x] Update bot/momentum_bot_v12.py to skip ML predictions when flag is False
- [x] Add log message on startup: "ML mode disabled - using agent-only mode"
- [x] Test: Bot startup logs show ML mode disabled message
- [x] Test: Bot makes decisions using only agent voting (no ML predictions)
- [x] Verify ML model code path is not executed during decision loop
- [x] Typecheck passes

### US-BF-014: Lower entry price threshold
**Description:** As a developer, I need to lower entry price limits to reduce fee drag and improve profitability by lowering the breakeven win rate from 52% to 51%.

**Acceptance Criteria:**
- [x] Update MAX_ENTRY from 0.40 to 0.25 in config
- [x] Update EARLY_MAX_ENTRY from 0.75 to 0.30 in config
- [x] Log warning if attempting to trade above new thresholds
- [x] Test: Entry price >0.25 is rejected with clear reason
- [x] Verify existing positions unaffected (config only affects new trades)
- [x] Typecheck passes

### US-BF-015: Check and disable bull market overrides
**Description:** As a developer, I need to detect and disable bull market overrides if active, as they are inappropriate for current neutral/choppy market conditions.

**Acceptance Criteria:**
- [x] Check if state/bull_market_overrides.json is being loaded
- [x] Add flag to disable overrides if detected: DISABLE_BULL_OVERRIDES=True
- [x] Log warning on startup if overrides file exists but disabled
- [x] Test: Bot ignores bull_market_overrides.json when flag is set
- [x] If file doesn't exist, log info message (not error)
- [x] Typecheck passes

### US-BF-011: Raise confluence threshold
**Description:** As a developer, I need to raise the confluence threshold from 0.15% to 0.30% to filter out random walk noise in 15-minute epochs.

**Acceptance Criteria:**
- [x] Change CONFLUENCE_THRESHOLD from 0.0015 to 0.003 in config/agent_config.py line 78
- [x] Add comment explaining threshold filters ±0.05% typical random walk
- [x] Test: 0.20% price move does not trigger confluence
- [x] Test: 0.35% price move does trigger confluence
- [x] Verify threshold used in TechAgent decision logic
- [x] Typecheck passes

### US-BF-005: Implement "Skip" vote type
**Description:** As a developer, I need agents to abstain when uncertain instead of defaulting to a direction, preventing systematic bias.

**Acceptance Criteria:**
- [x] Add "Skip" to valid directions in agents/base_agent.py Vote dataclass line 26
- [x] Update Vote validation to accept "Skip" as valid direction
- [x] Skip votes have confidence=0.0 and quality=0.0 by convention
- [x] Add docstring explaining when to return Skip vote
- [x] Test: Skip vote can be created without validation errors
- [x] Typecheck passes

### US-BF-001: Remove TechAgent default-to-Up bias
**Description:** As a developer, I need TechAgent to abstain when no clear direction exists so it doesn't create systematic Up bias in neutral markets.

**Acceptance Criteria:**
- [x] Change agents/tech_agent.py line 318: Return Skip vote instead of picking Up on tie
- [x] Skip vote has confidence=0.0 and quality=0.0
- [x] Reasoning indicates "no confluence detected → ABSTAINING"
- [x] Test: Flat market (avg_change=0) → Skip vote returned
- [x] Test: Tie scenario (2 Up, 2 Down exchanges) → Skip vote returned
- [x] Typecheck passes

### US-BF-002: Remove SentimentAgent default-to-Up bias
**Description:** As a developer, I need SentimentAgent to abstain when no orderbook data exists or on errors, instead of defaulting to Up.

**Acceptance Criteria:**
- [x] Change agents/sentiment_agent.py line 77: Return Skip vote on missing orderbook
- [x] Change agents/sentiment_agent.py line 107: Return Skip vote on API errors
- [x] Skip votes have confidence=0.0 and quality=0.0
- [x] Reasoning indicates reason for abstaining
- [x] Test: Missing orderbook → Skip vote
- [x] Test: API timeout → Skip vote
- [x] Typecheck passes

### US-BF-003: Remove RegimeAgent default-to-Up bias
**Description:** As a developer, I need RegimeAgent to abstain in sideways/choppy regimes instead of defaulting to Up.

**Acceptance Criteria:**
- [x] Change agents/regime_agent.py line 128: Return Skip vote in sideways regime
- [x] Skip vote has confidence=0.0 and quality=0.0
- [x] Reasoning indicates "sideways regime → ABSTAINING"
- [x] Test: Choppy market detection → Skip vote returned
- [x] Test: Bull/bear regime still returns Up/Down votes
- [x] Typecheck passes

### US-BF-004: Fix RSI neutral zone scoring
**Description:** As a developer, I need RSI 40-60 (neutral zone) to return 0.5 confidence instead of 1.0, preventing false high confidence in sideways markets.

**Acceptance Criteria:**
- [ ] Change agents/tech_agent.py lines 95, 105: Return 0.5 instead of 1.0 for RSI 40-60
- [ ] Update reasoning to indicate "RSI neutral → low confidence"
- [ ] Test: RSI=50 → confidence=0.5
- [ ] Test: RSI=65 → confidence=0.8 (bearish, unchanged)
- [ ] Test: RSI=35 → confidence=0.8 (bullish, unchanged)
- [ ] Typecheck passes

### US-BF-006: Update vote aggregator for Skip votes
**Description:** As a developer, I need the vote aggregator to filter out Skip votes before calculating consensus, treating abstentions correctly.

**Acceptance Criteria:**
- [ ] Update coordinator/vote_aggregator.py line 119: Filter Skip votes before aggregation
- [ ] Only count Up/Down votes in consensus calculation
- [ ] Log number of Skip votes for debugging
- [ ] Test: 3 Up, 2 Down, 1 Skip → consensus calculated from 5 votes (not 6)
- [ ] Test: All Skip votes → return no consensus (skip trade)
- [ ] Typecheck passes

### US-BF-007: Change weighted score to average
**Description:** As a developer, I need weighted scores to average instead of sum to prevent weak signals from stacking into false consensus.

**Acceptance Criteria:**
- [ ] Change coordinator/vote_aggregator.py lines 140-142: Divide sum by count
- [ ] Formula: weighted_score = sum(confidence * weight) / sum(weight)
- [ ] Test: Three 0.35 confidence votes → weighted score ~0.35 (not 1.05)
- [ ] Test: One 0.80 vote + two 0.30 votes → weighted average calculated correctly
- [ ] Log weighted score for debugging
- [ ] Typecheck passes

### US-BF-008: Add directional balance tracker class
**Description:** As a developer, I need a tracker that monitors directional balance over rolling windows to detect cascading bias early.

**Acceptance Criteria:**
- [ ] Create DirectionalBalanceTracker class in coordinator/decision_engine.py
- [ ] Track last 20 decisions with direction and timestamp
- [ ] Calculate rolling directional percentages
- [ ] Alert when >70% same direction over 20+ decisions
- [ ] Test: 15 Up / 5 Down → returns 75% Up bias with alert
- [ ] Test: 10 Up / 10 Down → returns 50% balanced, no alert
- [ ] Typecheck passes

### US-BF-009: Integrate balance tracker
**Description:** As a developer, I need the balance tracker integrated into decision logic to log warnings when directional cascades are detected.

**Acceptance Criteria:**
- [ ] Instantiate DirectionalBalanceTracker in decision engine
- [ ] Add tracker.record() call after each decision
- [ ] Log warning if tracker.check_balance() detects >70% bias
- [ ] Test: After 15 Up decisions, warning logged
- [ ] Test: Balanced decisions (10 Up / 10 Down) → no warning
- [ ] Typecheck passes

### US-BF-010: Verify consensus threshold
**Description:** As a developer, I need to confirm the consensus threshold is correctly enforced as configured (0.75) with debug logging.

**Acceptance Criteria:**
- [ ] Add debug logging in coordinator/decision_engine.py line 200
- [ ] Log: "Consensus threshold check: {score} vs {threshold}"
- [ ] Log includes configured threshold value on startup
- [ ] Test: Score 0.74 → logged as "below threshold"
- [ ] Test: Score 0.76 → logged as "above threshold"
- [ ] Typecheck passes

### US-BF-012: Add threshold debug logging
**Description:** As a developer, I need comprehensive debug logging for all threshold checks to diagnose future issues quickly.

**Acceptance Criteria:**
- [ ] Log consensus threshold checks with actual values
- [ ] Log confidence threshold checks with actual values
- [ ] Log confluence threshold checks with price changes
- [ ] Include agent name and reasoning in logs
- [ ] Test: Review logs show all threshold decisions clearly
- [ ] Typecheck passes

### US-BF-016: Shadow test validation setup
**Description:** As a developer, I need to create a shadow strategy with all 16 fixes to validate improvements before live deployment.

**Acceptance Criteria:**
- [ ] Add "fixed_bugs" strategy to simulation/strategy_configs.py
- [ ] Strategy config includes all 16 fixes applied
- [ ] Strategy runs in parallel with current live strategy
- [ ] Log shadow vs live comparison metrics after each trade
- [ ] Test: Shadow strategy executes trades independently
- [ ] Run for 24 hours, collect win rate, directional balance, confidence metrics
- [ ] Typecheck passes

## Non-Goals

- No ML model retraining (separate PRD after collecting clean data)
- No regime-specific threshold adjustments (P3 optimization)
- No geometric mean scoring implementation (P3 optimization)
- No bull market override file removal (only disable if exists)
- No position hedging or advanced risk strategies
- No multi-timeframe confirmation (future enhancement)

## Technical Considerations

- Agents use async/await patterns - maintain compatibility
- Vote aggregation in coordinator/vote_aggregator.py - careful with Skip vote filtering
- Decision logic in coordinator/decision_engine.py - balance tracker must be lightweight
- Configuration in config/agent_config.py - use consistent naming for thresholds
- Must maintain backward compatibility with existing shadow strategies
- Shadow trading system must continue working during all changes
- ML model code remains in codebase but disabled via flag (not deleted)
- Entry price changes only affect NEW trades (existing positions unaffected)
- All changes must pass typecheck before deployment to VPS
