# Shadow Strategy Leaderboard Report

**Author:** Victor 'Vic' Ramanujan (Quantitative Strategist)
**Date:** 2026-01-16
**Data Source:** simulation/trade_journal.db

---

## Executive Summary

**Assessment:** INSUFFICIENT DATA
**Total Strategies Analyzed:** 0

⚠️ **No shadow strategy data available** (bot may not be running or database empty)

---

## Top 10 Strategies (by Total P&L)

*No strategies found in database*

---

## Recommendations

**Data Collection Phase:**
- Shadow trading system not populated yet
- Ensure bot is running with shadow strategies enabled
- Re-run this analysis after 50+ trades per strategy

---

## Methodology

**Data Source:** SQLite database `trade_journal.db`

**Query Logic:**
- Extract latest performance snapshot for each strategy
- Rank by total P&L (primary) and win rate (secondary)
- Calculate Sharpe ratio for strategies with ≥10 trades

**Sharpe Ratio Calculation:**
- `Sharpe = (avg_pnl / std_dev_pnl) * sqrt(n_trades)`
- Higher Sharpe = better risk-adjusted returns
- Requires ≥10 trades for reliable calculation

**Baseline Strategy:**
- Random 50/50 coin flip at typical entry price ($0.20)
- If default strategy underperforms random, system has negative edge
