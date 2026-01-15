#!/usr/bin/env python3
"""
Daily Epoch Pattern Analysis

Analyzes 15-minute epoch outcomes over full days to identify:
1. Up/Down ratio for each crypto per day
2. Patterns or thresholds that emerge
3. Whether cryptos have directional biases

This helps answer: Do cryptos tend to stay within certain up/down ranges per day?
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import time

sys.path.append(str(Path(__file__).parent.parent))

from simulation.outcome_fetcher import OutcomeFetcher


def analyze_daily_patterns(crypto: str, num_days: int = 7):
    """
    Analyze up/down patterns for a crypto over multiple days.

    Args:
        crypto: Cryptocurrency (btc, eth, sol, xrp, link)
        num_days: Number of days to analyze

    Returns:
        Dict with daily stats and overall patterns
    """
    fetcher = OutcomeFetcher()

    # Calculate epoch range (96 epochs per day = 24 hours * 4 per hour)
    epochs_per_day = 96
    current_time = int(time.time())

    # Round to start of current epoch
    current_epoch = (current_time // 900) * 900

    # Go back num_days
    start_epoch = current_epoch - (epochs_per_day * 900 * num_days)

    daily_stats = defaultdict(lambda: {'ups': 0, 'downs': 0, 'total': 0, 'ratio': 0.0})

    print(f"Analyzing {crypto.upper()} over {num_days} days ({num_days * epochs_per_day} epochs)")
    print(f"From: {datetime.fromtimestamp(start_epoch).strftime('%Y-%m-%d %H:%M')}")
    print(f"To:   {datetime.fromtimestamp(current_epoch).strftime('%Y-%m-%d %H:%M')}")
    print()
    print("Fetching data (this may take a few minutes)...")
    print()

    # Fetch outcomes for each epoch
    epoch = start_epoch
    epoch_count = 0
    errors = 0

    while epoch <= current_epoch:
        # Get date key for grouping
        date_key = datetime.fromtimestamp(epoch).strftime('%Y-%m-%d')

        # Fetch outcome
        try:
            result = fetcher.get_epoch_outcome(crypto, epoch)

            if result:
                daily_stats[date_key]['total'] += 1

                if result.direction == 'Up':
                    daily_stats[date_key]['ups'] += 1
                else:
                    daily_stats[date_key]['downs'] += 1

                epoch_count += 1

                # Progress indicator
                if epoch_count % 20 == 0:
                    print(f"  Processed {epoch_count} epochs...", end='\r')
            else:
                errors += 1

        except Exception as e:
            errors += 1
            if errors > 20:
                print(f"\n⚠️  Too many errors ({errors}), stopping analysis")
                break

        # Next epoch (15 minutes = 900 seconds)
        epoch += 900

    print(f"\nCompleted: {epoch_count} epochs analyzed, {errors} errors")
    print()

    # Calculate ratios
    for date, stats in daily_stats.items():
        if stats['total'] > 0:
            stats['ratio'] = stats['ups'] / stats['total']

    return daily_stats


def print_daily_report(crypto: str, daily_stats: dict):
    """Print formatted daily report."""
    print("=" * 100)
    print(f"DAILY EPOCH PATTERN ANALYSIS - {crypto.upper()}")
    print("=" * 100)
    print()

    print(f"{'Date':<12} {'Total':<8} {'Ups':<8} {'Downs':<8} {'Up %':<10} {'Down %':<10} {'Ratio (U/D)':<12}")
    print("-" * 100)

    total_ups = 0
    total_downs = 0

    for date in sorted(daily_stats.keys()):
        stats = daily_stats[date]
        ups = stats['ups']
        downs = stats['downs']
        total = stats['total']

        if total > 0:
            up_pct = (ups / total) * 100
            down_pct = (downs / total) * 100
            ratio = ups / downs if downs > 0 else float('inf')

            # Color coding
            if up_pct > 60:
                indicator = "🔥"  # Strong upward bias
            elif down_pct > 60:
                indicator = "❄️"  # Strong downward bias
            else:
                indicator = "⚖️"  # Balanced

            print(f"{indicator} {date:<10} {total:<8} {ups:<8} {downs:<8} {up_pct:<9.1f}% {down_pct:<9.1f}% {ratio:<12.2f}")

            total_ups += ups
            total_downs += downs

    print("-" * 100)

    # Overall stats
    grand_total = total_ups + total_downs
    if grand_total > 0:
        overall_up_pct = (total_ups / grand_total) * 100
        overall_down_pct = (total_downs / grand_total) * 100
        overall_ratio = total_ups / total_downs if total_downs > 0 else float('inf')

        print(f"TOTAL     {grand_total:<8} {total_ups:<8} {total_downs:<8} {overall_up_pct:<9.1f}% {overall_down_pct:<9.1f}% {overall_ratio:<12.2f}")

    print()
    print("=" * 100)
    print()

    # Pattern analysis
    print("PATTERN INSIGHTS:")
    print("-" * 100)

    if grand_total > 0:
        # Check for bias
        if overall_up_pct > 55:
            print(f"✅ {crypto.upper()} shows UPWARD BIAS: {overall_up_pct:.1f}% of epochs go up")
        elif overall_down_pct > 55:
            print(f"✅ {crypto.upper()} shows DOWNWARD BIAS: {overall_down_pct:.1f}% of epochs go down")
        else:
            print(f"⚖️  {crypto.upper()} is BALANCED: ~50/50 up/down distribution")

        # Daily volatility (standard deviation of daily ratios)
        ratios = [stats['ratio'] for stats in daily_stats.values() if stats['total'] > 0]
        if len(ratios) > 1:
            import statistics
            avg_ratio = statistics.mean(ratios)
            std_ratio = statistics.stdev(ratios)

            print(f"\n📊 Daily Up/Down Ratio:")
            print(f"   Average: {avg_ratio:.2f} (typical day has {avg_ratio:.2f}x more ups than downs)")
            print(f"   Std Dev: {std_ratio:.2f} (consistency: {'HIGH' if std_ratio < 0.2 else 'MEDIUM' if std_ratio < 0.5 else 'LOW'})")

        # Check if any day exceeded 70% threshold
        extreme_days = [(date, stats['ratio']) for date, stats in daily_stats.items()
                       if stats['total'] > 0 and (stats['ratio'] > 0.7 or stats['ratio'] < 0.3)]

        if extreme_days:
            print(f"\n⚠️  Found {len(extreme_days)} EXTREME DAYS (>70% or <30% ups):")
            for date, ratio in sorted(extreme_days):
                print(f"   {date}: {ratio*100:.1f}% ups")
        else:
            print(f"\n✅ No extreme days found (all days stay within 30-70% range)")

    print()
    print("=" * 100)


def compare_cryptos(cryptos: list, num_days: int = 7):
    """Compare multiple cryptos side-by-side."""
    all_stats = {}

    for crypto in cryptos:
        print(f"\nAnalyzing {crypto.upper()}...")
        daily_stats = analyze_daily_patterns(crypto, num_days)
        all_stats[crypto] = daily_stats
        print_daily_report(crypto, daily_stats)

    # Cross-crypto comparison
    print("\n")
    print("=" * 100)
    print("CROSS-CRYPTO COMPARISON")
    print("=" * 100)
    print()

    print(f"{'Crypto':<10} {'Avg Up%':<12} {'Avg Down%':<12} {'Bias':<15} {'Consistency':<15}")
    print("-" * 100)

    for crypto in cryptos:
        daily_stats = all_stats[crypto]

        # Calculate overall
        total_ups = sum(s['ups'] for s in daily_stats.values())
        total_downs = sum(s['downs'] for s in daily_stats.values())
        grand_total = total_ups + total_downs

        if grand_total > 0:
            up_pct = (total_ups / grand_total) * 100
            down_pct = (total_downs / grand_total) * 100

            # Determine bias
            if up_pct > 55:
                bias = f"↗️  Upward ({up_pct:.1f}%)"
            elif down_pct > 55:
                bias = f"↙️  Downward ({down_pct:.1f}%)"
            else:
                bias = "⚖️  Balanced (50/50)"

            # Consistency (how similar days are to each other)
            ratios = [s['ratio'] for s in daily_stats.values() if s['total'] > 0]
            if len(ratios) > 1:
                import statistics
                std_ratio = statistics.stdev(ratios)
                consistency = "HIGH" if std_ratio < 0.2 else "MEDIUM" if std_ratio < 0.5 else "LOW"
            else:
                consistency = "N/A"

            print(f"{crypto.upper():<10} {up_pct:<11.1f}% {down_pct:<11.1f}% {bias:<15} {consistency:<15}")

    print()
    print("=" * 100)
    print()
    print("💡 BETTING INSIGHTS:")
    print("-" * 100)
    print("1. Look for cryptos with strong bias (>55% in one direction)")
    print("2. High consistency = predictable daily patterns = safer bets")
    print("3. Extreme days (>70%) may revert to mean next day")
    print("4. Balanced cryptos (50/50) = use technical analysis, not directional bias")
    print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze daily 15-min epoch patterns')
    parser.add_argument('--crypto', type=str, help='Single crypto to analyze (btc, eth, sol, xrp, link)')
    parser.add_argument('--all', action='store_true', help='Compare all cryptos')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')

    args = parser.parse_args()

    if args.all:
        # Analyze all major cryptos
        cryptos = ['btc', 'eth', 'sol', 'xrp', 'link']
        compare_cryptos(cryptos, args.days)
    elif args.crypto:
        # Single crypto analysis
        daily_stats = analyze_daily_patterns(args.crypto.lower(), args.days)
        print_daily_report(args.crypto.lower(), daily_stats)
    else:
        print("Please specify --crypto <name> or --all")
        print("Examples:")
        print("  python3 analysis/daily_epoch_patterns.py --crypto link --days 7")
        print("  python3 analysis/daily_epoch_patterns.py --all --days 14")


if __name__ == '__main__':
    main()
