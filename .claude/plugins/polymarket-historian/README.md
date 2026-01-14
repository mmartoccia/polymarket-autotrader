# Polymarket Historian Plugin

**Continuous trade analysis and pattern detection for autonomous strategy optimization**

## Purpose

The Historian plugin acts as your **data scientist** - continuously collecting trade data, analyzing performance patterns, and surfacing actionable insights to improve the bot's win rate.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   POLYMARKET HISTORIAN                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. COLLECTION LAYER                                        │
│     • Snapshots: Trade logs, positions, agent votes         │
│     • Frequency: Every epoch / on-demand / post-task hook   │
│     • Storage: .claude/plugins/polymarket-historian/data/   │
│                                                             │
│  2. ANALYSIS LAYER                                          │
│     • Pattern Detection: Win rate by strategy/crypto/time   │
│     • Agent Performance: Which agents predict best          │
│     • Market Regime: Bull/bear/sideways effectiveness       │
│     • Entry Timing: Early vs late vs contrarian             │
│                                                             │
│  3. INSIGHT LAYER                                           │
│     • Recommendations: "Disable early BTC, boost SOL late"  │
│     • Anomalies: "XRP contrarian 85% WR - investigate"      │
│     • Optimization: Parameter tuning suggestions            │
│                                                             │
│  4. FEEDBACK LOOP                                           │
│     • Auto-update CLAUDE.md with findings                   │
│     • Generate strategy config recommendations              │
│     • Flag underperforming agents                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Collect Trade Data

```bash
# Manual snapshot
/historian-collect

# Automatic (via post-task hook)
# Runs after every /commit, /deploy, or Task completion
```

### Analyze Patterns

```bash
# Quick pattern analysis
/historian-patterns

# Full analysis with recommendations
/historian-analyze

# Comprehensive report (weekly/monthly)
/historian-report --period weekly
```

## What Gets Tracked

### Trade Metrics
- Entry price, exit price, P&L
- Strategy used (early/late/contrarian)
- Crypto, direction (Up/Down)
- Epoch timing (seconds into epoch)
- Agent votes and consensus score
- Market regime at time of trade

### Agent Performance
- Win rate per agent
- Confidence vs actual accuracy
- Best/worst cryptos per agent
- Regime-specific performance

### Market Patterns
- Win rate by crypto (BTC, ETH, SOL, XRP)
- Win rate by strategy
- Win rate by time-of-day
- Win rate by market regime

### Position Lifecycle
- Time held before redemption
- Probability evolution (entry → exit)
- Drawdown during hold period

## Data Storage

```
.claude/plugins/polymarket-historian/data/
├── snapshots/
│   ├── 2026-01-14_03-45-00.json    # Epoch snapshots
│   ├── 2026-01-14_04-00-00.json
│   └── ...
├── daily/
│   ├── 2026-01-14.json              # Daily aggregates
│   └── ...
├── patterns/
│   ├── winning_strategies.json      # Identified patterns
│   ├── agent_performance.json
│   └── market_regimes.json
└── insights/
    ├── recommendations.md           # Generated recommendations
    └── anomalies.md                 # Unusual patterns
```

## Example Insights

### Pattern Detection

```markdown
## Winning Patterns (70%+ WR)

1. **SOL Contrarian Late** - 85% WR (12/14 wins)
   - Entry: $0.08-0.15 (low probability side)
   - Timing: 720-840s into epoch
   - Regime: Bull momentum
   - Agent consensus: 65%+

2. **ETH Early Momentum** - 72% WR (18/25 wins)
   - Entry: $0.18-0.28
   - Timing: 60-180s into epoch
   - Regime: Any
   - Agent consensus: 80%+
   - TechAgent + RegimeAgent both agree

## Losing Patterns (40%- WR)

1. **BTC Extreme Contrarian** - 35% WR (7/20 losses)
   - Entry: $0.03-0.08 (extreme low probability)
   - Timing: Any
   - SentimentAgent high confidence but wrong
   - FIX: Now blocked by extreme contrarian filter

## Agent Performance

| Agent | Win Rate | Best Crypto | Worst Crypto | Confidence Accuracy |
|-------|----------|-------------|--------------|---------------------|
| TechAgent | 68% | SOL | BTC | 92% (well-calibrated) |
| SentimentAgent | 58% | ETH | XRP | 71% (overconfident) |
| RegimeAgent | 65% | BTC | SOL | 88% (good) |
| RiskAgent | N/A | - | - | 95% (veto accuracy) |

**Recommendation:** Reduce SentimentAgent weight by 15%, increase TechAgent weight by 10%
```

### Optimization Suggestions

