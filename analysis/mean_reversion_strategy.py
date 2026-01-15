#!/usr/bin/env python3
"""
Mean Reversion Strategy Analyzer

Tests the hypothesis: "After an extreme day (>70% one direction),
the next day tends to revert toward the mean (50/50)."

Backtests this strategy against historical data.
"""

import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent))


def get_daily_patterns(crypto: str, db_path: str = 'analysis/epoch_history.db') -> Dict[str, Dict]:
    """Get up/down stats for each day."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute('''
        SELECT
            date,
            direction,
            COUNT(*) as count
        FROM epoch_outcomes
        WHERE crypto = ?
        GROUP BY date, direction
        ORDER BY date
    ''', (crypto,)).fetchall()

    daily_stats = defaultdict(lambda: {'ups': 0, 'downs': 0, 'total': 0})

    for row in rows:
        date = row['date']
        if row['direction'] == 'Up':
            daily_stats[date]['ups'] = row['count']
        else:
            daily_stats[date]['downs'] = row['count']

    # Calculate ratios
    for date, stats in daily_stats.items():
        stats['total'] = stats['ups'] + stats['downs']
        if stats['total'] > 0:
            stats['up_pct'] = (stats['ups'] / stats['total']) * 100

    conn.close()
    return dict(daily_stats)


def test_mean_reversion(crypto: str, extreme_threshold: float = 70.0) -> Dict:
    """
    Test mean reversion hypothesis.

    Strategy:
    - After day with >extreme_threshold% ups → bet DOWN next day
    - After day with <(100-extreme_threshold)% ups → bet UP next day

    Returns results dict with win rate and profitability.
    """
    daily_stats = get_daily_patterns(crypto)

    if not daily_stats:
        return {'error': 'No historical data'}

    # Sort dates
    sorted_dates = sorted(daily_stats.keys())

    extreme_days = []
    signals = []

    for i, date in enumerate(sorted_dates[:-1]):  # Exclude last day (no "next day")
        stats = daily_stats[date]
        up_pct = stats['up_pct']

        next_date = sorted_dates[i + 1]
        next_stats = daily_stats[next_date]
        next_up_pct = next_stats['up_pct']

        # Check if extreme day
        if up_pct > extreme_threshold:
            # Extreme UP day → bet DOWN next day
            signal = 'DOWN'
            extreme_type = 'EXTREME_UP'
            extreme_days.append((date, up_pct, signal))

            # Did it work?
            actual_direction = 'DOWN' if next_up_pct < 50 else 'UP'
            win = (signal == actual_direction)

            signals.append({
                'date': date,
                'type': extreme_type,
                'up_pct': up_pct,
                'signal': signal,
                'next_date': next_date,
                'next_up_pct': next_up_pct,
                'actual': actual_direction,
                'win': win
            })

        elif up_pct < (100 - extreme_threshold):
            # Extreme DOWN day → bet UP next day
            signal = 'UP'
            extreme_type = 'EXTREME_DOWN'
            extreme_days.append((date, up_pct, signal))

            # Did it work?
            actual_direction = 'UP' if next_up_pct > 50 else 'DOWN'
            win = (signal == actual_direction)

            signals.append({
                'date': date,
                'type': extreme_type,
                'up_pct': up_pct,
                'signal': signal,
                'next_date': next_date,
                'next_up_pct': next_up_pct,
                'actual': actual_direction,
                'win': win
            })

    # Calculate win rate
    if not signals:
        return {
            'total_days': len(sorted_dates),
            'extreme_days': 0,
            'signals': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'message': f'No extreme days found (threshold: {extreme_threshold}%)'
        }

    wins = sum(1 for s in signals if s['win'])
    losses = len(signals) - wins
    win_rate = (wins / len(signals)) * 100

    return {
        'crypto': crypto,
        'total_days': len(sorted_dates),
        'extreme_days': len(extreme_days),
        'signals': len(signals),
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'threshold': extreme_threshold,
        'signals_detail': signals
    }


def print_mean_reversion_report(crypto: str, threshold: float = 70.0):
    """Print formatted mean reversion analysis."""
    results = test_mean_reversion(crypto, threshold)

    if 'error' in results:
        print(f"⚠️  {results['error']}")
        return

    print("="*100)
    print(f"MEAN REVERSION STRATEGY BACKTEST - {crypto.upper()}")
    print("="*100)
    print()

    print(f"Strategy: After extreme day (>{threshold}% or <{100-threshold}% up), bet opposite direction next day")
    print()

    print("RESULTS:")
    print("-"*100)
    print(f"  Total days analyzed: {results['total_days']}")
    print(f"  Extreme days found: {results['extreme_days']}")
    print(f"  Trading signals: {results['signals']}")
    print(f"  Wins: {results['wins']}")
    print(f"  Losses: {results['losses']}")
    print(f"  Win Rate: {results['win_rate']:.1f}%")
    print()

    # Profitability assessment
    if results['win_rate'] > 55:
        verdict = "✅ PROFITABLE - Strategy shows edge over random (>55%)"
    elif results['win_rate'] > 50:
        verdict = "⚖️  MARGINAL - Slightly better than coin flip"
    else:
        verdict = "❌ UNPROFITABLE - Strategy underperforms random"

    print(f"VERDICT: {verdict}")
    print()

    # Show individual signals
    if results['signals'] > 0:
        print("SIGNAL HISTORY:")
        print("-"*100)
        print(f"{'Date':<12} {'Type':<15} {'Up%':<8} {'Signal':<8} {'Next Day':<12} {'Next Up%':<10} {'Result':<10}")
        print("-"*100)

        for sig in results['signals_detail']:
            result_emoji = "✅" if sig['win'] else "❌"
            print(f"{result_emoji} {sig['date']:<10} {sig['type']:<15} {sig['up_pct']:<7.1f}% "
                  f"{sig['signal']:<8} {sig['next_date']:<12} {sig['next_up_pct']:<9.1f}% "
                  f"{'WIN' if sig['win'] else 'LOSS':<10}")

    print()
    print("="*100)


def compare_thresholds(crypto: str, thresholds: List[float] = [60, 65, 70, 75, 80]):
    """Compare strategy performance at different extreme thresholds."""
    print("="*100)
    print(f"THRESHOLD OPTIMIZATION - {crypto.upper()}")
    print("="*100)
    print()

    print(f"{'Threshold':<12} {'Signals':<10} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Assessment':<20}")
    print("-"*100)

    best_threshold = None
    best_win_rate = 0

    for threshold in thresholds:
        results = test_mean_reversion(crypto, threshold)

        if 'error' in results or results['signals'] == 0:
            print(f"  {threshold}%       -         -       -       -              No extreme days")
            continue

        win_rate = results['win_rate']
        signals = results['signals']
        wins = results['wins']
        losses = results['losses']

        # Assessment
        if win_rate > 55 and signals >= 3:
            assessment = "✅ Profitable"
            indicator = "🔥"
        elif win_rate > 50:
            assessment = "⚖️  Marginal"
            indicator = "⚖️"
        else:
            assessment = "❌ Unprofitable"
            indicator = "❄️"

        print(f"{indicator} {threshold}%       {signals:<10} {wins:<8} {losses:<8} "
              f"{win_rate:<11.1f}% {assessment:<20}")

        if win_rate > best_win_rate and signals >= 3:
            best_win_rate = win_rate
            best_threshold = threshold

    print()
    print("="*100)
    print()

    if best_threshold:
        print(f"🏆 OPTIMAL THRESHOLD: {best_threshold}% ({best_win_rate:.1f}% win rate)")
    else:
        print("⚠️  No profitable threshold found")

    print()


def compare_cryptos():
    """Compare mean reversion strategy across all cryptos."""
    cryptos = ['btc', 'eth', 'sol', 'xrp']

    print("="*100)
    print("MEAN REVERSION STRATEGY - CROSS-CRYPTO COMPARISON")
    print("="*100)
    print()

    print(f"{'Crypto':<10} {'Total Days':<12} {'Extreme Days':<15} {'Win Rate':<12} {'Verdict':<20}")
    print("-"*100)

    for crypto in cryptos:
        results = test_mean_reversion(crypto, extreme_threshold=70)

        if 'error' in results:
            print(f"  {crypto.upper():<8} - No data")
            continue

        win_rate = results['win_rate']
        total_days = results['total_days']
        extreme_days = results['extreme_days']

        # Verdict
        if results['signals'] == 0:
            verdict = "No extreme days"
            indicator = "⚪"
        elif win_rate > 55:
            verdict = "✅ Profitable"
            indicator = "🔥"
        elif win_rate > 50:
            verdict = "⚖️  Marginal"
            indicator = "⚖️"
        else:
            verdict = "❌ Unprofitable"
            indicator = "❄️"

        print(f"{indicator} {crypto.upper():<8} {total_days:<12} {extreme_days:<15} "
              f"{win_rate:<11.1f}% {verdict:<20}")

    print()
    print("="*100)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Test mean reversion trading strategy')
    parser.add_argument('--crypto', type=str, help='Single crypto (btc, eth, sol, xrp)')
    parser.add_argument('--all', action='store_true', help='Compare all cryptos')
    parser.add_argument('--threshold', type=float, default=70.0, help='Extreme day threshold (default: 70 percent)')
    parser.add_argument('--optimize', action='store_true', help='Find optimal threshold')

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
        compare_cryptos()
    elif args.optimize and args.crypto:
        compare_thresholds(args.crypto.lower())
    elif args.crypto:
        print_mean_reversion_report(args.crypto.lower(), args.threshold)
    else:
        print("Please specify --crypto <name> or --all")
        print()
        print("Examples:")
        print("  python3 analysis/mean_reversion_strategy.py --crypto btc")
        print("  python3 analysis/mean_reversion_strategy.py --crypto btc --optimize")
        print("  python3 analysis/mean_reversion_strategy.py --all")


if __name__ == '__main__':
    main()
