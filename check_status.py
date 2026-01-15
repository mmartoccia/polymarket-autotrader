#!/usr/bin/env python3
"""Quick status check for shadow trading and live bot"""
import sqlite3
import json
from datetime import datetime, timedelta

conn = sqlite3.connect("simulation/trade_journal.db")
cur = conn.cursor()

cutoff = datetime.now().timestamp() - 86400

cur.execute("""
    SELECT strategy,
           COUNT(*) as trades,
           SUM(CASE WHEN predicted_direction = actual_direction THEN 1 ELSE 0 END) as wins,
           ROUND(AVG(CASE WHEN predicted_direction = actual_direction THEN 1.0 ELSE 0.0 END)*100, 1) as win_pct,
           ROUND(SUM(pnl), 2) as total_pnl,
           ROUND(AVG(pnl), 2) as avg_pnl
    FROM outcomes
    WHERE timestamp > ?
    GROUP BY strategy
    ORDER BY total_pnl DESC
""", (cutoff,))

print("\n" + "="*90)
print("SHADOW TRADING PERFORMANCE (Last 24 Hours)")
print("="*90)
print(f"{'Strategy':<30} {'Trades':>7} {'Wins':>5} {'Win%':>6} {'Total P/L':>11} {'Avg P/L':>9}")
print("-"*90)

rows = cur.fetchall()
if rows:
    for row in rows:
        strategy, trades, wins, win_pct, total_pnl, avg_pnl = row
        pnl_indicator = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
        print(f"{pnl_indicator} {strategy:<28} {trades:>7} {wins:>5} {win_pct:>5.1f}% ${total_pnl:>9.2f} ${avg_pnl:>8.2f}")
else:
    print("No shadow trades in last 24 hours")

print("\n" + "="*90)
print("LIVE BOT STATUS")
print("="*90)
with open("state/trading_state.json") as f:
    state = json.load(f)

balance = state.get("current_balance", 0)
peak = state.get("peak_balance", 0)
mode = state.get("mode", "unknown")
drawdown = ((peak - balance) / peak * 100) if peak > 0 else 0

print(f"Current Balance: ${balance:.2f}")
print(f"Peak Balance: ${peak:.2f}")
print(f"Drawdown: {drawdown:.1f}%")
print(f"Mode: {mode}")
print(f"Daily P/L: ${state.get('daily_pnl', 0):.2f}")
print("="*90 + "\n")

conn.close()
