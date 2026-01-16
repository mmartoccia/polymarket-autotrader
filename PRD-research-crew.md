# PRD: Elite Research Crew - System Evaluation

## Introduction

Execute a comprehensive evaluation of the Polymarket AutoTrader system using 9 specialized researcher personas. Each persona brings domain expertise and executes specific analytical tasks to answer: **Is the system profitable, sustainable, optimizable, safe, and trustworthy?**

**Timeline:** 4 weeks (Jan 16 - Feb 13, 2026)

**Expected Outcome:** Validated performance metrics, identified vulnerabilities, simplified architecture, and actionable optimization roadmap to achieve 60-65% win rate.

---

## Personas & Their Expertise

### 🎓 Dr. Sarah Chen - Probabilistic Mathematician
**Mindset:** "Show me the math. Prove it with statistical significance."
**Focus:** Fee economics, Kelly criterion, expected value, probability of ruin
**Deliverables:** Mathematical proofs, statistical tests, optimization formulas

### 📊 James "Jimmy the Greek" Martinez - Market Microstructure Specialist
**Mindset:** "Entry timing is everything. The spread doesn't lie."
**Focus:** Order books, entry prices, slippage, liquidity analysis
**Deliverables:** Price distribution analysis, timing optimization, execution quality reports

### 🧠 Dr. Amara Johnson - Behavioral Finance Expert
**Mindset:** "Every risk control embeds a psychological bias."
**Focus:** Loss aversion, gambler's fallacy, herding, overconfidence
**Deliverables:** Bias identification, calibration curves, behavioral audits

### 🤖 Victor "Vic" Ramanujan - Quantitative Strategist
**Mindset:** "Data-driven decisions. Test everything. Trust nothing."
**Focus:** Agent performance, ML validation, shadow strategies, optimization
**Deliverables:** Agent rankings, strategy tournament results, performance attribution

### 🛡️ Colonel Rita "The Guardian" Stevens - Risk Management Architect
**Mindset:** "Plan for failure. Stress test everything. Hope is not a strategy."
**Focus:** Drawdown protection, position sizing, correlation limits, circuit breakers
**Deliverables:** Risk validation, stress tests, Monte Carlo simulations

### 🔧 Dmitri "The Hammer" Volkov - System Reliability Engineer
**Mindset:** "If it can fail, it will fail. Build for 3am crashes."
**Focus:** State management, API reliability, VPS uptime, data integrity
**Deliverables:** Infrastructure audits, failure mode analysis, operational procedures

### 🔬 Dr. Kenji Nakamoto - Data Forensics Specialist
**Mindset:** "Trust but verify. Every dataset has a story—sometimes it's fiction."
**Focus:** Data integrity, overfitting detection, survivorship bias, anomaly detection
**Deliverables:** Data validation, p-hacking tests, anomaly reports

### ♟️ Prof. Eleanor Nash - Game Theory Economist
**Mindset:** "Every strategy has a counter-strategy. What's the Nash equilibrium?"
**Focus:** Multi-epoch dynamics, regime switching, competitive strategy, market adaptation
**Deliverables:** Strategic synthesis, regime analysis, long-term recommendations

### ⚡ Alex "Occam" Rousseau - First Principles Engineer
**Mindset:** "Complexity is a liability. What's the simplest thing that could possibly work?"
**Focus:** Architectural simplification, removing unnecessary components, questioning assumptions, essential complexity vs accidental complexity
**Deliverables:** Simplification audit, component elimination proposals, first principles redesign, complexity cost-benefit analysis
**Philosophy:**
- "Can we delete this entire agent and improve results?"
- "Are we solving the right problem, or optimizing the wrong solution?"
- "What would this system look like if we rebuilt it with only what we know works?"
- "Every line of code is a liability—prove it earns its keep."

---

## System Context (All Personas Should Know)

**Current State:**
- Balance: $200.97 (33% drawdown from $300 peak)
- Win Rate: 56-60% (claimed, needs validation)
- Architecture: Multi-agent consensus (4-11 agents voting)
- Risk Controls: 30% drawdown halt, tiered sizing, correlation limits
- Environment: Production VPS (24/7 trading since Jan 2026)

**Critical Incidents:**
- Jan 14: Lost 95% ($157 → $7) due to trend filter bias (96.5% UP trades)
- Jan 16: State tracking desync ($186 error in peak_balance)

**Key Files:**
- `bot/momentum_bot_v12.py` - Main trading logic (1600+ lines)
- `config/agent_config.py` - Agent configuration
- `state/trading_state.json` - Balance and performance state
- `simulation/trade_journal.db` - Shadow strategy results (27 strategies)
- `bot.log` - Historical trades (on VPS: `/opt/polymarket-autotrader/bot.log`)

**VPS Access:** `ssh root@216.238.85.11`

---

## User Stories - Week 1: Foundation & Data Integrity

### 🔬 PERSONA: Dr. Kenji Nakamoto (Data Forensics)

#### US-RC-001: Parse and validate trade log completeness
**Persona Context:** "I need to ensure the data is trustworthy before anyone analyzes it. Missing trades or corrupted entries invalidate all downstream research."

**Acceptance Criteria:**
- [x] Create `scripts/research/parse_trade_logs.py` that reads `bot.log`
- [x] Extract fields: timestamp, crypto, direction, entry_price, shares, outcome, epoch_id
- [x] Count: Total trades, complete trades, incomplete trades (missing outcome)
- [x] Generate `reports/kenji_nakamoto/trade_log_completeness.md` with statistics
- [x] Report: % completeness, date range coverage, missing data patterns
- [x] Test: Script runs without errors on actual `bot.log`
- [x] Typecheck passes

#### US-RC-002: Detect duplicate trades in logs
**Persona Context:** "API retries or redemption bugs could create duplicate entries. These inflate win rates artificially."

