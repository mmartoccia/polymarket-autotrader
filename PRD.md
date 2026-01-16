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
- [x] Change agents/tech_agent.py lines 95, 105: Return 0.5 instead of 1.0 for RSI 40-60
- [x] Update reasoning to indicate "RSI neutral → low confidence"
- [x] Test: RSI=50 → confidence=0.5
- [x] Test: RSI=65 → confidence=0.8 (bearish, unchanged)
- [x] Test: RSI=35 → confidence=0.8 (bullish, unchanged)
- [x] Typecheck passes

### US-BF-006: Update vote aggregator for Skip votes
**Description:** As a developer, I need the vote aggregator to filter out Skip votes before calculating consensus, treating abstentions correctly.

**Acceptance Criteria:**
- [x] Update coordinator/vote_aggregator.py line 119: Filter Skip votes before aggregation
- [x] Only count Up/Down votes in consensus calculation
- [x] Log number of Skip votes for debugging
- [x] Test: 3 Up, 2 Down, 1 Skip → consensus calculated from 5 votes (not 6)
- [x] Test: All Skip votes → return no consensus (skip trade)
- [x] Typecheck passes

### US-BF-007: Change weighted score to average
**Description:** As a developer, I need weighted scores to average instead of sum to prevent weak signals from stacking into false consensus.

**Acceptance Criteria:**
- [x] Change coordinator/vote_aggregator.py lines 140-142: Divide sum by count
- [x] Formula: weighted_score = sum(confidence * weight) / sum(weight)
- [x] Test: Three 0.35 confidence votes → weighted score ~0.35 (not 1.05)
- [x] Test: One 0.80 vote + two 0.30 votes → weighted average calculated correctly
- [x] Log weighted score for debugging
- [x] Typecheck passes

### US-BF-008: Add directional balance tracker class
**Description:** As a developer, I need a tracker that monitors directional balance over rolling windows to detect cascading bias early.

**Acceptance Criteria:**
- [x] Create DirectionalBalanceTracker class in coordinator/decision_engine.py
- [x] Track last 20 decisions with direction and timestamp
- [x] Calculate rolling directional percentages
- [x] Alert when >70% same direction over 20+ decisions
- [x] Test: 15 Up / 5 Down → returns 75% Up bias with alert
- [x] Test: 10 Up / 10 Down → returns 50% balanced, no alert
- [x] Typecheck passes

### US-BF-009: Integrate balance tracker
**Description:** As a developer, I need the balance tracker integrated into decision logic to log warnings when directional cascades are detected.

**Acceptance Criteria:**
- [x] Instantiate DirectionalBalanceTracker in decision engine
- [x] Add tracker.record() call after each decision
- [x] Log warning if tracker.check_balance() detects >70% bias
- [x] Test: After 15 Up decisions, warning logged
- [x] Test: Balanced decisions (10 Up / 10 Down) → no warning
- [x] Typecheck passes

### US-BF-010: Verify consensus threshold
**Description:** As a developer, I need to confirm the consensus threshold is correctly enforced as configured (0.75) with debug logging.

**Acceptance Criteria:**
- [x] Add debug logging in coordinator/decision_engine.py line 200
- [x] Log: "Consensus threshold check: {score} vs {threshold}"
- [x] Log includes configured threshold value on startup
- [x] Test: Score 0.74 → logged as "below threshold"
- [x] Test: Score 0.76 → logged as "above threshold"
- [x] Typecheck passes

### US-BF-012: Add threshold debug logging
**Description:** As a developer, I need comprehensive debug logging for all threshold checks to diagnose future issues quickly.

**Acceptance Criteria:**
- [x] Log consensus threshold checks with actual values
- [x] Log confidence threshold checks with actual values
- [x] Log confluence threshold checks with price changes
- [x] Include agent name and reasoning in logs
- [x] Test: Review logs show all threshold decisions clearly
- [x] Typecheck passes

### US-BF-016: Shadow test validation setup
**Description:** As a developer, I need to create a shadow strategy with all 16 fixes to validate improvements before live deployment.

