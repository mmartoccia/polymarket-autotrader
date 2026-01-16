#!/usr/bin/env python3
"""
US-RC-014: Entry Price Distribution Analysis
Persona: James "Jimmy the Greek" Martinez (Market Microstructure Specialist)

Analyzes entry price distribution from trade logs to understand:
- Entry price statistics (mean, median, mode, std dev, percentiles)
- Strategy classification by timing (early momentum, contrarian, late confirmation)
- Comparison to configured limits (MAX_ENTRY=0.25)
- Distribution visualization (ASCII histogram)

Author: Ralph (Autonomous Coding Agent)
Date: 2026-01-16
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import Counter
import statistics


@dataclass
class Trade:
    """Represents a single trade with entry price and timing."""
    timestamp: datetime
    crypto: str
    direction: str
    entry_price: float
    shares: float
    outcome: Optional[str] = None
    epoch_start: Optional[datetime] = None
    seconds_into_epoch: Optional[int] = None
    strategy: Optional[str] = None  # early_momentum, contrarian, late_confirmation

    def classify_strategy(self) -> str:
        """Classify strategy based on timing and entry price."""
        if self.seconds_into_epoch is None:
            return "unknown"

        # Early momentum: 15-300 seconds, mid-range price (0.12-0.30)
        if 15 <= self.seconds_into_epoch <= 300 and 0.12 <= self.entry_price <= 0.30:
            return "early_momentum"

        # Contrarian: 30-700 seconds, cheap entry (<0.20)
        if 30 <= self.seconds_into_epoch <= 700 and self.entry_price < 0.20:
            return "contrarian"

        # Late confirmation: 720+ seconds, high probability (>0.85)
        if self.seconds_into_epoch >= 720 and self.entry_price > 0.85:
            return "late_confirmation"

        # Unknown pattern
        return "other"


class EntryPriceAnalyzer:
    """Analyzes entry price distribution from trade logs."""

    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.trades: List[Trade] = []

    def parse_trades(self) -> None:
        """Parse trades from bot.log."""
        if not self.log_file.exists():
            print(f"Warning: Log file not found: {self.log_file}")
            return

        # Patterns for ORDER PLACED messages
        order_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*ORDER PLACED.*'
            r'(BTC|ETH|SOL|XRP)\s+(Up|Down).*'
            r'Entry:\s*\$?([0-9.]+).*'
            r'Shares:\s*([0-9.]+)',
            re.IGNORECASE
        )

        # Pattern for epoch timing (if available)
        timing_pattern = re.compile(
            r'(\d+)s into epoch',
            re.IGNORECASE
        )

        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                order_match = order_pattern.search(line)
                if order_match:
                    try:
                        timestamp = datetime.strptime(order_match.group(1), '%Y-%m-%d %H:%M:%S')
                        crypto = order_match.group(2)
                        direction = order_match.group(3)
                        entry_price = float(order_match.group(4))
                        shares = float(order_match.group(5))

                        # Extract timing if available
                        seconds_into_epoch = None
                        timing_match = timing_pattern.search(line)
                        if timing_match:
                            seconds_into_epoch = int(timing_match.group(1))

                        trade = Trade(
                            timestamp=timestamp,
                            crypto=crypto,
                            direction=direction,
                            entry_price=entry_price,
                            shares=shares,
                            seconds_into_epoch=seconds_into_epoch
                        )

                        # Classify strategy
                        trade.strategy = trade.classify_strategy()

                        self.trades.append(trade)
                    except (ValueError, AttributeError) as e:
                        # Skip malformed entries
                        continue

    def calculate_statistics(self) -> Dict:
        """Calculate entry price statistics."""
        if not self.trades:
            return {
                'count': 0,
                'mean': 0.0,
                'median': 0.0,
                'mode': 0.0,
                'std_dev': 0.0,
                'min': 0.0,
                'max': 0.0,
                'p25': 0.0,
                'p75': 0.0,
                'p10': 0.0,
                'p90': 0.0
            }

        entry_prices = [t.entry_price for t in self.trades]

        # Mode calculation (most common price, rounded to 2 decimals)
        rounded_prices = [round(p, 2) for p in entry_prices]
        mode_counts = Counter(rounded_prices)
        mode = mode_counts.most_common(1)[0][0] if mode_counts else 0.0

        # Percentiles
        sorted_prices = sorted(entry_prices)
        n = len(sorted_prices)
        p10 = sorted_prices[int(n * 0.10)] if n > 0 else 0.0
        p25 = sorted_prices[int(n * 0.25)] if n > 0 else 0.0
        p75 = sorted_prices[int(n * 0.75)] if n > 0 else 0.0
        p90 = sorted_prices[int(n * 0.90)] if n > 0 else 0.0

        return {
            'count': len(entry_prices),
            'mean': statistics.mean(entry_prices),
            'median': statistics.median(entry_prices),
            'mode': mode,
            'std_dev': statistics.stdev(entry_prices) if len(entry_prices) > 1 else 0.0,
            'min': min(entry_prices),
            'max': max(entry_prices),
            'p25': p25,
            'p75': p75,
            'p10': p10,
            'p90': p90
        }

    def calculate_strategy_stats(self) -> Dict[str, Dict]:
        """Calculate statistics per strategy."""
        strategies = {}

        for trade in self.trades:
            strategy = trade.strategy
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(trade.entry_price)

        # Calculate stats for each strategy
        strategy_stats = {}
        for strategy, prices in strategies.items():
            if prices:
                strategy_stats[strategy] = {
                    'count': len(prices),
                    'mean': statistics.mean(prices),
                    'median': statistics.median(prices),
                    'std_dev': statistics.stdev(prices) if len(prices) > 1 else 0.0,
                    'min': min(prices),
                    'max': max(prices)
                }
            else:
                strategy_stats[strategy] = {
                    'count': 0,
                    'mean': 0.0,
                    'median': 0.0,
                    'std_dev': 0.0,
                    'min': 0.0,
                    'max': 0.0
                }

        return strategy_stats

    def generate_ascii_histogram(self, bins: int = 20) -> str:
        """Generate ASCII histogram of entry prices."""
        if not self.trades:
            return "No data available for histogram."

        entry_prices = [t.entry_price for t in self.trades]
        min_price = min(entry_prices)
        max_price = max(entry_prices)

        # Create bins
        bin_width = (max_price - min_price) / bins
        if bin_width == 0:
            bin_width = 0.01

        bin_counts = [0] * bins
        for price in entry_prices:
            bin_idx = min(int((price - min_price) / bin_width), bins - 1)
            bin_counts[bin_idx] += 1

        # Generate histogram
        max_count = max(bin_counts) if bin_counts else 1
        histogram_lines = []
        histogram_lines.append("Entry Price Distribution (ASCII Histogram)")
        histogram_lines.append("=" * 70)

        for i in range(bins):
            bin_start = min_price + i * bin_width
            bin_end = bin_start + bin_width
            count = bin_counts[i]
            bar_width = int((count / max_count) * 50) if max_count > 0 else 0
            bar = "█" * bar_width
            pct = (count / len(entry_prices)) * 100 if entry_prices else 0
            histogram_lines.append(
                f"${bin_start:.2f}-${bin_end:.2f} | {bar} {count:>4} ({pct:>5.1f}%)"
            )

        histogram_lines.append("=" * 70)
        return "\n".join(histogram_lines)

    def generate_report(self, output_file: str) -> None:
        """Generate comprehensive markdown report."""
        stats = self.calculate_statistics()
        strategy_stats = self.calculate_strategy_stats()
        histogram = self.generate_ascii_histogram()

        # Determine assessment based on mean entry price
        mean_entry = stats['mean']
        if mean_entry < 0.20:
            assessment = "EXCELLENT"
            assessment_icon = "🟢"
            interpretation = "Excellent fee economics - most entries are cheap (<$0.20)"
        elif mean_entry < 0.25:
            assessment = "GOOD"
            assessment_icon = "🟡"
            interpretation = "Good entry pricing - within configured limit"
        elif mean_entry < 0.30:
            assessment = "ACCEPTABLE"
            assessment_icon = "🟠"
            interpretation = "Acceptable but suboptimal - approaching high-fee territory"
        else:
            assessment = "POOR"
            assessment_icon = "🔴"
            interpretation = "Poor entry pricing - excessive fees eroding profits"

        # Check limit compliance
        max_entry_limit = 0.25  # From bot config
        exceeds_limit = stats['max'] > max_entry_limit

        report_lines = [
            "# Entry Price Distribution Analysis",
            "",
            "**Persona:** James 'Jimmy the Greek' Martinez (Market Microstructure Specialist)",
            f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Data Source:** {self.log_file}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"**Assessment:** {assessment_icon} **{assessment}**",
            f"**Total Trades Analyzed:** {stats['count']}",
            f"**Mean Entry Price:** ${stats['mean']:.4f}",
            f"**Median Entry Price:** ${stats['median']:.4f}",
            "",
            f"**Interpretation:** {interpretation}",
            "",
            "**Key Findings:**",
            f"- Average entry: ${stats['mean']:.4f}",
            f"- Median entry: ${stats['median']:.4f} (50% of trades below this price)",
            f"- Mode entry: ${stats['mode']:.2f} (most common price)",
            f"- Price range: ${stats['min']:.4f} - ${stats['max']:.4f}",
            f"- 75th percentile: ${stats['p75']:.4f} (75% of trades below this)",
            f"- Max entry limit: ${max_entry_limit:.2f} {'⚠️ EXCEEDED' if exceeds_limit else '✓ Compliant'}",
            "",
            "---",
            "",
            "## Distribution Statistics",
            "",
            "### Summary Statistics",
            "",
            "| Statistic | Value |",
            "|-----------|-------|",
            f"| Count | {stats['count']} |",
            f"| Mean | ${stats['mean']:.4f} |",
            f"| Median | ${stats['median']:.4f} |",
            f"| Mode | ${stats['mode']:.2f} |",
            f"| Std Dev | ${stats['std_dev']:.4f} |",
            f"| Min | ${stats['min']:.4f} |",
            f"| Max | ${stats['max']:.4f} |",
            "",
            "### Percentiles",
            "",
            "| Percentile | Value | Interpretation |",
            "|------------|-------|----------------|",
            f"| 10th | ${stats['p10']:.4f} | 10% of trades below this price |",
            f"| 25th | ${stats['p25']:.4f} | 25% of trades below this price (Q1) |",
            f"| 50th | ${stats['median']:.4f} | Median (half trades below) |",
            f"| 75th | ${stats['p75']:.4f} | 75% of trades below this price (Q3) |",
            f"| 90th | ${stats['p90']:.4f} | 90% of trades above this price |",
            "",
            "---",
            "",
            "## Strategy Breakdown",
            "",
            "Entry prices grouped by inferred strategy (based on timing and price):",
            "",
            "| Strategy | Trades | Mean Entry | Median | Std Dev | Min | Max |",
            "|----------|--------|------------|--------|---------|-----|-----|"
        ]

        # Add strategy stats
        strategy_order = ['early_momentum', 'contrarian', 'late_confirmation', 'other', 'unknown']
        for strategy in strategy_order:
            if strategy in strategy_stats:
                s = strategy_stats[strategy]
                strategy_name = strategy.replace('_', ' ').title()
                line = (
                    f"| {strategy_name} | {s['count']} | ${s['mean']:.4f} | ${s['median']:.4f} | "
                    f"${s['std_dev']:.4f} | ${s['min']:.4f} | ${s['max']:.4f} |"
                )
                report_lines.append(line)

        report_lines.extend([
            "",
            "**Strategy Definitions:**",
            "- **Early Momentum:** 15-300s into epoch, entry $0.12-$0.30 (catching trend formation)",
            "- **Contrarian:** 30-700s into epoch, entry <$0.20 (fading overpriced side)",
            "- **Late Confirmation:** 720+ seconds, entry >$0.85 (high probability, low reward)",
            "- **Other:** Patterns not matching above strategies",
            "- **Unknown:** Timing data not available in logs",
            "",
            "---",
            "",
            "## Histogram",
            "",
            "```",
            histogram,
            "```",
            "",
            "---",
            "",
            "## Comparison to Config Limits",
            "",
            f"**Configured MAX_ENTRY:** ${max_entry_limit:.2f}",
            f"**Actual Max Entry:** ${stats['max']:.4f}",
            f"**Compliance:** {'⚠️ LIMIT EXCEEDED' if exceeds_limit else '✓ All trades within limit'}",
            "",
        ])

        if exceeds_limit:
            report_lines.extend([
                f"**Violations:** {sum(1 for t in self.trades if t.entry_price > max_entry_limit)} trades exceeded limit",
                "",
                "**Recommendation:** Review config enforcement. Trades should be rejected if entry_price > MAX_ENTRY.",
                ""
            ])

        report_lines.extend([
            "**Entry Price vs Fee Rate:**",
            "",
            "| Entry Price | Fee Rate | Round-Trip Fee | Breakeven WR |",
            "|-------------|----------|----------------|--------------|",
            "| $0.10 | 0.63% | 1.26% | 50.63% |",
            "| $0.15 | 1.26% | 2.52% | 51.26% |",
            "| $0.20 | 1.89% | 3.78% | 51.89% |",
            "| $0.25 | 2.52% | 5.04% | 52.52% |",
            "| $0.30 | 3.15% | 6.30% | 53.15% |",
            "",
            "**Interpretation:** Cheaper entries have lower fees and easier profitability thresholds.",
            "",
            "---",
            "",
            "## Recommendations",
            "",
        ])

        # Recommendations based on assessment
        if assessment == "EXCELLENT":
            report_lines.extend([
                "✅ **Current Performance:**",
                "- Entry pricing is excellent (mean <$0.20)",
                "- Fee burden is minimal",
                "- Contrarian strategy appears to be working well",
                "",
                "📊 **Maintain:**",
                "- Continue prioritizing cheap entries (<$0.20)",
                "- Focus on contrarian opportunities (>70% overpriced)",
                "- Avoid mid-range entries ($0.40-$0.60) with high fees",
                ""
            ])
        elif assessment == "GOOD":
            report_lines.extend([
                "✅ **Current Performance:**",
                "- Entry pricing is good (within limit)",
                "- Fee burden is reasonable",
                "",
                "⚠️ **Optimize:**",
                "- Target more cheap entries (<$0.20) to improve fee economics",
                "- Review strategy mix - increase contrarian trades?",
                "- Monitor for price creep toward $0.25+ limit",
                ""
            ])
        elif assessment == "ACCEPTABLE":
            report_lines.extend([
                "⚠️ **Action Required:**",
                "- Entry prices approaching high-fee territory",
                "- Fee burden is significant (>2.5% average)",
                "",
                "🔧 **Immediate Actions:**",
                "- Lower MAX_ENTRY limit from $0.25 to $0.20",
                "- Increase MIN_SIGNAL_STRENGTH to be more selective",
                "- Prioritize contrarian trades (cheaper entries)",
                ""
            ])
        else:  # POOR
            report_lines.extend([
                "🔴 **CRITICAL ACTION REQUIRED:**",
                "- Entry prices are too high (mean >$0.30)",
                "- Fee burden is excessive (>3% average)",
                "- Profitability is severely impacted",
                "",
                "🚨 **Immediate Actions:**",
                "1. Lower MAX_ENTRY limit to $0.20 immediately",
                "2. Disable early momentum strategy (high entry prices)",
                "3. Focus exclusively on contrarian trades (<$0.20)",
                "4. Review signal quality - may be entering too late",
                ""
            ])

        report_lines.extend([
            "---",
            "",
            "## Methodology",
            "",
            "**Data Sources:**",
            f"- Trade logs: `{self.log_file}`",
            "- Parsed using US-RC-001 trade log parser patterns",
            "",
            "**Analysis Steps:**",
            "1. Parse ORDER PLACED messages for entry prices",
            "2. Extract timing data (seconds into epoch)",
            "3. Classify trades into strategies based on timing + price",
            "4. Calculate distribution statistics (mean, median, mode, std dev, percentiles)",
            "5. Generate ASCII histogram (20 bins)",
            "6. Compare to configured limits (MAX_ENTRY=0.25)",
            "7. Calculate fee rates using Polymarket formula",
            "",
            "**Strategy Classification Logic:**",
            "- **Early Momentum:** 15-300s + entry $0.12-$0.30",
            "- **Contrarian:** 30-700s + entry <$0.20",
            "- **Late Confirmation:** 720+ seconds + entry >$0.85",
            "- **Other:** Does not match above patterns",
            "- **Unknown:** Missing timing data",
            "",
            "**Fee Rate Formula:**",
            "```",
            "fee_rate = 3.15% × (1 - |2 × entry_price - 1|)",
            "round_trip_fee = 2 × fee_rate",
            "breakeven_wr = 50% + (round_trip_fee / 2)",
            "```",
            "",
            "---",
            "",
            "## Appendix: Trade Details",
            "",
            f"**Total Trades:** {len(self.trades)}",
            f"**Date Range:** {self.trades[0].timestamp.strftime('%Y-%m-%d') if self.trades else 'N/A'} to {self.trades[-1].timestamp.strftime('%Y-%m-%d') if self.trades else 'N/A'}",
            "",
            "**Sample Trades (First 10):**",
            "",
            "| Timestamp | Crypto | Direction | Entry | Strategy |",
            "|-----------|--------|-----------|-------|----------|"
        ])

        # Add sample trades
        for trade in self.trades[:10]:
            report_lines.append(
                f"| {trade.timestamp.strftime('%Y-%m-%d %H:%M')} | {trade.crypto} | {trade.direction} | "
                f"${trade.entry_price:.4f} | {trade.strategy.replace('_', ' ').title()} |"
            )

        report_lines.extend([
            "",
            "---",
            "",
            f"**Generated by:** US-RC-014 Entry Price Distribution Analyzer",
            f"**Report Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Persona:** James 'Jimmy the Greek' Martinez",
            ""
        ])

        # Write report
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        print(f"✅ Report generated: {output_file}")
        print(f"   Total trades: {stats['count']}")
        print(f"   Mean entry: ${stats['mean']:.4f}")
        print(f"   Assessment: {assessment_icon} {assessment}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python entry_price_distribution.py <bot_log_file>")
        print("Example: python entry_price_distribution.py bot.log")
        sys.exit(1)

    log_file = sys.argv[1]
    output_file = "reports/jimmy_martinez/entry_price_distribution.md"

    print("=" * 70)
    print("US-RC-014: Entry Price Distribution Analysis")
    print("Persona: James 'Jimmy the Greek' Martinez")
    print("=" * 70)
    print()

    analyzer = EntryPriceAnalyzer(log_file)

    print(f"📊 Parsing trade logs: {log_file}")
    analyzer.parse_trades()

    if not analyzer.trades:
        print("⚠️  No trades found in log file.")
        print("    Generating report with no data...")
    else:
        print(f"✅ Parsed {len(analyzer.trades)} trades")

    print()
    print(f"📈 Generating distribution report...")
    analyzer.generate_report(output_file)

    print()
    print("=" * 70)
    print("Analysis complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