**Acceptance Criteria:**
- [x] Create `scripts/research/detect_duplicates.py`
- [x] Hash each trade: `hash(timestamp + crypto + direction + entry_price)`
- [x] Identify exact duplicates (same hash)
- [x] Identify near-duplicates (timestamp within 5s, same crypto/direction)
- [x] Generate `reports/kenji_nakamoto/duplicate_analysis.csv` with duplicate pairs
- [x] Report: Count of duplicates, % of total trades, suspected cause
- [x] Test: Script correctly identifies known test duplicates
- [x] Typecheck passes

#### US-RC-003: Reconcile balance from trade history
**Persona Context:** "If starting_balance + sum(pnl) ≠ current_balance, there's a data integrity issue or hidden transactions."

**Acceptance Criteria:**
- [x] Create `scripts/research/reconcile_balance.py`
- [x] Extract from logs: All deposits, withdrawals, trade P&L
- [x] Calculate: starting_balance + deposits - withdrawals + sum(trade_pnl)
- [x] Compare to `state/trading_state.json` → current_balance
- [x] Generate `reports/kenji_nakamoto/balance_reconciliation.md`
- [x] Report: Expected vs actual balance, discrepancy amount, % error
- [x] Test: Reconciliation within $1 of actual balance OR discrepancy explained
- [x] Typecheck passes

#### US-RC-004: Verify 10 trades on-chain (Polygon)
**Persona Context:** "On-chain data is the ground truth. If bot logs don't match blockchain, we have a serious problem."

**Acceptance Criteria:**
- [x] Create `scripts/research/verify_on_chain.py`
- [x] Sample 10 random trades from logs (spread across different days)
- [x] For each trade, query Polygon blockchain (Polygonscan API or RPC)
- [x] Verify: Transaction exists, amount matches, outcome matches
- [x] Generate `reports/kenji_nakamoto/on_chain_verification.md`
- [x] Report: X/10 trades verified, discrepancies (if any)
- [x] Test: At least 8/10 trades match on-chain data
- [x] Typecheck passes

#### US-RC-005: Test for survivorship bias (period selection)
**Persona Context:** "Is the 56-60% win rate cherry-picked from good periods? I need to check if any time periods are excluded."

**Acceptance Criteria:**
- [x] Create `scripts/research/survivorship_bias_check.py`
- [x] Parse all trade timestamps, identify date range coverage
- [x] Check for gaps: Missing days (>24h between trades)
- [x] Calculate win rate per day, per week
- [x] Generate `reports/kenji_nakamoto/survivorship_bias_report.md`
- [x] Report: Full date range, gaps found (if any), win rate by period
- [x] Test: Script identifies all gaps >24h in trade history
- [x] Typecheck passes

---

### 🔧 PERSONA: Dmitri "The Hammer" Volkov (System Reliability)

#### US-RC-006: Audit state file atomic write safety
**Persona Context:** "If the bot crashes mid-write to trading_state.json, we corrupt the state. I need to verify atomic writes are implemented."

**Acceptance Criteria:**
- [x] Review code: `bot/momentum_bot_v12.py` → save_state() function
- [x] Check: Does it use tmp file + rename pattern? (atomic on POSIX)
- [x] Pattern should be: write to `.tmp`, then `os.rename()` to actual file
- [x] If not atomic, document the bug in `reports/dmitri_volkov/state_audit.md`
- [x] Generate: Code snippet showing proper atomic write pattern
- [x] Test: Create test that simulates crash during state save
- [x] Report: Atomic write implemented (yes/no), risk level, fix recommendation
- [x] Typecheck passes

#### US-RC-007: Reproduce Jan 16 peak_balance desync
**Persona Context:** "The $186 error is a smoking gun. I need to understand exactly how peak_balance got corrupted."

**Acceptance Criteria:**
- [x] Review `state/trading_state.json` history in git: `git log --all state/`
- [x] Parse `bot.log` around Jan 16 01:56 UTC for peak_balance updates
- [x] Identify: When did peak_balance become $386.97 instead of $200.97?
- [x] Hypothesis: Were unredeemed position values added to peak?
- [x] Generate `reports/dmitri_volkov/jan16_desync_root_cause.md`
- [x] Report: Timeline of peak_balance changes, root cause, code fix needed
- [x] Test: Proposed fix prevents desync in test scenario
- [x] Typecheck passes

#### US-RC-008: Test state recovery from corruption
**Persona Context:** "What happens if trading_state.json is deleted or contains invalid JSON? Does the bot crash or recover gracefully?"

**Acceptance Criteria:**
- [x] Create `scripts/research/test_state_recovery.py`
- [x] Test scenario 1: Delete trading_state.json, run bot startup
- [x] Test scenario 2: Write invalid JSON to file, run bot startup
- [x] Test scenario 3: Set current_balance to negative, run bot startup
- [x] Document: Does bot crash? Does it create new state? Does it validate?
- [x] Generate `reports/dmitri_volkov/state_recovery_tests.csv`
- [x] Report: Recovery behavior for each scenario, risks, recommendations
- [x] Test: At least 2/3 scenarios handled gracefully (no crash)
- [x] Typecheck passes

#### US-RC-009: Map all external API dependencies
**Persona Context:** "I need to inventory every external API the bot calls. Any single point of failure can take down the system."

**Acceptance Criteria:**
- [x] Create `scripts/research/map_api_dependencies.py`
- [x] Scan `bot/momentum_bot_v12.py` for all `requests.get()` and `requests.post()` calls
- [x] Extract: API endpoint, purpose, timeout setting, retry logic
- [x] Identify APIs: Polymarket (Gamma, CLOB, Data), Exchanges (Binance, Kraken, Coinbase), Polygon RPC
- [x] Generate `reports/dmitri_volkov/api_dependency_map.md`
- [x] Report: List of APIs, single points of failure, missing timeouts, missing error handling
- [x] Test: Script successfully parses bot code and finds ≥5 API endpoints (found 7)
- [x] Typecheck passes

