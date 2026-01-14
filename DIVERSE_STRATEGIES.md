# Diverse Shadow Trading Strategies

**Date:** 2026-01-14
**Purpose:** Test truly different approaches to identify what actually works

---

## Problem Identified

All 5 original strategies showed **identical performance** (1W/11L, 8.3% win rate) because they were too similar:
- All used same 4 agents
- Only differed in threshold levels and minor weight adjustments
- All made essentially the same decisions

**Solution:** Create fundamentally different strategies that will produce divergent results.

---

## New Strategy Categories

### 1. Inverse/Contrarian Strategies ⚡

These strategies **trade the OPPOSITE direction** of what the agents recommend.

#### `inverse_consensus`
- **Theory:** What if our agents are consistently wrong? Maybe the opposite is right.
- **Implementation:** Negative weights on ALL agents (-1.0)
- **Expected:** If current strategies lose, this should win

#### `inverse_momentum`
- **Theory:** Fade strong momentum - "buy fear, sell greed"
- **Implementation:** -1.5 weight on TechAgent, -1.0 on Regime
- **Expected:** Profit from reversals after strong moves

#### `inverse_sentiment`
- **Theory:** Go WITH the crowd instead of fading it
- **Implementation:** -1.5 weight on SentimentAgent
- **Expected:** Test if "fade the fade" works better

### 2. Extreme Thresholds 🎯

#### `ultra_conservative`
- **Theory:** Only take absolute best setups
- **Thresholds:** 0.85 consensus, 0.75 confidence (very high)
- **Position size:** 8% (smaller)
- **Expected:** Very few trades, but high win rate

#### `ultra_aggressive`
- **Theory:** Take every signal, volume compensates for losses
- **Thresholds:** 0.25 consensus, 0.25 confidence (very low)
- **Position size:** 25% (larger)
- **Expected:** Many trades, lower win rate, but potential for outliers

### 3. Single Agent Isolation 🔬

Test each agent individually to see which one is actually valuable.

#### `tech_only`
- **Only uses:** TechAgent (momentum/confluence)
- **Disabled:** Sentiment, Regime, Candlestick
- **Tests:** Pure momentum/technical analysis

#### `sentiment_only`
- **Only uses:** SentimentAgent (contrarian fading)
- **Disabled:** Tech, Regime, Candlestick
- **Tests:** Pure contrarian strategy

#### `regime_only`
- **Only uses:** RegimeAgent (market structure)
- **Disabled:** Tech, Sentiment, Candlestick
- **Tests:** Pure market regime analysis

---

## Why This Will Show Differences

### Before (Original Strategies):
```
All strategies: Same agents, minor tweaks → Same decisions → Same results
```

### After (Diverse Strategies):
```
inverse_consensus:      Trade OPPOSITE    → Should win if agents wrong
ultra_conservative:     Take 5% of trades → High quality only
ultra_aggressive:       Take 95% of trades → Volume play
tech_only:             Momentum only      → Isolate tech signals
inverse_momentum:      Fade momentum      → Reversal strategy
```

**These WILL produce different results** because they make fundamentally different decisions.

---

## Expected Outcomes

### Scenario 1: Current Agents Are Wrong
- `inverse_consensus` wins
- `inverse_momentum` wins
- Original strategies keep losing
- **Action:** Deploy inverse strategy to live bot

### Scenario 2: We're Being Too Picky
- `ultra_aggressive` wins (more trades = more opportunities)
- `conservative`/`ultra_conservative` struggle (miss opportunities)
- **Action:** Lower thresholds on live bot

### Scenario 3: One Agent is Hurting Us
- `tech_only` or `sentiment_only` wins
- Others lose when that agent is included
- **Action:** Disable or reduce weight on underperforming agent

### Scenario 4: We Need Higher Quality
- `ultra_conservative` wins (fewer but better trades)
- `ultra_aggressive` loses (too many bad trades)
- **Action:** Raise thresholds on live bot

---

## Testing Matrix

