#!/usr/bin/env python3
"""
Time-of-Day Pattern Analysis

Analyzes whether certain hours of the day have predictable up/down biases.
Uses historical dataset to find optimal trading hours.
"""

import sys
from pathlib import Path
import sqlite3
from datetime import datetime
from typing import Dict, List

sys.path.append(str(Path(__file__).parent.parent))


def analyze_hourly_patterns(crypto: str, days: int = 7,
                           db_path: str = 'analysis/epoch_history.db') -> Dict:
    """
    Analyze up/down patterns by hour of day.

    Returns dict with hourly stats and best/worst hours to trade.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get hourly breakdown
    rows = conn.execute('''
        SELECT
            hour,
            direction,
            COUNT(*) as count,
            AVG(change_pct) as avg_change
        FROM epoch_outcomes
        WHERE crypto = ?
        AND date >= date('now', '-' || ? || ' days')
        GROUP BY hour, direction
        ORDER BY hour
    ''', (crypto, days)).fetchall()

    hourly_stats = {}
    for h in range(24):
        hourly_stats[h] = {
            'ups': 0,
            'downs': 0,
            'total': 0,
            'up_pct': 0.0,
            'avg_up_change': 0.0,
            'avg_down_change': 0.0
        }

    for row in rows:
        hour = row['hour']
        if row['direction'] == 'Up':
            hourly_stats[hour]['ups'] = row['count']
            hourly_stats[hour]['avg_up_change'] = row['avg_change']
        else:
            hourly_stats[hour]['downs'] = row['count']
            hourly_stats[hour]['avg_down_change'] = row['avg_change']

    # Calculate percentages
    for hour, stats in hourly_stats.items():
        stats['total'] = stats['ups'] + stats['downs']
        if stats['total'] > 0:
            stats['up_pct'] = (stats['ups'] / stats['total']) * 100

    conn.close()
    return hourly_stats


def print_hourly_report(crypto: str, days: int = 7):
    """Print formatted hourly analysis."""
    stats = analyze_hourly_patterns(crypto, days)

    print("="*100)
    print(f"TIME-OF-DAY ANALYSIS - {crypto.upper()} (Past {days} days)")
    print("="*100)
    print()

    print(f"{'Hour (UTC)':<12} {'Total':<8} {'Ups':<6} {'Downs':<6} {'Up %':<10} {'Bias':<10} {'Strength':<10}")
    print("-"*100)

    best_up_hours = []
    best_down_hours = []

    for hour in range(24):
        stats_h = stats[hour]
        total = stats_h['total']

        if total == 0:
            continue

        ups = stats_h['ups']
        downs = stats_h['downs']
        up_pct = stats_h['up_pct']

        # Determine bias
        if up_pct > 60:
            bias = "↗️  UP"
            strength = "STRONG" if up_pct > 70 else "MODERATE"
            indicator = "🔥"
            best_up_hours.append((hour, up_pct))
        elif up_pct < 40:
            bias = "↙️  DOWN"
            strength = "STRONG" if up_pct < 30 else "MODERATE"
            indicator = "❄️"
            best_down_hours.append((hour, up_pct))
        else:
            bias = "⚖️  NEUTRAL"
            strength = "WEAK"
            indicator = "⚖️"

        print(f"{indicator} {hour:02d}:00-{hour:02d}:59 {total:<8} {ups:<6} {downs:<6} {up_pct:<9.1f}% {bias:<10} {strength:<10}")

    print()
    print("="*100)
    print()

    # Summary insights
    print("⏰ BEST TRADING HOURS:")
    print("-"*100)

    if best_up_hours:
        best_up_hours.sort(key=lambda x: x[1], reverse=True)
        print("\n🔥 BEST HOURS TO BET UP:")
        for hour, pct in best_up_hours[:5]:
            print(f"   {hour:02d}:00-{hour:02d}:59 UTC → {pct:.1f}% up bias")

    if best_down_hours:
        best_down_hours.sort(key=lambda x: x[1])
        print("\n❄️  BEST HOURS TO BET DOWN:")
        for hour, pct in best_down_hours[:5]:
            print(f"   {hour:02d}:00-{hour:02d}:59 UTC → {100-pct:.1f}% down bias")

    if not best_up_hours and not best_down_hours:
        print("\n⚖️  No strong hourly biases detected (all hours near 50/50)")

    print()
    print("="*100)


def compare_cryptos_by_hour(cryptos: List[str] = ['btc', 'eth', 'sol', 'xrp'], days: int = 7):
    """Compare hourly patterns across multiple cryptos."""
    print("="*100)
    print(f"CROSS-CRYPTO HOURLY COMPARISON (Past {days} days)")
    print("="*100)
    print()

    all_stats = {}
    for crypto in cryptos:
        all_stats[crypto] = analyze_hourly_patterns(crypto, days)

    # Find best hours for each strategy
    print("🔥 BEST UP-BIAS HOURS (>60% up):")
    print("-"*100)

    for crypto in cryptos:
        stats = all_stats[crypto]
        up_hours = [(h, s['up_pct']) for h, s in stats.items()
                   if s['total'] > 0 and s['up_pct'] > 60]

        if up_hours:
            up_hours.sort(key=lambda x: x[1], reverse=True)
            hours_str = ", ".join([f"{h:02d}:00({pct:.0f}%)" for h, pct in up_hours[:5]])
            print(f"  {crypto.upper():<6} → {hours_str}")
        else:
            print(f"  {crypto.upper():<6} → No strong up-bias hours")

    print()
    print("❄️  BEST DOWN-BIAS HOURS (<40% up):")
    print("-"*100)

    for crypto in cryptos:
        stats = all_stats[crypto]
        down_hours = [(h, s['up_pct']) for h, s in stats.items()
                     if s['total'] > 0 and s['up_pct'] < 40]

        if down_hours:
            down_hours.sort(key=lambda x: x[1])
            hours_str = ", ".join([f"{h:02d}:00({100-pct:.0f}% dn)" for h, pct in down_hours[:5]])
            print(f"  {crypto.upper():<6} → {hours_str}")
        else:
            print(f"  {crypto.upper():<6} → No strong down-bias hours")

    print()
    print("="*100)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze time-of-day trading patterns')
    parser.add_argument('--crypto', type=str, help='Single crypto (btc, eth, sol, xrp)')
    parser.add_argument('--all', action='store_true', help='Compare all cryptos')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze')

    args = parser.parse_args()

    # Check if dataset exists
    db_path = Path('analysis/epoch_history.db')
    if not db_path.exists():
        print("⚠️  Historical dataset not found!")
        print()
        print("Please run first:")
        print("  python3 analysis/historical_dataset.py --backfill 7 --all")
        print()
        return

    if args.all:
        compare_cryptos_by_hour(days=args.days)
    elif args.crypto:
        print_hourly_report(args.crypto.lower(), args.days)
    else:
        print("Please specify --crypto <name> or --all")


if __name__ == '__main__':
    main()