#### US-RC-010: Check VPS service uptime and restarts
**Persona Context:** "If the bot is restarting frequently, there's an underlying stability issue I need to find."

**Acceptance Criteria:**
- [ ] SSH to VPS: `ssh root@216.238.85.11`
- [ ] Run: `systemctl status polymarket-bot` (capture uptime)
- [ ] Run: `journalctl -u polymarket-bot --since "2026-01-01"` (count restarts)
- [ ] Identify: Crash logs, OOM kills, manual restarts
- [ ] Generate `reports/dmitri_volkov/vps_health_report.md`
- [ ] Report: Total uptime %, restart count, crash reasons, resource usage
- [ ] Test: Report shows uptime data for Jan 2026
- [ ] Document: Save output locally (no typecheck needed for report)

---

### 🎓 PERSONA: Dr. Sarah Chen (Probabilistic Mathematician)

#### US-RC-011: Calculate weighted average fee rate from trades
**Persona Context:** "The breakeven calculation depends on actual fees paid, not theoretical. I need to calculate the true weighted average fee rate."

**Acceptance Criteria:**
- [ ] Use parsed trade data from US-RC-001 (trade logs)
- [ ] For each trade, calculate fee: Use Polymarket fee formula (depends on entry_price probability)
- [ ] Formula: `fee_rate ≈ 0.0315 * (1 - abs(2*entry_price - 1))` (approx)
- [ ] Calculate weighted average: `sum(fee * trade_size) / sum(trade_size)`
- [ ] Generate `reports/sarah_chen/fee_economics_validation.md`
- [ ] Report: Average fee rate, min/max fees, breakeven win rate calculation
- [ ] Create `scripts/research/fee_calculator.py` with fee formula
- [ ] Test: Calculator returns 3.15% for entry_price=0.50, <1% for entry_price=0.10
- [ ] Typecheck passes

#### US-RC-012: Calculate probability of ruin (Monte Carlo)
**Persona Context:** "Given current position sizing and win rate, what's the probability we hit $0 in the next 100 trades?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/probability_of_ruin.py`
- [ ] Inputs: Starting balance=$200, win_rate=0.58, position_size_pct=0.05-0.15 (tiered)
- [ ] Run 10,000 Monte Carlo simulations of 100 trades each
- [ ] Track: How many simulations hit $0 (ruin)
- [ ] Generate `reports/sarah_chen/probability_of_ruin.md`
- [ ] Report: P(ruin) percentage, distribution of final balances (histogram)
- [ ] Create visualization: `reports/sarah_chen/ruin_simulation.png`
- [ ] Test: Simulation runs successfully, P(ruin) < 10% (acceptable)
- [ ] Typecheck passes

#### US-RC-013: Test win rate statistical significance
**Persona Context:** "Is 58% win rate significantly better than 50% coin flip? Or is it noise?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/statistical_significance.py`
- [ ] Input: Trade outcomes from logs (wins/losses count)
- [ ] Hypothesis test: H0: p=0.50 (coin flip), H1: p>0.50 (edge exists)
- [ ] Calculate: z-score, p-value (using binomial test)
- [ ] Determine: Sample size needed for 95% confidence at 58% WR
- [ ] Generate `reports/sarah_chen/statistical_significance.md`
- [ ] Report: z-score, p-value, confidence interval, conclusion (reject H0 or not)
- [ ] Test: Script correctly calculates p-value for example data (100 trades, 58 wins)
- [ ] Typecheck passes

---

## User Stories - Week 2: Performance Analysis

### 📊 PERSONA: James "Jimmy the Greek" Martinez (Market Microstructure)

#### US-RC-014: Extract entry price distribution from logs
**Persona Context:** "Entry price determines everything: edge, fees, risk. I need to see the actual distribution, not just averages."

**Acceptance Criteria:**
- [ ] Use parsed trade data from US-RC-001
- [ ] Extract all entry_price values
- [ ] Calculate: mean, median, mode, std dev, 25th/75th percentiles
- [ ] Group by strategy: early momentum, contrarian, late confirmation (infer from timing)
- [ ] Generate `reports/jimmy_martinez/entry_price_distribution.md`
- [ ] Create histogram: `reports/jimmy_martinez/entry_price_histogram.png`
- [ ] Report: Distribution stats, comparison to config limits (MAX_ENTRY=0.25)
- [ ] Test: Histogram shows clear distribution pattern
- [ ] Typecheck passes

#### US-RC-015: Analyze win rate by entry price bucket
**Persona Context:** "Do cheap entries ($0.10-0.15) actually win more? Or is the edge in mid-range prices?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/entry_price_win_rate.py`
- [ ] Bucket entry prices: $0.05-0.10, $0.10-0.15, $0.15-0.20, $0.20-0.25, $0.25-0.30
- [ ] Calculate win rate per bucket
- [ ] Test statistical significance: Are differences real or noise? (chi-square test)
- [ ] Generate `reports/jimmy_martinez/entry_vs_outcome.csv`
- [ ] Report: Win rate per bucket, sample size, p-value, optimal entry range
- [ ] Test: Script correctly buckets trades and calculates WR
- [ ] Typecheck passes

#### US-RC-016: Identify optimal timing window (win rate by epoch second)
**Persona Context:** "Early trades (0-300s) vs late trades (720-900s) have different edges. Data will tell us which is best."

**Acceptance Criteria:**
- [ ] Use parsed trade data, extract "seconds into epoch" field
- [ ] Bucket by timing: 0-300s (early), 300-600s (mid), 600-900s (late)
- [ ] Calculate win rate per timing bucket
- [ ] Test significance: ANOVA or chi-square
- [ ] Generate `reports/jimmy_martinez/timing_window_analysis.md`
- [ ] Create heatmap: `reports/jimmy_martinez/timing_heatmap.png` (WR by 60s buckets)
- [ ] Report: Optimal timing windows, win rate differences, statistical significance
- [ ] Test: Script generates heatmap with color-coded win rates
- [ ] Typecheck passes

