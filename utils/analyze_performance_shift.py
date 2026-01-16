#!/usr/bin/env python3
"""
Performance Shift Analyzer

Analyzes recent trading performance to identify regime changes,
pattern shifts, and reasons for declining win rates.

Usage:
    python3 utils/analyze_performance_shift.py [--hours 4]
"""

import sqlite3
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json


def analyze_performance_shift(db_path: str = 'simulation/trade_journal.db', hours: int = 4):
    """Compare recent performance vs previous period."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(hours=hours)
    previous_start = now - timedelta(hours=hours * 2)

    print("=" * 80)
    print(f"PERFORMANCE SHIFT ANALYSIS - Last {hours} Hours vs Previous {hours} Hours")
    print("=" * 80)

    # Recent period stats
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
            AVG(CASE WHEN outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100 as win_rate,
            SUM(pnl) as total_pnl,
            AVG(confidence) * 100 as avg_confidence,
            AVG(entry_price) as avg_entry
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND t.timestamp >= ?
    """, (recent_start.isoformat(),))

    recent = cursor.fetchone()

    # Previous period stats
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
            AVG(CASE WHEN outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100 as win_rate,
            SUM(pnl) as total_pnl,
            AVG(confidence) * 100 as avg_confidence,
            AVG(entry_price) as avg_entry
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND t.timestamp >= ? AND t.timestamp < ?
    """, (previous_start.isoformat(), recent_start.isoformat()))

    previous = cursor.fetchone()

    # Print comparison
    print(f"\n📊 OVERALL COMPARISON")
    print("-" * 80)
    print(f"{'Metric':<20} {'Recent':<20} {'Previous':<20} {'Change':<20}")
    print("-" * 80)

    metrics = [
        ("Trades", recent[0], previous[0]),
        ("Wins", recent[1], previous[1]),
        ("Losses", recent[2], previous[2]),
        ("Win Rate (%)", recent[3], previous[3]),
        ("P&L ($)", recent[4] or 0, previous[4] or 0),
        ("Avg Confidence (%)", recent[5] or 0, previous[5] or 0),
        ("Avg Entry ($)", recent[6] or 0, previous[6] or 0),
    ]

    for name, rec, prev in metrics:
        if prev and prev != 0:
            if "Rate" in name or "Confidence" in name or "Entry" in name:
                change = rec - prev
                change_str = f"{'+' if change > 0 else ''}{change:.1f}"
            else:
                change_pct = ((rec - prev) / prev) * 100
                change_str = f"{'+' if change_pct > 0 else ''}{change_pct:.1f}%"
        else:
            change_str = "N/A"

        print(f"{name:<20} {rec:<20.2f} {prev:<20.2f} {change_str:<20}")

    # Crypto breakdown
    print(f"\n🪙 CRYPTO BREAKDOWN (Recent)")
    print("-" * 80)
    cursor.execute("""
        SELECT
            CASE
                WHEN market_title LIKE '%BTC%' THEN 'BTC'
                WHEN market_title LIKE '%ETH%' THEN 'ETH'
                WHEN market_title LIKE '%SOL%' THEN 'SOL'
                WHEN market_title LIKE '%XRP%' THEN 'XRP'
                ELSE 'Other'
            END as crypto,
            COUNT(*) as trades,
            SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100 as win_rate,
            SUM(pnl) as pnl,
            AVG(entry_price) as avg_entry
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND t.timestamp >= ?
        GROUP BY crypto
        ORDER BY pnl DESC
    """, (recent_start.isoformat(),))

    crypto_stats = cursor.fetchall()
    print(f"{'Crypto':<8} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'P&L':<10} {'Avg Entry':<10}")
    print("-" * 80)
    for stat in crypto_stats:
        print(f"{stat[0]:<8} {stat[1]:<8} {stat[2]:<6} {stat[3]:<8.1f} ${stat[4]:<9.2f} ${stat[5]:.3f}")

    # Direction breakdown
    print(f"\n📈 DIRECTION BREAKDOWN (Recent)")
    print("-" * 80)
    cursor.execute("""
        SELECT
            side,
            COUNT(*) as trades,
            SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
            AVG(CASE WHEN outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100 as win_rate,
            SUM(pnl) as pnl,
            AVG(entry_price) as avg_entry
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND t.timestamp >= ?
        GROUP BY side
        ORDER BY pnl DESC
    """, (recent_start.isoformat(),))

    direction_stats = cursor.fetchall()
    print(f"{'Direction':<10} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'P&L':<10} {'Avg Entry':<10}")
    print("-" * 80)
    for stat in direction_stats:
        print(f"{stat[0]:<10} {stat[1]:<8} {stat[2]:<6} {stat[3]:<8.1f} ${stat[4]:<9.2f} ${stat[5]:.3f}")

    # Losing trades analysis
    print(f"\n❌ RECENT LOSING TRADES")
    print("-" * 80)
    cursor.execute("""
        SELECT
            t.timestamp,
            t.market_title,
            t.side,
            t.confidence * 100 as confidence,
            t.entry_price,
            t.size,
            o.pnl,
            t.market_data
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND o.outcome = 'loss'
        AND t.timestamp >= ?
        ORDER BY t.timestamp DESC
        LIMIT 20
    """, (recent_start.isoformat(),))

    losses = cursor.fetchall()
    if losses:
        print(f"{'Time':<6} {'Market':<40} {'Side':<5} {'Conf%':<7} {'Entry':<8} {'Loss':<8}")
        print("-" * 80)
        for loss in losses:
            ts = datetime.fromisoformat(loss[0]).strftime('%H:%M')
            market = loss[1][:38] if len(loss[1]) > 38 else loss[1]
            print(f"{ts:<6} {market:<40} {loss[2]:<5} {loss[3]:<7.1f} ${loss[4]:<7.3f} ${loss[6]:<7.2f}")
    else:
        print("No losses in recent period")

    # Pattern analysis
    print(f"\n🔍 PATTERN ANALYSIS")
    print("-" * 80)

    # Entry price distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN entry_price < 0.15 THEN '<$0.15'
                WHEN entry_price < 0.25 THEN '$0.15-0.25'
                WHEN entry_price < 0.35 THEN '$0.25-0.35'
                WHEN entry_price < 0.50 THEN '$0.35-0.50'
                ELSE '>$0.50'
            END as price_range,
            COUNT(*) as trades,
            AVG(CASE WHEN outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100 as win_rate,
            SUM(pnl) as pnl
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND t.timestamp >= ?
        GROUP BY price_range
        ORDER BY win_rate DESC
    """, (recent_start.isoformat(),))

    entry_distribution = cursor.fetchall()
    if entry_distribution:
        print("\nEntry Price Performance:")
        print(f"{'Range':<15} {'Trades':<8} {'WR%':<8} {'P&L':<10}")
        print("-" * 50)
        for dist in entry_distribution:
            print(f"{dist[0]:<15} {dist[1]:<8} {dist[2]:<8.1f} ${dist[3]:<9.2f}")

    # Confidence distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN confidence < 0.50 THEN '<50%'
                WHEN confidence < 0.55 THEN '50-55%'
                WHEN confidence < 0.60 THEN '55-60%'
                WHEN confidence < 0.65 THEN '60-65%'
                ELSE '>65%'
            END as conf_range,
            COUNT(*) as trades,
            AVG(CASE WHEN outcome = 'win' THEN 1.0 ELSE 0.0 END) * 100 as win_rate,
            SUM(pnl) as pnl
        FROM trades t
        JOIN outcomes o ON t.id = o.trade_id
        WHERE t.strategy = 'live'
        AND t.timestamp >= ?
        GROUP BY conf_range
        ORDER BY win_rate DESC
    """, (recent_start.isoformat(),))

    conf_distribution = cursor.fetchall()
    if conf_distribution:
        print("\nConfidence Level Performance:")
        print(f"{'Range':<15} {'Trades':<8} {'WR%':<8} {'P&L':<10}")
        print("-" * 50)
        for dist in conf_distribution:
            print(f"{dist[0]:<15} {dist[1]:<8} {dist[2]:<8.1f} ${dist[3]:<9.2f}")

    # Key findings
    print(f"\n💡 KEY FINDINGS")
    print("-" * 80)

    findings = []

    # Win rate degradation
    if previous[3] and recent[3] < previous[3] - 5:
        findings.append(f"⚠️  Win rate dropped by {previous[3] - recent[3]:.1f}% (was {previous[3]:.1f}%, now {recent[3]:.1f}%)")

    # Direction imbalance
    if len(direction_stats) == 2:
        imbalance = abs(direction_stats[0][1] - direction_stats[1][1]) / sum(s[1] for s in direction_stats)
        if imbalance > 0.3:
            findings.append(f"⚠️  Directional imbalance: {imbalance*100:.1f}% skew (should be <30%)")

    # Entry price issues
    if entry_distribution:
        high_entry_trades = sum(d[1] for d in entry_distribution if '>$0' in d[0] and float(d[0].split('$')[1].split('-')[0]) > 0.35)
        total_trades = sum(d[1] for d in entry_distribution)
        if high_entry_trades / total_trades > 0.3:
            findings.append(f"⚠️  {high_entry_trades}/{total_trades} trades at >$0.35 entry (high fees!)")

    # Crypto-specific issues
    worst_crypto = crypto_stats[-1] if crypto_stats else None
    if worst_crypto and worst_crypto[3] < 40:
        findings.append(f"⚠️  {worst_crypto[0]} performing poorly: {worst_crypto[3]:.1f}% WR, ${worst_crypto[4]:.2f} P&L")

    # Confidence vs win rate mismatch
    if conf_distribution:
        for dist in conf_distribution:
            if '>60%' in dist[0] and dist[2] < 55:
                findings.append(f"⚠️  High confidence trades ({dist[0]}) underperforming: {dist[2]:.1f}% WR")

    if findings:
        for i, finding in enumerate(findings, 1):
            print(f"{i}. {finding}")
    else:
        print("✅ No major issues detected")

    # Recommendations
    print(f"\n📋 RECOMMENDATIONS")
    print("-" * 80)

    recommendations = []

    if recent[6] and recent[6] > 0.30:
        recommendations.append("• Lower MAX_ENTRY_PRICE to $0.25-0.30 (reduce fee drag)")

    if recent[3] < 53:
        recommendations.append("• Increase MIN_SIGNAL_STRENGTH threshold (filter weak signals)")

    if len(direction_stats) == 2 and abs(direction_stats[0][1] - direction_stats[1][1]) / sum(s[1] for s in direction_stats) > 0.3:
        recommendations.append("• Check regime detection - may have directional bias")

    if worst_crypto and worst_crypto[3] < 40:
        recommendations.append(f"• Consider temporarily disabling {worst_crypto[0]} trading")

    for dist in conf_distribution:
        if '>60%' in dist[0] and dist[2] < 55:
            recommendations.append("• ML model may be overconfident - retrain or recalibrate")

    if not recommendations:
        recommendations.append("• Continue monitoring - no immediate action needed")

    for rec in recommendations:
        print(rec)

    print("\n" + "=" * 80)

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze performance shifts")
    parser.add_argument('--hours', type=int, default=4, help='Hours to analyze (default: 4)')
    parser.add_argument('--db', type=str, default='simulation/trade_journal.db', help='Database path')

    args = parser.parse_args()

    try:
        analyze_performance_shift(db_path=args.db, hours=args.hours)
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure the database exists and is accessible.")
        print(f"Looking for: {args.db}")
