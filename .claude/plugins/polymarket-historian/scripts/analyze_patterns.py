#!/usr/bin/env python3
"""
Pattern Analyzer - Identifies winning strategies from historical data

Analyzes:
- Win rate by strategy (early/late/contrarian)
- Win rate by crypto (BTC/ETH/SOL/XRP)
- Win rate by time-of-day
- Win rate by market regime
- Agent performance and accuracy
- Entry price effectiveness
"""

import json
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# Plugin directories
PLUGIN_DIR = Path(__file__).parent.parent
DATA_DIR = PLUGIN_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
PATTERNS_DIR = DATA_DIR / "patterns"
INSIGHTS_DIR = DATA_DIR / "insights"

# Ensure directories exist
PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)


def load_all_snapshots() -> List[Dict]:
    """Load all snapshot files."""
    snapshots = []

    if not SNAPSHOTS_DIR.exists():
        return snapshots

    for file in sorted(SNAPSHOTS_DIR.glob("*.json")):
        try:
            with open(file, 'r') as f:
                snapshots.append(json.load(f))
        except Exception as e:
            print(f"Warning: Could not load {file}: {e}")

    return snapshots


def extract_completed_trades(snapshots: List[Dict]) -> List[Dict]:
    """
    Extract completed trades with outcomes from snapshots.

    Match ORDER PLACED with subsequent WIN/LOSS by tracking positions.
    """

    # For now, parse from logs within snapshots
    # In future: Match entry -> exit via position tracking

    trades = []

    for snapshot in snapshots:
        for trade in snapshot.get('recent_trades', []):
            if trade.get('type') == 'entry':
                # Add metadata from snapshot
                trade['snapshot_time'] = snapshot.get('timestamp')
                trade['bot_mode'] = snapshot.get('bot_state', {}).get('mode', 'unknown')

                trades.append(trade)

    return trades


def classify_strategy(trade: Dict) -> str:
    """Classify trade into strategy type based on entry price and timing."""

    entry_price = trade.get('entry_price', 0)

    if entry_price <= 0.20:
        return 'contrarian'
    elif entry_price <= 0.35:
        return 'early_momentum'
    elif entry_price >= 0.85:
        return 'late_confirmation'
    else:
        return 'mid_epoch'


def analyze_by_strategy(trades: List[Dict]) -> Dict:
    """Analyze win rates by strategy type."""

    strategy_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0, 'trades': []})

    for trade in trades:
        strategy = classify_strategy(trade)
        strategy_stats[strategy]['total'] += 1
        strategy_stats[strategy]['trades'].append(trade)

        # TODO: Determine win/loss from position tracking
        # For now, just count trades

    # Calculate win rates
    results = {}
    for strategy, stats in strategy_stats.items():
        total = stats['total']
        wins = stats['wins']
        win_rate = (wins / total * 100) if total > 0 else 0

        results[strategy] = {
            'total_trades': total,
            'wins': wins,
            'losses': stats['losses'],
            'win_rate': win_rate,
            'avg_entry': sum(t.get('entry_price', 0) for t in stats['trades']) / total if total > 0 else 0
        }

    return results


def analyze_by_crypto(trades: List[Dict]) -> Dict:
    """Analyze win rates by cryptocurrency."""

    crypto_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0, 'total_pnl': 0})

    for trade in trades:
        crypto = trade.get('crypto', 'unknown')
        crypto_stats[crypto]['total'] += 1

        # TODO: Track actual P&L

    # Calculate win rates
    results = {}
    for crypto, stats in crypto_stats.items():
        total = stats['total']
        wins = stats['wins']
        win_rate = (wins / total * 100) if total > 0 else 0

        results[crypto] = {
            'total_trades': total,
            'wins': wins,
            'losses': stats['losses'],
            'win_rate': win_rate,
            'total_pnl': stats['total_pnl']
        }

    return results