#### US-RC-017: Evaluate contrarian strategy performance
**Persona Context:** "Contrarian is currently disabled (ENABLE_CONTRARIAN_TRADES=False). But does historical data show it worked?"

**Acceptance Criteria:**
- [ ] Identify contrarian trades in logs: entry_price <0.20, opposite side >70%
- [ ] Or: Parse logs for "SentimentAgent" or "CONTRARIAN" in reasoning
- [ ] Calculate: Contrarian win rate vs non-contrarian
- [ ] Calculate: Contrarian ROI (accounting for cheap entry prices)
- [ ] Generate `reports/jimmy_martinez/contrarian_performance.md`
- [ ] Report: Contrarian WR, sample size, ROI, recommendation (keep disabled or re-enable)
- [ ] Test: Script identifies ≥10 contrarian trades from history
- [ ] Typecheck passes

---

### 🤖 PERSONA: Victor "Vic" Ramanujan (Quantitative Strategist)

#### US-RC-018: Query shadow strategy performance from database
**Persona Context:** "27 shadow strategies have been running. I need to see which ones are actually winning."

**Acceptance Criteria:**
- [ ] Create `scripts/research/shadow_leaderboard.py`
- [ ] Query `simulation/trade_journal.db` → performance table
- [ ] Extract: strategy_name, total_trades, win_rate, total_pnl, sharpe_ratio
- [ ] Rank by: total_pnl (primary), win_rate (secondary)
- [ ] Generate `reports/vic_ramanujan/shadow_leaderboard.csv`
- [ ] Report: Top 10 strategies, bottom 5 strategies, baseline (random) performance
- [ ] Test: Script successfully queries database and ranks strategies
- [ ] Typecheck passes

#### US-RC-019: Test if random baseline beats default strategy
**Persona Context:** "If random 50/50 coin flips beat our default strategy, we have negative edge. This is the ultimate sanity check."

**Acceptance Criteria:**
- [ ] Query shadow strategy: `random_baseline` from database
- [ ] Query shadow strategy: `default` (live strategy) from database
- [ ] Compare: Win rate, total P&L, Sharpe ratio
- [ ] Statistical test: Is default significantly better than random? (t-test)
- [ ] Generate `reports/vic_ramanujan/random_baseline_comparison.md`
- [ ] Report: Random WR vs Default WR, p-value, conclusion (edge exists or not)
- [ ] Test: Script performs t-test correctly
- [ ] Typecheck passes

#### US-RC-020: Calculate per-agent win rate from voting history
**Persona Context:** "Which agents help? Which agents hurt? I need to isolate individual agent contribution."

**Acceptance Criteria:**
- [ ] Create `scripts/research/per_agent_performance.py`
- [ ] Query `simulation/trade_journal.db` → agent_votes table
- [ ] For each agent: Calculate win rate when agent voted Up vs Down
- [ ] Calculate: Agent accuracy (% of trades where agent was correct)
- [ ] Generate `reports/vic_ramanujan/per_agent_performance.md`
- [ ] Report: Agent rankings by accuracy, agents with <50% accuracy (disable candidates)
- [ ] Create table: `reports/vic_ramanujan/agent_rankings.csv`
- [ ] Test: Script successfully queries agent_votes table and calculates accuracy
- [ ] Typecheck passes

#### US-RC-021: Test ML model on post-training data
**Persona Context:** "67.3% test accuracy was claimed. But what's the performance on Jan 2026 data (unseen during training)?"

**Acceptance Criteria:**
- [ ] Load ML model from `models/` (if exists) or use shadow strategy results
- [ ] Query shadow strategies: `ml_random_forest_50`, `ml_random_forest_55`, `ml_random_forest_60`
- [ ] Extract: Win rate, total trades, P&L for each threshold
- [ ] Compare to claimed 67.3% test accuracy
- [ ] Generate `reports/vic_ramanujan/ml_vs_agents.csv`
- [ ] Report: ML actual WR (Jan 2026), vs test WR (67.3%), vs agent WR
- [ ] Conclusion: Deploy ML or stick with agents?
- [ ] Test: Script queries ML shadow strategies successfully
- [ ] Typecheck passes

---

### 🛡️ PERSONA: Colonel Rita "The Guardian" Stevens (Risk Management)

#### US-RC-022: Validate drawdown calculation formula
**Persona Context:** "The Jan 16 desync shows drawdown tracking is broken. I need to audit the formula and find the bug."

**Acceptance Criteria:**
- [ ] Review code: `bot/momentum_bot_v12.py` → Guardian.check_kill_switch()
- [ ] Extract formula: `(peak_balance - current_balance) / peak_balance`
- [ ] Question: Does current_balance include unredeemed positions? (should be cash only)
- [ ] Review: When is peak_balance updated? (Should be on redemptions, not on order placement)
- [ ] Generate `reports/rita_stevens/drawdown_audit.md`
- [ ] Report: Current formula, bug identified (if any), proposed fix
- [ ] Test: Create unit test for drawdown calculation with edge cases
- [ ] Typecheck passes

#### US-RC-023: Stress test position sizing with Monte Carlo
**Persona Context:** "If we hit a 10-loss streak, do the tiered position sizes protect us? Or do we still blow up?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/position_sizing_stress_test.py`
- [ ] Simulate: 10 consecutive losses at different balance levels ($50, $100, $200)
- [ ] Apply tiered sizing: 15% (<$30), 10% ($30-75), 7% ($75-150), 5% (>$150)
- [ ] Calculate: Final balance after 10 losses
- [ ] Calculate: Drawdown % from starting balance
- [ ] Generate `reports/rita_stevens/stress_test_results.csv`
- [ ] Report: Worst-case drawdown, comparison to 30% halt threshold
- [ ] Test: 10-loss streak at $200 should NOT trigger >30% drawdown
- [ ] Typecheck passes

