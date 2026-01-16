#!/usr/bin/env python3
"""
US-RC-015: Analyze win rate by entry price bucket
Persona: James "Jimmy the Greek" Martinez (Market Microstructure Specialist)

Do cheap entries ($0.10-0.15) actually win more? Or is the edge in mid-range prices?
Statistical significance testing with chi-square.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass
import csv


@dataclass
class Trade:
    """Represents a trade with entry price and outcome"""
    timestamp: datetime
    crypto: str
    direction: str
    entry_price: float
    shares: float
    outcome: Optional[str] = None  # "WIN" or "LOSS"
    pnl: Optional[float] = None


class EntryPriceWinRateAnalyzer:
    """Analyzes win rate by entry price bucket with statistical significance testing"""

    # Entry price buckets
    BUCKETS = [
        (0.05, 0.10, "$0.05-0.10"),
        (0.10, 0.15, "$0.10-0.15"),
        (0.15, 0.20, "$0.15-0.20"),
        (0.20, 0.25, "$0.20-0.25"),
        (0.25, 0.30, "$0.25-0.30"),
    ]

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.trades: List[Trade] = []
        self.bucket_stats: Dict[str, Dict] = defaultdict(lambda: {
            "wins": 0,
            "losses": 0,
            "total": 0,
            "win_rate": 0.0,
            "sample_entries": []
        })

    def parse_trades(self) -> None:
        """Parse bot.log for ORDER PLACED and WIN/LOSS messages"""
        if not Path(self.log_path).exists():
            print(f"Warning: Log file not found at {self.log_path}")
            return

        orders = []
        outcomes = []

        # Regex patterns
        order_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?ORDER PLACED.*?'
            r'(BTC|ETH|SOL|XRP).*?(Up|Down).*?Entry:\s*\$?([0-9.]+)'
        )
        outcome_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(WIN|LOSS).*?'
            r'(BTC|ETH|SOL|XRP).*?(Up|Down).*?P&L:\s*\$?([0-9.-]+)'
        )

        # Parse log file
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Extract orders
                    order_match = order_pattern.search(line)
                    if order_match:
                        timestamp_str, crypto, direction, entry_price = order_match.groups()
                        try:
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            orders.append({
                                'timestamp': timestamp,
                                'crypto': crypto,
                                'direction': direction,
                                'entry_price': float(entry_price),
                            })
                        except ValueError:
                            continue

                    # Extract outcomes
                    outcome_match = outcome_pattern.search(line)
                    if outcome_match:
                        timestamp_str, outcome, crypto, direction, pnl = outcome_match.groups()
                        try:
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            outcomes.append({
                                'timestamp': timestamp,
                                'outcome': outcome,
                                'crypto': crypto,
                                'direction': direction,
                                'pnl': float(pnl)
                            })
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Warning: Error parsing log file: {e}")
            return

        # Fuzzy match outcomes to orders (20-minute window)
        for order in orders:
            trade = Trade(
                timestamp=order['timestamp'],
                crypto=order['crypto'],
                direction=order['direction'],
                entry_price=order['entry_price'],
                shares=0.0  # Not extracted from logs
            )

            # Find matching outcome within 20 minutes
            for outcome in outcomes:
                time_diff = abs((outcome['timestamp'] - order['timestamp']).total_seconds())
                if (time_diff <= 1200 and  # 20 minutes
                    outcome['crypto'] == order['crypto'] and
                    outcome['direction'] == order['direction']):
                    trade.outcome = outcome['outcome']
                    trade.pnl = outcome['pnl']
                    break

            if trade.outcome:  # Only include complete trades
                self.trades.append(trade)

    def bucket_trades(self) -> None:
        """Group trades by entry price bucket"""
        for trade in self.trades:
            for min_price, max_price, label in self.BUCKETS:
                if min_price <= trade.entry_price < max_price:
                    self.bucket_stats[label]["total"] += 1
                    if trade.outcome == "WIN":
                        self.bucket_stats[label]["wins"] += 1
                    else:
                        self.bucket_stats[label]["losses"] += 1

                    # Store sample entries (first 5 per bucket)
                    if len(self.bucket_stats[label]["sample_entries"]) < 5:
                        self.bucket_stats[label]["sample_entries"].append(trade.entry_price)
                    break

        # Calculate win rates
        for label in self.bucket_stats:
            total = self.bucket_stats[label]["total"]
            if total > 0:
                self.bucket_stats[label]["win_rate"] = (
                    self.bucket_stats[label]["wins"] / total
                )

    def chi_square_test(self) -> Tuple[float, float, str]:
        """
        Perform chi-square test to determine if win rate differences are statistically significant.

        H0: Win rate is independent of entry price bucket
        H1: Win rate depends on entry price bucket

        Returns: (chi_square_stat, p_value, conclusion)
        """
        # Build contingency table
        observed_wins = []
        observed_losses = []
        bucket_labels = []

        for label in sorted(self.bucket_stats.keys()):
            if self.bucket_stats[label]["total"] >= 5:  # Minimum sample size
                observed_wins.append(self.bucket_stats[label]["wins"])
                observed_losses.append(self.bucket_stats[label]["losses"])
                bucket_labels.append(label)

        if len(bucket_labels) < 2:
            return 0.0, 1.0, "INSUFFICIENT_DATA"

        # Calculate expected frequencies
        total_wins = sum(observed_wins)
        total_losses = sum(observed_losses)
        total_trades = total_wins + total_losses

        chi_square_stat = 0.0
        degrees_of_freedom = len(bucket_labels) - 1

        for i in range(len(bucket_labels)):
            row_total = observed_wins[i] + observed_losses[i]
            expected_wins = (total_wins * row_total) / total_trades
            expected_losses = (total_losses * row_total) / total_trades

            # Chi-square formula: sum((O - E)^2 / E)
            chi_square_stat += ((observed_wins[i] - expected_wins) ** 2) / expected_wins
            chi_square_stat += ((observed_losses[i] - expected_losses) ** 2) / expected_losses

        # Approximate p-value using chi-square critical values
        # Critical values for α=0.05: df=1: 3.84, df=2: 5.99, df=3: 7.81, df=4: 9.49
        critical_values = {1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49}
        critical_value = critical_values.get(degrees_of_freedom, 9.49)

        if chi_square_stat > critical_value:
            p_value_estimate = "<0.05"
            conclusion = "SIGNIFICANT"
        else:
            p_value_estimate = ">0.05"
            conclusion = "NOT_SIGNIFICANT"

        return chi_square_stat, p_value_estimate, conclusion

    def find_optimal_entry_range(self) -> Tuple[str, float, int]:
        """
        Find entry price bucket with highest win rate

        Returns: (bucket_label, win_rate, sample_size)
        """
        best_bucket = None
        best_win_rate = 0.0
        best_sample_size = 0

        for label, stats in self.bucket_stats.items():
            if stats["total"] >= 10:  # Minimum sample size for reliability
                if stats["win_rate"] > best_win_rate:
                    best_win_rate = stats["win_rate"]
                    best_bucket = label
                    best_sample_size = stats["total"]

        return best_bucket or "N/A", best_win_rate, best_sample_size

    def generate_csv_report(self, output_path: str) -> None:
        """Generate CSV report for downstream analysis"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Entry Price Bucket",
                "Total Trades",
                "Wins",
                "Losses",
                "Win Rate",
                "Sample Entries"
            ])

            for label in sorted(self.bucket_stats.keys()):
                stats = self.bucket_stats[label]
                writer.writerow([
                    label,
                    stats["total"],
                    stats["wins"],
                    stats["losses"],
                    f"{stats['win_rate']:.1%}",
                    ", ".join([f"${p:.2f}" for p in stats["sample_entries"][:3]])
                ])

    def generate_markdown_report(self, output_path: str) -> None:
        """Generate comprehensive markdown report"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Run analysis
        chi_square, p_value, significance = self.chi_square_test()
        optimal_bucket, optimal_wr, optimal_n = self.find_optimal_entry_range()

        # Overall stats
        total_trades = len(self.trades)
        total_wins = sum(1 for t in self.trades if t.outcome == "WIN")
        overall_wr = total_wins / total_trades if total_trades > 0 else 0.0

        report_lines = [
            "# Win Rate by Entry Price Bucket Analysis",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Persona:** James \"Jimmy the Greek\" Martinez (Market Microstructure Specialist)",
            f"**Data Source:** {self.log_path}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"**Total Trades Analyzed:** {total_trades}",
            f"**Overall Win Rate:** {overall_wr:.1%}",
            f"**Optimal Entry Range:** {optimal_bucket} ({optimal_wr:.1%} WR, n={optimal_n})",
            f"**Statistical Significance:** {significance} (χ² = {chi_square:.2f}, p {p_value})",
            "",
        ]

        # Assessment
        if significance == "SIGNIFICANT":
            report_lines.extend([
                "**🟢 VERDICT:** Entry price significantly affects win rate. Cheap entries provide measurable edge.",
                "",
            ])
        elif significance == "NOT_SIGNIFICANT":
            report_lines.extend([
                "**🟡 VERDICT:** No statistically significant difference detected. Win rate appears independent of entry price (within tested ranges).",
                "",
            ])
        else:
            report_lines.extend([
                "**⚠️ VERDICT:** Insufficient data for statistical testing. Need ≥5 trades per bucket.",
                "",
            ])

        # Win rate by bucket table
        report_lines.extend([
            "---",
            "",
            "## Win Rate by Entry Price Bucket",
            "",
            "| Entry Price Bucket | Total Trades | Wins | Losses | Win Rate | Sample Entries |",
            "|-------------------|--------------|------|--------|----------|----------------|",
        ])

        for label in sorted(self.bucket_stats.keys()):
            stats = self.bucket_stats[label]
            sample_entries = ", ".join([f"${p:.2f}" for p in stats["sample_entries"][:3]])
            if not sample_entries:
                sample_entries = "—"
            report_lines.append(
                f"| {label} | {stats['total']} | {stats['wins']} | {stats['losses']} | "
                f"{stats['win_rate']:.1%} | {sample_entries} |"
            )

        report_lines.extend([
            "",
            f"**Overall:** {total_trades} trades, {total_wins}W/{total_trades - total_wins}L, {overall_wr:.1%} win rate",
            "",
        ])

        # Statistical test results
        report_lines.extend([
            "---",
            "",
            "## Statistical Significance Test (Chi-Square)",
            "",
            "**Hypothesis:**",
            "- H0: Win rate is independent of entry price bucket",
            "- H1: Win rate depends on entry price bucket",
            "",
            "**Results:**",
            f"- Chi-square statistic: {chi_square:.2f}",
            f"- P-value: {p_value}",
            f"- Conclusion: {significance}",
            "",
        ])

        if significance == "SIGNIFICANT":
            report_lines.extend([
                "**Interpretation:** The difference in win rates across entry price buckets is statistically significant (p < 0.05). Entry price selection materially impacts profitability.",
                "",
            ])
        elif significance == "NOT_SIGNIFICANT":
            report_lines.extend([
                "**Interpretation:** Win rate differences are within the range of random variation (p > 0.05). No conclusive evidence that entry price affects outcomes.",
                "",
            ])
        else:
            report_lines.extend([
                "**Interpretation:** Insufficient sample size. Need ≥5 trades per bucket for chi-square test validity.",
                "",
            ])

        # Optimal entry range
        report_lines.extend([
            "---",
            "",
            "## Optimal Entry Range",
            "",
            f"**Best Performing Bucket:** {optimal_bucket}",
            f"**Win Rate:** {optimal_wr:.1%}",
            f"**Sample Size:** {optimal_n} trades",
            "",
        ])

        if optimal_n >= 10:
            report_lines.extend([
                f"**Recommendation:** Focus entries in the **{optimal_bucket}** range for best win rate.",
                "",
            ])
        else:
            report_lines.extend([
                "**Recommendation:** Insufficient data. Need ≥10 trades per bucket for reliable recommendation.",
                "",
            ])

        # Recommendations
        report_lines.extend([
            "---",
            "",
            "## Recommendations",
            "",
        ])

        if significance == "SIGNIFICANT" and optimal_wr > overall_wr + 0.05:
            report_lines.extend([
                "### Immediate Actions",
                f"1. **Prioritize {optimal_bucket} entries** - Highest observed win rate",
                "2. **Set entry price filters** - Reject trades outside optimal range",
                "3. **Adjust strategy weights** - Boost strategies that naturally target this range",
                "",
                "### Long-term",
                "4. **Monitor win rate stability** - Re-test monthly as sample size grows",
                "5. **Test sub-ranges** - Narrow optimal bucket (e.g., $0.12-0.17)",
                "",
            ])
        elif significance == "NOT_SIGNIFICANT":
            report_lines.extend([
                "### Immediate Actions",
                "1. **No action required** - Entry price does not materially affect win rate",
                "2. **Focus on other factors** - Strategy timing, regime detection, agent accuracy",
                "",
                "### Long-term",
                "3. **Re-test with larger sample** - Current data may lack statistical power",
                "4. **Test interaction effects** - Entry price × strategy type, entry price × crypto",
                "",
            ])
        else:
            report_lines.extend([
                "### Data Collection Phase",
                "1. **Collect more data** - Need ≥50 trades per bucket for reliable analysis",
                "2. **Re-run analysis monthly** - Statistical tests require adequate sample size",
                "",
            ])

        # Methodology
        report_lines.extend([
            "---",
            "",
            "## Methodology",
            "",
            "**Data Sources:**",
            f"- Trade log: {self.log_path}",
            "- Parsed trades: ORDER PLACED + WIN/LOSS messages (fuzzy matched)",
            "",
            "**Analysis Steps:**",
            "1. Extract all trades with entry price and outcome",
            "2. Group trades by entry price bucket ($0.05 increments)",
            "3. Calculate win rate per bucket",
            "4. Perform chi-square test for statistical significance",
            "5. Identify optimal entry range (highest win rate, n ≥ 10)",
            "",
            "**Statistical Test:**",
            "- Chi-square test for independence",
            "- Significance level: α = 0.05",
            "- Minimum sample size: 5 trades per bucket",
            "",
            "**Limitations:**",
            "- Assumes independence of trades (may not hold if markets are non-stationary)",
            "- Chi-square requires adequate sample size (≥5 per bucket)",
            "- Does not account for confounding variables (crypto type, strategy, regime)",
            "",
        ])

        # Write report
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))

        print(f"✅ Report generated: {output_path}")


def main():
    """Main execution"""
    # Get log file path
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        log_file = "bot.log"

    # Run analysis
    analyzer = EntryPriceWinRateAnalyzer(log_file)
    analyzer.parse_trades()
    analyzer.bucket_trades()

    # Generate reports
    markdown_path = "reports/jimmy_martinez/entry_vs_outcome.md"
    csv_path = "reports/jimmy_martinez/entry_vs_outcome.csv"

    analyzer.generate_markdown_report(markdown_path)
    analyzer.generate_csv_report(csv_path)

    print(f"✅ Analysis complete")
    print(f"   - Markdown: {markdown_path}")
    print(f"   - CSV: {csv_path}")
    print(f"   - Trades analyzed: {len(analyzer.trades)}")

    # Exit code
    sys.exit(0)


if __name__ == "__main__":
    main()