def analyze_by_time_of_day(trades: List[Dict]) -> Dict:
    """Analyze win rates by hour of day."""

    hourly_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0})

    for trade in trades:
        timestamp = trade.get('timestamp')
        if not timestamp:
            continue

        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour

            hourly_stats[hour]['total'] += 1
            # TODO: Track wins/losses
        except:
            pass

    # Calculate win rates
    results = {}
    for hour, stats in hourly_stats.items():
        total = stats['total']
        wins = stats['wins']
        win_rate = (wins / total * 100) if total > 0 else 0

        results[hour] = {
            'total_trades': total,
            'wins': wins,
            'losses': stats['losses'],
            'win_rate': win_rate
        }

    return results


def generate_recommendations(patterns: Dict) -> List[str]:
    """Generate actionable recommendations from patterns."""

    recommendations = []

    # Analyze strategy performance
    strategy_patterns = patterns.get('by_strategy', {})

    for strategy, stats in strategy_patterns.items():
        total = stats.get('total_trades', 0)
        win_rate = stats.get('win_rate', 0)

        if total < 10:
            continue  # Not enough data

        if win_rate >= 70:
            recommendations.append({
                'priority': 'high',
                'type': 'boost_strategy',
                'strategy': strategy,
                'reason': f"{strategy} has {win_rate:.1f}% win rate ({stats['wins']}/{total} wins)",
                'action': f"Increase position size for {strategy} by 20%"
            })
        elif win_rate <= 50:
            recommendations.append({
                'priority': 'high',
                'type': 'disable_strategy',
                'strategy': strategy,
                'reason': f"{strategy} has only {win_rate:.1f}% win rate ({stats['wins']}/{total} wins)",
                'action': f"Disable or significantly reduce {strategy} until further analysis"
            })

    # Analyze crypto performance
    crypto_patterns = patterns.get('by_crypto', {})

    for crypto, stats in crypto_patterns.items():
        total = stats.get('total_trades', 0)
        win_rate = stats.get('win_rate', 0)

        if total < 5:
            continue

        if win_rate >= 75:
            recommendations.append({
                'priority': 'medium',
                'type': 'boost_crypto',
                'crypto': crypto,
                'reason': f"{crypto} performing excellently ({win_rate:.1f}% WR)",
                'action': f"Increase {crypto} exposure by 15%"
            })
        elif win_rate <= 45:
            recommendations.append({
                'priority': 'medium',
                'type': 'reduce_crypto',
                'crypto': crypto,
                'reason': f"{crypto} underperforming ({win_rate:.1f}% WR)",
                'action': f"Reduce {crypto} position sizes by 30% or disable temporarily"
            })

    return recommendations