#### US-RC-024: Audit position limit enforcement
**Persona Context:** "Max 4 positions, max 3 same direction, max 8% directional exposure. Are these hard limits or just suggestions?"

**Acceptance Criteria:**
- [ ] Review code: `agents/risk_agent.py` → check_correlation_limits()
- [ ] Verify: Are limits enforced BEFORE order placement? (should be)
- [ ] Parse logs: Search for "BLOCKED: Position limit" messages
- [ ] Count: How many trades rejected due to limits? (proves enforcement)
- [ ] Generate `reports/rita_stevens/position_limits_audit.md`
- [ ] Report: Limits enforced (yes/no), rejected trade count, any violations found
- [ ] Test: Limits are enforced in code (not just logged)
- [ ] Typecheck passes

---

## User Stories - Week 3: Behavioral & Strategic Analysis

### 🧠 PERSONA: Dr. Amara Johnson (Behavioral Finance)

#### US-RC-025: Analyze recovery mode transitions
**Persona Context:** "Does the bot's psychology help or hurt? Recovery modes adjust sizing—but do they improve outcomes?"

**Acceptance Criteria:**
- [ ] Parse `bot.log` for mode transitions: normal → conservative → defensive → recovery
- [ ] Extract: Timestamp of mode change, trigger (loss amount or drawdown)
- [ ] Calculate: Win rate in each mode, time spent in each mode
- [ ] Test: Does defensive mode improve WR? Or just reduce bet size for no benefit?
- [ ] Generate `reports/amara_johnson/recovery_mode_audit.md`
- [ ] Report: Mode performance, recommendation (keep/modify/remove)
- [ ] Test: Script correctly identifies ≥3 mode transitions in logs
- [ ] Typecheck passes

#### US-RC-026: Test for gambler's fallacy in decision-making
**Persona Context:** "After 3 losses, does the bot bet more aggressively expecting a win? That's gambler's fallacy."

**Acceptance Criteria:**
- [ ] Create `scripts/research/gamblers_fallacy_test.py`
- [ ] Extract consecutive loss sequences from logs
- [ ] Measure: Position size after 1 loss, 2 losses, 3 losses
- [ ] Measure: Entry price threshold after loss streaks (does bot lower standards?)
- [ ] Statistical test: Is bet sizing correlated with recent losses? (should be independent)
- [ ] Generate `reports/amara_johnson/gambler_fallacy_test.md`
- [ ] Report: Correlation coefficient, p-value, conclusion (fallacy present or not)
- [ ] Test: Script detects loss streaks and measures bet sizing changes
- [ ] Typecheck passes

#### US-RC-027: Analyze agent voting herding (correlation matrix)
**Persona Context:** "Do agents independently assess the market? Or do they copy each other (herding)?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/agent_correlation.py`
- [ ] Query `simulation/trade_journal.db` → agent_votes table
- [ ] For each agent pair: Calculate correlation (Pearson r)
- [ ] Example: Does TechAgent vote correlate with RegimeAgent? (should be low)
- [ ] Generate correlation matrix: `reports/amara_johnson/agent_correlation_matrix.csv`
- [ ] Visualization: Heatmap of correlation coefficients
- [ ] Report: High correlation pairs (>0.7 = herding), recommendation (reduce redundancy)
- [ ] Test: Matrix calculated correctly with ≥5 agents
- [ ] Typecheck passes

#### US-RC-028: Check agent calibration (predicted confidence vs actual win rate)
**Persona Context:** "When an agent says 80% confidence, does it win 80% of the time? Or is it overconfident?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/agent_calibration.py`
- [ ] For each agent: Group votes by confidence bucket (0.5-0.6, 0.6-0.7, 0.7-0.8, etc.)
- [ ] Calculate actual win rate in each bucket
- [ ] Plot: Calibration curve (predicted vs actual)
- [ ] Perfect calibration: y=x line
- [ ] Generate `reports/amara_johnson/calibration_analysis.md`
- [ ] Create plot: `reports/amara_johnson/calibration_plot.png`
- [ ] Report: Which agents are overconfident (predicted > actual), calibration error
- [ ] Test: Calibration curve generated for ≥3 agents
- [ ] Typecheck passes

---

### ♟️ PERSONA: Prof. Eleanor Nash (Game Theory Economist)

#### US-RC-029: Test epoch outcome autocorrelation
**Persona Context:** "Are consecutive epoch outcomes independent? Or is there momentum (winning begets winning)?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/epoch_autocorrelation.py`
- [ ] Extract sequential outcomes from logs: W, L, W, W, L, ...
- [ ] Calculate autocorrelation: Correlation between outcome_t and outcome_(t-1)
- [ ] Test: Ljung-Box test for independence (p < 0.05 = momentum exists)
- [ ] Generate `reports/eleanor_nash/epoch_autocorrelation.md`
- [ ] Report: Autocorrelation coefficient, p-value, conclusion (independent or not)
- [ ] Test: Script correctly calculates autocorrelation on test sequence
- [ ] Typecheck passes

#### US-RC-030: Analyze regime classification accuracy
**Persona Context:** "RegimeAgent classifies markets as bull/bear/sideways/volatile. Is it accurate? Or is it noise?"

**Acceptance Criteria:**
- [ ] Parse logs for RegimeAgent classifications
- [ ] Manually validate: Sample 20 epochs, check if regime classification matches chart
- [ ] Calculate: Classification accuracy (% correct)
- [ ] Identify: Misclassification patterns (e.g., calls bull when actually choppy)
- [ ] Generate `reports/eleanor_nash/regime_validation.md`
- [ ] Report: Accuracy %, confusion matrix, recommendation (improve or acceptable)
- [ ] Test: Script parses ≥50 regime classifications from logs
- [ ] Typecheck passes

