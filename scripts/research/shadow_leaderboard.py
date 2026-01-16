#!/usr/bin/env python3
"""
Shadow Strategy Leaderboard - Query and rank shadow strategies from database

Author: Victor "Vic" Ramanujan (Quantitative Strategist)
Date: 2026-01-16
Purpose: Extract shadow strategy performance from trade_journal.db and rank by P&L
"""

import sqlite3
import csv
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StrategyPerformance:
    """Performance metrics for a shadow strategy"""
    strategy_name: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    roi: float
    avg_pnl_per_trade: float
    sharpe_ratio: float


class ShadowLeaderboard:
    """Query shadow strategy performance and generate leaderboard"""

    def __init__(self, db_path: str = "simulation/trade_journal.db"):
        self.db_path = db_path
        self.strategies: List[StrategyPerformance] = []

    def query_performance(self) -> None:
        """Query performance table for all strategies"""
        if not Path(self.db_path).exists():
            print(f"WARNING: Database not found at {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Query latest performance snapshot for each strategy
            query = """
                SELECT
                    strategy,
                    total_trades,
                    wins,
                    losses,
                    win_rate,
                    total_pnl,
                    roi
                FROM performance p1
                WHERE timestamp = (
                    SELECT MAX(timestamp)
                    FROM performance p2
                    WHERE p2.strategy = p1.strategy
                )
                ORDER BY total_pnl DESC
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                strategy, trades, wins, losses, wr, pnl, roi = row

                # Calculate additional metrics
                avg_pnl = pnl / max(trades, 1)

                # Simple Sharpe ratio approximation
                # Sharpe = (avg_return - risk_free_rate) / std_dev_return
                # For simplicity: sharpe ≈ avg_pnl * sqrt(trades) / (pnl_volatility)
                # If insufficient data, set to 0
                sharpe = 0.0
                if trades >= 10:
                    # Query individual trade P&L for volatility calculation
                    pnl_query = """
                        SELECT pnl FROM outcomes
                        WHERE strategy = ?
                        ORDER BY timestamp DESC
                        LIMIT 100
                    """
                    cursor.execute(pnl_query, (strategy,))
                    pnl_values = [r[0] for r in cursor.fetchall()]

                    if len(pnl_values) >= 10:
                        # Calculate standard deviation
                        mean_pnl = sum(pnl_values) / len(pnl_values)
                        variance = sum((x - mean_pnl) ** 2 for x in pnl_values) / len(pnl_values)
                        std_dev = variance ** 0.5

                        if std_dev > 0:
                            sharpe = (mean_pnl / std_dev) * (len(pnl_values) ** 0.5)

                self.strategies.append(StrategyPerformance(
                    strategy_name=strategy,
                    total_trades=trades,
                    wins=wins,
                    losses=losses,
                    win_rate=wr,
                    total_pnl=pnl,
                    roi=roi,
                    avg_pnl_per_trade=avg_pnl,
                    sharpe_ratio=sharpe
                ))

            conn.close()

        except sqlite3.Error as e:
            print(f"ERROR: Database query failed: {e}", file=sys.stderr)

    def generate_csv(self, output_path: str) -> None:
        """Generate CSV leaderboard"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Rank", "Strategy", "Total Trades", "Wins", "Losses",
                "Win Rate", "Total P&L", "Avg P&L/Trade", "ROI", "Sharpe Ratio"
            ])

            for rank, strat in enumerate(self.strategies, 1):
                writer.writerow([
                    rank,
                    strat.strategy_name,
                    strat.total_trades,
                    strat.wins,
                    strat.losses,
                    f"{strat.win_rate * 100:.1f}%",
                    f"${strat.total_pnl:.2f}",
                    f"${strat.avg_pnl_per_trade:.2f}",
                    f"{strat.roi * 100:.1f}%",
                    f"{strat.sharpe_ratio:.2f}"
                ])

        print(f"CSV leaderboard saved to {output_path}")

    def generate_markdown_report(self, output_path: str) -> None:
        """Generate detailed markdown report"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Identify baseline (random) strategy if exists
        baseline = next((s for s in self.strategies if 'random' in s.strategy_name.lower()), None)
        default = next((s for s in self.strategies if s.strategy_name == 'default'), None)

        # Calculate summary stats
        total_strategies = len(self.strategies)
        top_10 = self.strategies[:10] if len(self.strategies) >= 10 else self.strategies
        bottom_5 = self.strategies[-5:] if len(self.strategies) >= 5 else []

        # Determine assessment
        assessment = "INSUFFICIENT DATA"
        if total_strategies >= 10 and any(s.total_trades >= 10 for s in self.strategies):
            assessment = "SUFFICIENT DATA"

        report_lines = []
        report_lines.append("# Shadow Strategy Leaderboard Report")
        report_lines.append("")
        report_lines.append(f"**Author:** Victor 'Vic' Ramanujan (Quantitative Strategist)")
        report_lines.append(f"**Date:** 2026-01-16")
        report_lines.append(f"**Data Source:** {self.db_path}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("## Executive Summary")
        report_lines.append("")
        report_lines.append(f"**Assessment:** {assessment}")
        report_lines.append(f"**Total Strategies Analyzed:** {total_strategies}")

        if total_strategies > 0:
            max_trades = max(s.total_trades for s in self.strategies)
            report_lines.append(f"**Max Trades per Strategy:** {max_trades}")

            if baseline:
                report_lines.append(f"**Baseline (Random) Performance:** {baseline.win_rate*100:.1f}% WR, ${baseline.total_pnl:.2f} P&L")

            if default:
                report_lines.append(f"**Default (Live) Performance:** {default.win_rate*100:.1f}% WR, ${default.total_pnl:.2f} P&L")

                if baseline and default.total_trades >= 10 and baseline.total_trades >= 10:
                    if default.total_pnl > baseline.total_pnl:
                        report_lines.append("")
                        report_lines.append(f"✅ **Verdict:** Default strategy BEATS random baseline by ${default.total_pnl - baseline.total_pnl:.2f} (edge confirmed)")
                    else:
                        report_lines.append("")
                        report_lines.append(f"❌ **Verdict:** Default strategy UNDERPERFORMS random baseline by ${baseline.total_pnl - default.total_pnl:.2f} (negative edge)")
        else:
            report_lines.append("")
            report_lines.append("⚠️ **No shadow strategy data available** (bot may not be running or database empty)")

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        # Top 10 Strategies
        report_lines.append("## Top 10 Strategies (by Total P&L)")
        report_lines.append("")

        if len(top_10) > 0:
            report_lines.append("| Rank | Strategy | Trades | W/L | Win Rate | Total P&L | Avg P&L | ROI | Sharpe |")
            report_lines.append("|------|----------|--------|-----|----------|-----------|---------|-----|--------|")

            for rank, strat in enumerate(top_10, 1):
                emoji = "🟢" if rank == 1 else ("🟡" if rank <= 3 else "")
                report_lines.append(
                    f"| {emoji}{rank} | {strat.strategy_name} | {strat.total_trades} | "
                    f"{strat.wins}W/{strat.losses}L | {strat.win_rate*100:.1f}% | "
                    f"${strat.total_pnl:+.2f} | ${strat.avg_pnl_per_trade:+.2f} | "
                    f"{strat.roi*100:+.1f}% | {strat.sharpe_ratio:.2f} |"
                )
        else:
            report_lines.append("*No strategies found in database*")

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        # Bottom 5 Strategies
        if len(bottom_5) > 0:
            report_lines.append("## Bottom 5 Strategies (by Total P&L)")
            report_lines.append("")
            report_lines.append("| Rank | Strategy | Trades | W/L | Win Rate | Total P&L | Avg P&L | ROI |")
            report_lines.append("|------|----------|--------|-----|----------|-----------|---------|-----|")

            start_rank = len(self.strategies) - len(bottom_5) + 1
            for idx, strat in enumerate(bottom_5):
                rank = start_rank + idx
                emoji = "🔴" if idx == len(bottom_5) - 1 else ""
                report_lines.append(
                    f"| {emoji}{rank} | {strat.strategy_name} | {strat.total_trades} | "
                    f"{strat.wins}W/{strat.losses}L | {strat.win_rate*100:.1f}% | "
                    f"${strat.total_pnl:+.2f} | ${strat.avg_pnl_per_trade:+.2f} | "
                    f"{strat.roi*100:+.1f}% |"
                )

            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")

        # Baseline Comparison
        if baseline and default:
            report_lines.append("## Baseline Comparison")
            report_lines.append("")
            report_lines.append("Comparing default strategy against random baseline to test for edge:")
            report_lines.append("")
            report_lines.append("| Metric | Random Baseline | Default (Live) | Difference |")
            report_lines.append("|--------|-----------------|----------------|------------|")
            report_lines.append(f"| Win Rate | {baseline.win_rate*100:.1f}% | {default.win_rate*100:.1f}% | {(default.win_rate - baseline.win_rate)*100:+.1f}% |")
            report_lines.append(f"| Total P&L | ${baseline.total_pnl:.2f} | ${default.total_pnl:.2f} | ${default.total_pnl - baseline.total_pnl:+.2f} |")
            report_lines.append(f"| Avg P&L/Trade | ${baseline.avg_pnl_per_trade:.2f} | ${default.avg_pnl_per_trade:.2f} | ${default.avg_pnl_per_trade - baseline.avg_pnl_per_trade:+.2f} |")
            report_lines.append(f"| ROI | {baseline.roi*100:.1f}% | {default.roi*100:.1f}% | {(default.roi - baseline.roi)*100:+.1f}% |")
            report_lines.append("")

            if default.total_trades >= 10 and baseline.total_trades >= 10:
                if default.total_pnl > baseline.total_pnl:
                    report_lines.append(f"✅ **Conclusion:** Default strategy has positive edge (outperforms random by ${default.total_pnl - baseline.total_pnl:.2f})")
                elif default.total_pnl < baseline.total_pnl:
                    report_lines.append(f"❌ **Conclusion:** Default strategy has negative edge (underperforms random by ${baseline.total_pnl - default.total_pnl:.2f})")
                else:
                    report_lines.append("⚪ **Conclusion:** Default strategy matches random baseline (no edge detected)")
            else:
                report_lines.append("⚠️ **Conclusion:** Insufficient sample size (<10 trades) for reliable comparison")

            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")

        # Recommendations
        report_lines.append("## Recommendations")
        report_lines.append("")

        if total_strategies == 0:
            report_lines.append("**Data Collection Phase:**")
            report_lines.append("- Shadow trading system not populated yet")
            report_lines.append("- Ensure bot is running with shadow strategies enabled")
            report_lines.append("- Re-run this analysis after 50+ trades per strategy")
        elif assessment == "INSUFFICIENT DATA":
            report_lines.append("**Data Collection Phase:**")
            report_lines.append(f"- Current max trades per strategy: {max(s.total_trades for s in self.strategies)}")
            report_lines.append("- Need ≥10 trades per strategy for reliable comparison")
            report_lines.append("- Continue shadow trading for 1-2 weeks")
            report_lines.append("- Re-run this analysis weekly")
        else:
            report_lines.append("**Immediate Actions:**")

            if len(top_10) > 0:
                winner = top_10[0]
                report_lines.append(f"- **Top performer:** {winner.strategy_name} (${winner.total_pnl:+.2f}, {winner.win_rate*100:.1f}% WR)")

                if default and winner.strategy_name != 'default' and winner.total_pnl > default.total_pnl + 5.0:
                    report_lines.append(f"- **Consider promoting:** {winner.strategy_name} outperforms default by ${winner.total_pnl - default.total_pnl:.2f}")

            if len(bottom_5) > 0:
                loser = bottom_5[-1]
                if loser.win_rate < 0.50:
                    report_lines.append(f"- **Disable underperformer:** {loser.strategy_name} ({loser.win_rate*100:.1f}% WR, ${loser.total_pnl:+.2f})")

            report_lines.append("")
            report_lines.append("**Long-term Monitoring:**")
            report_lines.append("- Track Sharpe ratio for risk-adjusted returns")
            report_lines.append("- Monitor win rate stability (weekly moving average)")
            report_lines.append("- Test top 3 strategies on next 100 trades (walk-forward validation)")

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        # Methodology
        report_lines.append("## Methodology")
        report_lines.append("")
        report_lines.append("**Data Source:** SQLite database `trade_journal.db`")
        report_lines.append("")
        report_lines.append("**Query Logic:**")
        report_lines.append("- Extract latest performance snapshot for each strategy")
        report_lines.append("- Rank by total P&L (primary) and win rate (secondary)")
        report_lines.append("- Calculate Sharpe ratio for strategies with ≥10 trades")
        report_lines.append("")
        report_lines.append("**Sharpe Ratio Calculation:**")
        report_lines.append("- `Sharpe = (avg_pnl / std_dev_pnl) * sqrt(n_trades)`")
        report_lines.append("- Higher Sharpe = better risk-adjusted returns")
        report_lines.append("- Requires ≥10 trades for reliable calculation")
        report_lines.append("")
        report_lines.append("**Baseline Strategy:**")
        report_lines.append("- Random 50/50 coin flip at typical entry price ($0.20)")
        report_lines.append("- If default strategy underperforms random, system has negative edge")
        report_lines.append("")

        # Write report
        with open(output_path, 'w') as f:
            f.write('\n'.join(report_lines))

        print(f"Markdown report saved to {output_path}")


def main():
    """Main execution"""
    db_path = "simulation/trade_journal.db"
    csv_path = "reports/vic_ramanujan/shadow_leaderboard.csv"
    md_path = "reports/vic_ramanujan/shadow_leaderboard.md"

    print("=" * 80)
    print("Shadow Strategy Leaderboard")
    print("=" * 80)
    print()

    leaderboard = ShadowLeaderboard(db_path)
    leaderboard.query_performance()

    print(f"Strategies analyzed: {len(leaderboard.strategies)}")

    if len(leaderboard.strategies) > 0:
        print(f"Top performer: {leaderboard.strategies[0].strategy_name} (${leaderboard.strategies[0].total_pnl:+.2f})")
        print(f"Bottom performer: {leaderboard.strategies[-1].strategy_name} (${leaderboard.strategies[-1].total_pnl:+.2f})")

    print()
    print("Generating reports...")
    leaderboard.generate_csv(csv_path)
    leaderboard.generate_markdown_report(md_path)

    print()
    print("✅ Shadow leaderboard analysis complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