```markdown
## Strategy Optimizations (Based on 500 trades)

1. **Disable Early BTC Trading**
   - Win rate: 42% (below breakeven with fees)
   - Reason: BTC too volatile in first 5 minutes
   - Action: Set EARLY_DISABLED_CRYPTOS = ['btc']

2. **Boost SOL Late Strategy**
   - Win rate: 83% (consistently strong)
   - Reason: SOL stabilizes well in late epoch
   - Action: Increase MAX_POSITION_USD for SOL late to $20

3. **Tighten XRP Contrarian Entry**
   - Win rate: 55% (barely profitable)
   - Reason: XRP false signals at $0.12-0.15
   - Action: Lower CONTRARIAN_MAX_ENTRY to $0.10 for XRP

4. **Time-of-Day Adjustment**
   - Best: 2am-6am UTC (75% WR) - low volume, clearer trends
   - Worst: 2pm-6pm UTC (52% WR) - high volatility
   - Action: Increase position size during Asian/early EU hours
```

## Integration with Bot

The historian **doesn't change the bot automatically** - it provides **data-driven recommendations** that you (or an orchestrator agent) can review and implement.

### Workflow

1. **Bot trades** → Logs written to `bot.log`
2. **Historian collects** → Parses logs into structured data
3. **Historian analyzes** → Identifies patterns
4. **Historian reports** → Generates recommendations
5. **Human/Agent reviews** → Decides what to implement
6. **Changes deployed** → Bot strategy updated
7. **Repeat** → Continuous improvement loop

## Commands Reference

### `/historian-collect`
**Purpose:** Snapshot current state (positions, balance, recent trades)

**Output:** Creates timestamped JSON in `data/snapshots/`

**When to use:** Manually capture important moments (big win/loss, strategy change)

---

### `/historian-patterns`
**Purpose:** Quick pattern extraction from recent data

**Output:** Console summary of win rates by strategy/crypto/time

**When to use:** Quick check on what's working/not working

---

### `/historian-analyze`
**Purpose:** Deep analysis with actionable recommendations

**Output:** Markdown report in `data/insights/recommendations.md`

**When to use:** Weekly review, before strategy changes

---

### `/historian-report --period <daily|weekly|monthly>`
**Purpose:** Comprehensive performance report

**Output:** Multi-page report with charts, tables, recommendations

**When to use:** Monthly reviews, investor updates, major strategy overhauls

## Advanced Features

### Auto-Detection of Regime Shifts

The historian detects when market conditions change and automatically flags if current strategy is suboptimal:

```
🚨 REGIME SHIFT DETECTED 🚨

Previous regime: Bull Momentum (Jan 10-13)
- Strategy: Momentum following
- Win rate: 72%

Current regime: Choppy Sideways (Jan 14+)
- Your strategy: Still momentum following
- Win rate: 48% ⚠️

RECOMMENDATION: Switch to contrarian strategy
Expected WR improvement: +18% (based on historical choppy periods)
```

### A/B Test Tracking

Track multiple strategies simultaneously:

```bash
# Enable A/B tracking
/historian-collect --experiment "contrarian_v2"

# Compare results
/historian-analyze --compare "baseline" "contrarian_v2"
```

### Backtest Validation

Compare historical pattern predictions vs actual outcomes:

```
Pattern: "SOL Late 85% WR"
- Predicted by historian: Jan 10 (based on Jan 1-9 data)
- Actual WR since prediction: 87% (23/26 wins)
- Validation: ✅ CONFIRMED (pattern held)
```

## Why This Matters

Without the historian:
- Gut feeling strategy changes
- "I think BTC is doing well" (maybe it's not)
- Manual log parsing (time-consuming)
- No data-driven optimization

With the historian:
- Evidence-based decisions
- "SOL contrarian has 85% WR in 14 trades - let's do more"
- Automated data collection
- Continuous improvement loop

**The historian turns your bot from a static strategy into a learning system.**

## Future Enhancements

- [ ] Real-time Slack/Discord alerts for anomalies
- [ ] ML-based pattern prediction (XGBoost, RandomForest)
- [ ] Auto-parameter tuning (grid search on historical data)
- [ ] Competitor analysis (track other bot behaviors)
- [ ] Market microstructure analysis (orderbook patterns)

## Installation

The plugin is already installed in `.claude/plugins/polymarket-historian/`.

To activate, simply use the commands:

```bash
/historian-collect   # Start collecting data
/historian-patterns  # See initial patterns
```

Data will accumulate over time, and insights will become more accurate with more trades.

---

**Remember:** The historian is a tool for **informed decision-making**, not a replacement for human judgment. Always review recommendations before implementing strategy changes.