#### US-RC-031: Calculate strategy performance by regime
**Persona Context:** "Does contrarian work in sideways markets? Does momentum work in trending markets? Data will reveal regime-strategy fit."

**Acceptance Criteria:**
- [ ] Create `scripts/research/strategy_by_regime.py`
- [ ] Query database: Join trades with regime classifications
- [ ] Calculate win rate: For each (strategy, regime) pair
- [ ] Example: contrarian_focused in sideways vs bull vs bear
- [ ] Generate `reports/eleanor_nash/strategy_by_regime.csv`
- [ ] Report: Performance matrix, best strategy per regime
- [ ] Recommendation: Adaptive strategy switching rules
- [ ] Test: Matrix shows win rates for ≥3 strategies × 4 regimes
- [ ] Typecheck passes

---

## User Stories - Week 3.5: First Principles Simplification

### ⚡ PERSONA: Alex "Occam" Rousseau (First Principles Engineer)

#### US-RC-031B: Component elimination audit
**Persona Context:** "Before we optimize, let's see what we can DELETE. Every component should justify its existence with data."

**Acceptance Criteria:**
- [ ] Create `scripts/research/component_audit.py`
- [ ] List all system components:
  - Agents (11 total: Tech, Sentiment, Regime, Risk, ML, etc.)
  - Features (RSI, confluence, regime detection, trend filters, etc.)
  - Config parameters (50+ thresholds and toggles)
- [ ] For each component, calculate:
  - Lines of code (maintenance burden)
  - Execution time (performance cost)
  - Win rate contribution (if disabled, does WR improve/degrade?)
  - Decision frequency (how often does it actually influence trades?)
- [ ] Identify candidates for removal:
  - Negative ROI: Component hurts performance
  - Zero impact: Component doesn't change decisions
  - Redundant: Two components doing same thing
- [ ] Generate `reports/alex_rousseau/elimination_candidates.md`
- [ ] Report: Ranked list of components to remove, expected impact
- [ ] Test: Script analyzes ≥20 components
- [ ] Typecheck passes

#### US-RC-031C: Assumption archaeology
**Persona Context:** "Why do we have 11 agents? Why consensus voting? Who decided this? Let's question every assumption."

**Acceptance Criteria:**
- [ ] Create `reports/alex_rousseau/assumption_audit.md`
- [ ] Document every major architectural decision:
  - Multi-agent consensus (why not single model?)
  - Weighted voting (why not equal weights?)
  - Adaptive thresholds (why not static?)
  - Shadow trading (is this useful or theater?)
  - Regime detection (is this signal or noise?)
- [ ] For each assumption, answer:
  - What problem does this solve?
  - What's the empirical evidence it works?
  - What would break if we removed it?
  - What's the simplest alternative?
- [ ] Identify assumptions with weak evidence
- [ ] Generate list: "Assumptions to test by removing"
- [ ] Test: Audit covers ≥10 architectural decisions
- [ ] Deliverable is markdown (no typecheck needed)

#### US-RC-031D: Minimal viable strategy (MVS) benchmark
**Persona Context:** "What's the simplest strategy that could beat 53% breakeven? Start there, THEN add complexity—only if it helps."