| Strategy | Agents Used | Direction | Threshold | Trade Freq |
|----------|-------------|-----------|-----------|------------|
| conservative | All 4 | Normal | High (0.75) | Low |
| aggressive | All 4 | Normal | Low (0.55) | High |
| inverse_consensus | All 4 | **OPPOSITE** | Normal | Medium |
| inverse_momentum | Tech inverted | **OPPOSITE** | Normal | Medium |
| inverse_sentiment | Sentiment inverted | **OPPOSITE** | Normal | Medium |
| ultra_conservative | All 4 | Normal | **Very High (0.85)** | Very Low |
| ultra_aggressive | All 4 | Normal | **Very Low (0.25)** | Very High |
| tech_only | Tech ONLY | Normal | Low (0.30) | Medium |
| sentiment_only | Sentiment ONLY | Normal | Low (0.30) | Medium |
| regime_only | Regime ONLY | Normal | Low (0.30) | Low |

---

## Implementation Details

### Negative Weights (Inverse Strategies)

When agent weights are negative, the weighted score calculation inverts:
```python
# Normal strategy:
TechAgent votes Up with confidence 0.8
weighted_score += 1.0 * 0.8 = +0.8  # Pushes toward Up

# Inverse strategy:
TechAgent votes Up with confidence 0.8
weighted_score += -1.0 * 0.8 = -0.8  # Pushes toward Down

Final decision: If weighted_score > 0 → Up, else → Down
With negative weights: Trades opposite direction
```

### Zero Weights (Single Agent Strategies)

Setting weight to 0.0 effectively disables that agent:
```python
# tech_only strategy:
agent_weights = {
    'TechAgent': 1.0,      # Only this counts
    'SentimentAgent': 0.0, # Ignored
    'RegimeAgent': 0.0,    # Ignored
    'CandlestickAgent': 0.0 # Ignored
}
```

---

## Analysis After 50+ Trades

### Key Questions to Answer:

1. **Are we wrong or just unlucky?**
   - If `inverse_consensus` wins → We're systematically wrong
   - If all strategies lose → Market is hard/fees too high

2. **Which agent adds value?**
   - Compare `tech_only`, `sentiment_only`, `regime_only`
   - Best single agent should be weighted highest

3. **What's the right selectivity?**
   - Compare `ultra_conservative`, `conservative`, `aggressive`, `ultra_aggressive`
   - Find optimal threshold sweet spot

4. **Does momentum work?**
   - Compare `momentum_focused` vs `inverse_momentum`
   - If inverse wins → We should fade, not follow

5. **Is contrarian working?**
   - Compare `sentiment_only` vs `inverse_sentiment`
   - If inverse wins → Stop fading, go with crowd

---

## Deployment Steps

1. **Backup current database:**
   ```bash
   cp simulation/trade_journal.db simulation/trade_journal.db.before_diverse
   ```

2. **Deploy new strategies:**
   - Code is already committed and pushed
   - Will restart with 10 diverse strategies (up from 5 similar ones)

3. **Wait for data:**
   - Need 50-100 trades per strategy
   - Should take 24-48 hours

4. **Analyze results:**
   ```bash
   python3 simulation/analyze.py compare
   python3 simulation/analyze.py details --strategy inverse_consensus
   ```

5. **Take action:**
   - Deploy best-performing strategy to live bot
   - Or adjust current strategy based on insights

---

## Success Criteria

After this deployment, we should see:

✅ **Divergent performance** - Not all strategies at 8.3% win rate
✅ **Clear winner** - At least one strategy with >60% win rate
✅ **Clear loser** - At least one strategy with <30% win rate
✅ **Actionable insights** - Know what to change in live bot

If all strategies still show similar results, that tells us:
- Market is truly efficient for these 15-min windows
- Or our edge is being eaten by fees
- Or sample size still too small (wait for more data)

---

## Risk Assessment

**Low Risk:**
- All strategies are virtual (shadow trading)
- No real money at risk
- Can disable anytime

**Benefit:**
- Will definitively answer: "Are our agents helping or hurting?"
- Will identify which approach actually works
- Will save money by not deploying bad strategies live

This is the **scientific method** applied to trading strategy development.