**Acceptance Criteria:**
- [x] Add "fixed_bugs" strategy to simulation/strategy_configs.py
- [x] Strategy config includes all 16 fixes applied
- [x] Strategy runs in parallel with current live strategy
- [x] Log shadow vs live comparison metrics after each trade
- [x] Test: Shadow strategy executes trades independently
- [x] Run for 24 hours, collect win rate, directional balance, confidence metrics
- [x] Typecheck passes

### US-BF-017: Add multi-epoch trend detection to prevent counter-trend trades
**Description:** As a developer, I need to prevent the bot from taking contrarian trades against clear medium-term trends (1-2 hour downtrends/uptrends) by adding consecutive epoch tracking to TechAgent and lowering detection thresholds.

**Context:**
- Jan 16 8am trades: Bot bought BTC/ETH Up during clear downtrend (both lost)
- TechAgent abstained (0.30% threshold too high for -0.15% per epoch moves)
- RegimeAgent abstained (0.1% mean return threshold classified -0.07% as "sideways")
- SentimentAgent dominated with 90% confidence contrarian fade
- Result: Single agent triggered trades against visible 3-5 epoch downtrend

**Root Causes:**
1. TechAgent only looks at single epoch (misses cumulative 3-5 epoch trends)
2. Confluence threshold 0.30% filters out -0.15 to -0.20% moves that accumulate
3. RegimeAgent threshold 0.1% too strict (-0.05 to -0.09% = "sideways" not "weak bear")
4. No agent tracks consecutive directional epochs (3+ Down in row = downtrend)
5. Gap between TechAgent (15min) and RegimeAgent (5hr) misses 1-2hr trends

**Acceptance Criteria:**
- [x] Lower TECH_CONFLUENCE_THRESHOLD from 0.003 to 0.002 (0.30% → 0.20%) in config/agent_config.py
- [x] Lower TECH_CONFLUENCE_THRESHOLD from 0.003 to 0.002 in agents/tech_agent.py (keep in sync)
- [x] Lower REGIME_TREND_THRESHOLD from 0.001 to 0.0005 (0.10% → 0.05%) in config/agent_config.py
- [x] Lower TREND_THRESHOLD from 0.001 to 0.0005 in agents/regime_agent.py (keep in sync)
- [x] Add consecutive_epochs tracking to TechAgent:
  - Track last 5 epochs of direction (Up/Down/Flat) per crypto
  - If 3+ consecutive same direction → recognize trend
  - If current vote conflicts with 3+ epoch trend → reduce confidence by 50%
  - Add reasoning: "Conflicts with 3-epoch downtrend, reducing confidence"
- [x] Add trend_strength field to RegimeAgent vote details:
  - "strong_bull" (mean > 0.10%), "weak_bull" (0.05-0.10%)
  - "strong_bear" (mean < -0.10%), "weak_bear" (-0.10 to -0.05%)
  - "sideways" (-0.05 to +0.05%)
- [x] Update vote aggregator to check for trend conflicts:
  - If TechAgent detects 3+ epoch trend AND agent votes opposite → log warning
  - Don't auto-veto but flag for consensus threshold adjustment
- [x] Add logging: "TechAgent detected 3-epoch downtrend (BTC: Down, Down, Down)"
- [x] Add logging: "RegimeAgent classified weak_bear regime (mean: -0.07%)"
- [x] Test: TechAgent recognizes 3 consecutive Down epochs as downtrend
- [x] Test: RegimeAgent classifies -0.07% mean as weak_bear not sideways
- [x] Test: Bot logs warning when SentimentAgent Up vote conflicts with downtrend
- [x] Test: Lower thresholds allow detection of -0.15% to -0.20% moves
- [x] Typecheck passes

**Success Metrics:**
- Bot should NOT buy Up during 3+ consecutive Down epochs
- TechAgent abstain rate should decrease (more signals detected)
- RegimeAgent should classify weak trends instead of sideways
- Trades should align with visible 1-2 hour TradingView trends

**Implementation Notes:**
- Store last 5 epochs per crypto in TechAgent: `self.epoch_history: Dict[str, deque] = {}`
- Use deque(maxlen=5) for automatic rolling window
- Check consecutive direction before returning final vote
- Don't block trades, just adjust confidence when conflict detected
- Log all trend detections for validation

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