def generate_insights_report(patterns: Dict, recommendations: List[str]) -> str:
    """Generate markdown report with insights and recommendations."""

    report = f"""# Polymarket Trading Insights Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

---

## Executive Summary

Total trades analyzed: {sum(p.get('total_trades', 0) for p in patterns.get('by_strategy', {}).values())}

### Top Performing Strategies

"""

    # Sort strategies by win rate
    strategies = patterns.get('by_strategy', {})
    sorted_strategies = sorted(strategies.items(), key=lambda x: x[1].get('win_rate', 0), reverse=True)

    for strategy, stats in sorted_strategies[:3]:
        if stats.get('total_trades', 0) >= 5:
            report += f"""
**{strategy.replace('_', ' ').title()}**
- Win Rate: {stats.get('win_rate', 0):.1f}%
- Trades: {stats.get('wins', 0)}/{stats.get('total_trades', 0)} wins
- Avg Entry: ${stats.get('avg_entry', 0):.3f}
"""

    report += "\n### Cryptocurrency Performance\n\n"

    cryptos = patterns.get('by_crypto', {})
    sorted_cryptos = sorted(cryptos.items(), key=lambda x: x[1].get('total_trades', 0), reverse=True)

    report += "| Crypto | Trades | Win Rate | P&L |\n"
    report += "|--------|--------|----------|-----|\n"

    for crypto, stats in sorted_cryptos:
        total = stats.get('total_trades', 0)
        wr = stats.get('win_rate', 0)
        pnl = stats.get('total_pnl', 0)
        report += f"| {crypto} | {total} | {wr:.1f}% | ${pnl:.2f} |\n"

    report += "\n---\n\n## Recommendations\n\n"

    if not recommendations:
        report += "*Not enough data yet to generate recommendations. Keep trading!*\n"
    else:
        # Sort by priority
        high_pri = [r for r in recommendations if r.get('priority') == 'high']
        med_pri = [r for r in recommendations if r.get('priority') == 'medium']

        if high_pri:
            report += "### 🔴 High Priority\n\n"
            for rec in high_pri:
                report += f"""
**{rec.get('type', 'Action').replace('_', ' ').title()}**
- Reason: {rec.get('reason', 'N/A')}
- Action: {rec.get('action', 'N/A')}
"""

        if med_pri:
            report += "\n### 🟡 Medium Priority\n\n"
            for rec in med_pri:
                report += f"""
**{rec.get('type', 'Action').replace('_', ' ').title()}**
- Reason: {rec.get('reason', 'N/A')}
- Action: {rec.get('action', 'N/A')}
"""

    report += "\n---\n\n## Next Steps\n\n"
    report += """
1. Review high-priority recommendations
2. Test changes on small position sizes first
3. Monitor for 24-48 hours before full deployment
4. Re-run analysis after implementing changes
5. Continue collecting data for better insights

**Data improves with more trades - keep the bot running!**
"""

    return report


def main():
    """Main analysis routine."""

    print("=" * 70)
    print("POLYMARKET HISTORIAN - PATTERN ANALYSIS")
    print("=" * 70)
    print()

    # Load data
    print("Loading snapshots...")
    snapshots = load_all_snapshots()
    print(f"  Loaded {len(snapshots)} snapshots")

    if len(snapshots) == 0:
        print("\n❌ No snapshots found. Run /historian-collect first!")
        return

    # Extract trades
    print("\nExtracting trades...")
    trades = extract_completed_trades(snapshots)
    print(f"  Found {len(trades)} trades")

    if len(trades) < 5:
        print("\n⚠️  Not enough trades for meaningful analysis. Keep collecting data!")
        return

    # Analyze patterns
    print("\nAnalyzing patterns...")

    patterns = {
        'by_strategy': analyze_by_strategy(trades),
        'by_crypto': analyze_by_crypto(trades),
        'by_time_of_day': analyze_by_time_of_day(trades),
        'metadata': {
            'total_trades': len(trades),
            'analyzed_at': datetime.now().isoformat(),
            'snapshot_count': len(snapshots)
        }
    }

    # Save patterns
    patterns_file = PATTERNS_DIR / "latest_analysis.json"
    with open(patterns_file, 'w') as f:
        json.dump(patterns, f, indent=2)

    print(f"  ✅ Patterns saved: {patterns_file}")

    # Generate recommendations
    print("\nGenerating recommendations...")
    recommendations = generate_recommendations(patterns)

    recommendations_file = PATTERNS_DIR / "recommendations.json"
    with open(recommendations_file, 'w') as f:
        json.dump(recommendations, f, indent=2)

    print(f"  ✅ Recommendations saved: {recommendations_file}")

    # Generate insights report
    print("\nGenerating insights report...")
    report = generate_insights_report(patterns, recommendations)

    report_file = INSIGHTS_DIR / "latest_report.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"  ✅ Report saved: {report_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print()
    print(f"Total Trades: {len(trades)}")
    print(f"Strategies Identified: {len(patterns['by_strategy'])}")
    print(f"Recommendations: {len(recommendations)}")
    print()
    print(f"📄 Full report: {report_file}")
    print()

    # Print quick summary
    if recommendations:
        print("TOP RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"  {i}. {rec.get('action', 'N/A')}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