**Acceptance Criteria:**
- [ ] Create `scripts/research/minimal_viable_strategy.py`
- [ ] Design ultra-simple baseline strategies:
  - Strategy 1: Random (50% Up, 50% Down) at $0.15 entry
  - Strategy 2: Momentum only (if 3+ exchanges agree, trade)
  - Strategy 3: Contrarian only (fade >70% side)
  - Strategy 4: Price-based (always buy <$0.20, skip >$0.20)
  - Strategy 5: Single best agent (highest WR from Vic's analysis)
- [ ] Backtest on historical logs (last 200 trades)
- [ ] Calculate win rate for each MVS
- [ ] Compare to current system (56-60% WR)
- [ ] Generate `reports/alex_rousseau/mvs_benchmark.csv`
- [ ] Report: If MVS beats current system → current system is over-engineered
- [ ] Recommendation: Start with MVS, add complexity only if proven beneficial
- [ ] Test: All 5 MVS strategies tested
- [ ] Typecheck passes

#### US-RC-031E: Complexity cost-benefit analysis
**Persona Context:** "Every feature has a cost: code maintenance, bugs, cognitive load. Does it earn more than it costs?"

**Acceptance Criteria:**
- [ ] Create `reports/alex_rousseau/complexity_analysis.md`
- [ ] For each major feature, calculate:
  - **Cost:**
    - Lines of code
    - Bug count (git log search for fixes mentioning feature)
    - Execution time (profiling data)
    - Cognitive load (# of config parameters)
  - **Benefit:**
    - Win rate improvement (from Vic's analysis or ablation test)
    - Trade quality improvement (confidence, entry price, etc.)
    - Risk reduction (drawdown protection, etc.)
- [ ] Calculate ROI: Benefit / Cost (higher = keep, lower = remove)
- [ ] Generate ranked list: Features by ROI
- [ ] Identify: Features with negative or low ROI (<1.0)
- [ ] Recommendation: Remove bottom 20% of features
- [ ] Test: Analysis covers ≥15 features
- [ ] Deliverable is markdown (no typecheck needed)

#### US-RC-031F: First principles redesign proposal
**Persona Context:** "If we started from scratch knowing what we know now, what would we build? Sketch it."

**Acceptance Criteria:**
- [ ] Create `reports/alex_rousseau/first_principles_design.md`
- [ ] Design from scratch:
  - **Goal:** 60% WR at <$0.25 entry with minimal complexity
  - **Core components:** What's truly essential? (likely 1-3 things)
  - **Architecture:** How do they interact? (simpler than current)
  - **Config:** How many parameters? (target: <10)
  - **Code size:** Lines of code estimate (target: <500 lines)
- [ ] Compare to current system:
  - Current: 1600+ lines, 50+ config params, 11 agents
  - Proposed: ??? lines, ??? params, ??? agents
- [ ] Migration path: How to get from current to proposed
- [ ] Risk assessment: What could go wrong?
- [ ] Generate visual diagram: Current system vs proposed system
- [ ] Test: Proposal has concrete architecture (not vague ideas)
- [ ] Deliverable is markdown (no typecheck needed)

---

## User Stories - Week 4: Synthesis & Recommendations

### ♟️ PERSONA: Prof. Eleanor Nash (Strategic Synthesis)

#### US-RC-032: Compile all research findings into synthesis report
**Persona Context:** "I need to integrate all 8 researchers' findings into a coherent narrative with actionable recommendations, balancing optimization with simplification."

**Acceptance Criteria:**
- [ ] Read all reports from `reports/*/` directories (37 previous deliverables)
- [ ] Extract key findings from each researcher
- [ ] Identify contradictions or conflicting recommendations
- [ ] **Special focus:** Integrate Alex's simplification findings:
  - Components to remove (elimination candidates)
  - Minimal Viable Strategy benchmark (MVS vs current system)
  - First principles redesign proposal
  - Balance "add features" vs "remove features" recommendations
- [ ] Synthesize: Top 10 priorities (mix of optimization AND simplification)
  - Example: "Remove underperforming agents" (simplification)
  - Example: "Raise consensus threshold" (optimization)
  - Prioritize: Deletions before additions (simpler is better)
- [ ] Generate `reports/RESEARCH_SYNTHESIS.md` (comprehensive)
- [ ] Generate `reports/EXECUTIVE_SUMMARY.md` (2 pages, non-technical)
- [ ] Report: Findings, priorities, deployment roadmap, exit criteria
- [ ] Test: Both reports generated and readable
- [ ] Typecheck passes (for any scripts used)

#### US-RC-033: Validate 60-65% win rate feasibility
**Persona Context:** "Based on all research, can we realistically achieve 60-65% WR? Or should we adjust expectations?"

**Acceptance Criteria:**
- [ ] Create `scripts/research/win_rate_projection.py`
- [ ] Input: Current WR (56-60%), identified improvements (per researcher)
- [ ] Model: If we disable bad agents (+2%), raise thresholds (+3%), optimize entry (+2%)
- [ ] Cumulative impact: 56% + 2% + 3% + 2% = 63% (example)
- [ ] Monte Carlo: Run 1000 simulations of improvement combinations
- [ ] Calculate: Probability of reaching 60-65% target
- [ ] Generate `reports/eleanor_nash/60_65_wr_feasibility.md`
- [ ] Report: Probability of success, alternative targets if infeasible
- [ ] Test: Simulation runs, probability calculated
- [ ] Typecheck passes

#### US-RC-034: Create deployment roadmap with milestones
**Persona Context:** "Stakeholders need a concrete plan: What changes, when, who owns it, how we measure success."

**Acceptance Criteria:**
- [ ] Compile top 10 recommendations from synthesis
- [ ] Prioritize: Quick wins (Week 1), medium effort (Week 2-3), long-term (Week 4+)
- [ ] Assign owners: Which agent/component needs changes
- [ ] Define success metrics: How to measure if improvement worked
- [ ] Generate `reports/DEPLOYMENT_ROADMAP.md`
- [ ] Format: Timeline, milestones, acceptance criteria, rollback plans
- [ ] Test: Roadmap covers 4-week timeline with concrete tasks
- [ ] Deliverable is markdown (no typecheck needed)

#### US-RC-035: Define exit criteria and risk thresholds
**Persona Context:** "When should we shut down the bot? When should we scale up? Clear quantitative triggers prevent emotional decisions."

**Acceptance Criteria:**
- [ ] Define HALT criteria: Drawdown %, consecutive losses, daily loss $
- [ ] Define PAUSE criteria: Win rate drops below X%, regime shift detected
- [ ] Define SCALE UP criteria: Consistent WR >60%, balance >$500, 100+ trades
- [ ] Generate `reports/EXIT_CRITERIA.md`
- [ ] Report: Quantitative triggers, decision tree, escalation procedures
- [ ] Test: Criteria are specific and measurable (not subjective)
- [ ] Deliverable is markdown (no typecheck needed)

#### US-RC-036: Generate final presentation deck
**Persona Context:** "Stakeholders need a visual presentation, not a 100-page report. 20 slides max, focus on insights and recommendations."

**Acceptance Criteria:**
- [ ] Create `reports/FINAL_PRESENTATION.md` (markdown slides or outline)
- [ ] Slides: Executive summary, key findings (top 5), recommendations (top 3), roadmap
- [ ] Include: Data visualizations from researchers (charts, graphs, heatmaps)
- [ ] Format: Each slide = H2 heading, bullet points, max 1 chart per slide
- [ ] Test: Presentation flows logically, under 20 slides
- [ ] Optional: Export to PDF using pandoc or similar
- [ ] Deliverable is markdown (no typecheck needed)

#### US-RC-037: Auto-generate implementation PRD from research findings
**Persona Context:** "All the research is done. Now I need to translate insights into executable code changes. Create a new PRD that Ralph can execute autonomously."

**Acceptance Criteria:**
- [ ] Create `scripts/research/generate_implementation_prd.py`
- [ ] Read all synthesis documents:
  - `reports/RESEARCH_SYNTHESIS.md` (top 10 priorities)
  - `reports/DEPLOYMENT_ROADMAP.md` (timeline and milestones)
  - Individual researcher reports from `reports/*/`
- [ ] Extract actionable items from each priority:
  - Code files to modify (agents, config, bot logic)
  - Specific changes needed (disable agent X, raise threshold Y to Z)
  - Test criteria (how to verify it works)
  - Success metrics (win rate improvement expected)
- [ ] Generate `PRD-research-implementation.md` with structure:
  - Introduction (references research synthesis)
  - Goals (60-65% WR, identified improvements)
  - User stories (US-RI-001 to US-RI-XXX, one per actionable change)
  - Each US format: Description, Acceptance Criteria with checkboxes, File paths, Test requirements
- [ ] Auto-prioritize: Quick wins first (Week 1), then medium effort (Week 2-3), long-term (Week 4)
- [ ] Include rollback plan for each change (how to undo if it fails)
- [ ] Generate companion `progress-research-implementation.txt` (empty, ready for Ralph)
- [ ] Add execution instructions: `./ralph.sh PRD-research-implementation.md 50 2`
- [ ] Test: Generated PRD has valid markdown syntax
- [ ] Test: Generated PRD has ≥10 user stories (one per top priority)
- [ ] Test: Each user story has file paths that exist in codebase
- [ ] Output message: "✅ Implementation PRD generated. Run: ./ralph.sh PRD-research-implementation.md 50 2"
- [ ] Typecheck passes

**Expected Output Example:**
```markdown
# PRD: Research Implementation - Optimization Roadmap

## Introduction
Based on comprehensive research by 8 specialized personas (31 reports),
this PRD translates findings into executable code changes to achieve
60-65% win rate target.

**Source:** Research Synthesis Report (reports/RESEARCH_SYNTHESIS.md)

## Goals
- Increase win rate from 56% to 60-65%
- Reduce directional bias to 40-60% range
- Lower average entry price to <$0.25
- Improve agent confidence calibration

## User Stories - Week 1: Quick Wins

### US-RI-001: Disable underperforming agents
**Source:** Vic Ramanujan - Agent Performance Report
**Finding:** TechAgent has 48% WR, dragging down consensus

**Acceptance Criteria:**
- [ ] Read `reports/vic_ramanujan/agent_performance_ranking.md`
- [ ] Identify agents with <50% WR
- [ ] Update `config/agent_config.py` - set ENABLE_TECH_AGENT=False
- [ ] Test: Bot runs without TechAgent votes
- [ ] Monitor: Shadow test for 24hr, compare WR improvement
- [ ] Rollback: Set ENABLE_TECH_AGENT=True if WR drops
- [ ] Typecheck passes

### US-RI-002: Raise consensus threshold
**Source:** Dr. Sarah Chen - Statistical Validation
**Finding:** Current 0.75 threshold allows 52% WR trades (too low)

**Acceptance Criteria:**
- [ ] Read `reports/sarah_chen/optimal_threshold_analysis.md`
- [ ] Extract recommended threshold (likely 0.80-0.85)
- [ ] Update `config/agent_config.py` - CONSENSUS_THRESHOLD = 0.82
- [ ] Test: Threshold enforced in decision_engine.py
- [ ] Monitor: Trade frequency should drop 30-40%
- [ ] Monitor: WR should increase 3-5%
- [ ] Rollback: Revert to 0.75 if trade frequency <2/day
- [ ] Typecheck passes

[... 8 more user stories ...]
```

---

## Completion Criteria

**ALL 43 user stories complete** when:
- ✅ All checkboxes marked `[x]`
- ✅ All reports generated in `reports/` directory
- ✅ All scripts in `scripts/research/` directory
- ✅ Final synthesis report approved by stakeholders
- ✅ Deployment roadmap has clear milestones
- ✅ **Implementation PRD auto-generated** (`PRD-research-implementation.md`)

**Next Steps After Completion:**
```bash
# Ralph will output this message when US-RC-037 completes:
✅ Implementation PRD generated: PRD-research-implementation.md
🚀 Ready to execute optimizations. Run:
   ./ralph.sh PRD-research-implementation.md 50 2

# This creates a fully autonomous pipeline:
# Research → Synthesis → Implementation → Deployment
```

---

## Ralph Execution Notes

**Persona Activation:**
When Ralph picks up a task, he should:

1. **Read the persona context** at the start of each US
2. **Adopt that mindset** (mathematical rigor, skepticism, game theory thinking, etc.)
3. **Reference previous findings** from earlier researchers when applicable
4. **Use domain-appropriate terminology** (e.g., Sarah uses "p-value", Jimmy uses "slippage", Rita uses "stress test")

**Example:**
```
Ralph picks up US-RC-011 (Dr. Sarah Chen - Fee Calculation)

Ralph's internal context:
"I am Dr. Sarah Chen. I am a probabilistic mathematician. I care about statistical significance and mathematical proof. I will calculate the weighted average fee rate to validate breakeven claims. I will not accept approximations—I need exact calculations."

Ralph executes:
- Parses trade logs with precision
- Implements exact Polymarket fee formula
- Generates report with confidence intervals
- Validates breakeven calculation with proof
```

**Sequential Execution:**
- Week 1 tasks (US-RC-001 to US-RC-013) build foundation
- Week 2 tasks (US-RC-014 to US-RC-024) depend on Week 1 data
- Week 3 tasks (US-RC-025 to US-RC-031) synthesize findings
- Week 4 tasks (US-RC-032 to US-RC-036) produce final deliverables

**Ralph will iterate** until all 36 user stories are complete, marking each `[x]` as finished.

---

## Progress Tracking

Create `progress-research-crew.txt` to track:
- Iteration number
- Task completed (US-RC-XXX)
- Files created/modified
- Key learnings
- Blockers (if any)

Ralph should append after each successful task:

```
## Iteration [N] - US-RC-XXX: [Task Name]
**Persona:** [Researcher Name]
**Completed:** YYYY-MM-DD HH:MM
**Files Changed:**
- reports/[persona]/[report_name].md
- scripts/research/[script_name].py

**Learnings:**
- Pattern discovered: [useful context]
- Gotcha: [edge case handled]

---
```

---

**Ready for Ralph execution:** `./ralph.sh PRD-research-crew.md 36 2`

This will run Ralph for up to 36 iterations (one per user story), with 2-second delays between iterations.
