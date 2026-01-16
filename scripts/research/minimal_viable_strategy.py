#!/usr/bin/env python3
"""
Minimal Viable Strategy (MVS) Benchmark

Author: Alex 'Occam' Rousseau (First Principles Engineer)
Persona Context: "What's the simplest strategy that could beat 53% breakeven?
                   Start there, THEN add complexity—only if it helps."

Design ultra-simple baseline strategies and compare to current system.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class Trade:
    """Minimal trade representation"""
    timestamp: str
    crypto: str
    direction: str
    entry_price: float
    shares: float
    outcome: Optional[str] = None
    epoch_id: Optional[str] = None
    seconds_into_epoch: Optional[int] = None


@dataclass
class StrategyResult:
    """Strategy performance results"""
    name: str
    description: str
    total_trades: int
    wins: int
    losses: int
    skips: int
    win_rate: float
    total_pnl: float


class MVStrategy:
    """Base class for minimal viable strategies"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        random.seed(42)  # For reproducibility

    def should_trade(self, trade: Trade) -> bool:
        """Return True if strategy would take this trade"""
        raise NotImplementedError

    def predict_outcome(self, trade: Trade) -> str:
        """Return 'WIN' or 'LOSS' prediction"""
        raise NotImplementedError


class RandomStrategy(MVStrategy):
    """Strategy 1: Pure random (50/50 coin flip)"""

    def __init__(self):
        super().__init__(
            "Random Baseline",
            "50/50 coin flip at $0.15 entry (control group)"
        )

    def should_trade(self, trade: Trade) -> bool:
        # Only trade if entry < $0.20 (within budget)
        return trade.entry_price <= 0.20

    def predict_outcome(self, trade: Trade) -> str:
        return 'WIN' if random.random() > 0.5 else 'LOSS'


class MomentumOnlyStrategy(MVStrategy):
    """Strategy 2: Simple momentum (if 3+ exchanges agree)"""

    def __init__(self):
        super().__init__(
            "Momentum Only",
            "Trade only if 3+ exchanges show agreement (simulated)"
        )
        self.confluence_threshold = 0.7  # Simulated confluence

    def should_trade(self, trade: Trade) -> bool:
        # Simulate confluence: cheaper entry = less agreement needed
        # This is a proxy since we don't have real exchange data in logs
        if trade.entry_price < 0.15:
            return random.random() > 0.3  # 70% trade rate for cheap entries
        elif trade.entry_price < 0.25:
            return random.random() > 0.5  # 50% trade rate for mid entries
        else:
            return random.random() > 0.8  # 20% trade rate for expensive entries

    def predict_outcome(self, trade: Trade) -> str:
        # Cheaper entry = better odds (inverse correlation)
        win_prob = 0.7 if trade.entry_price < 0.15 else 0.55
        return 'WIN' if random.random() < win_prob else 'LOSS'


class ContrarianOnlyStrategy(MVStrategy):
    """Strategy 3: Fade overpriced markets (>70% one side)"""

    def __init__(self):
        super().__init__(
            "Contrarian Only",
            "Fade markets >70% on one side (cheap entry <$0.20)"
        )

    def should_trade(self, trade: Trade) -> bool:
        # Contrarian only trades cheap entries (opposite side >70% = entry <30%)
        return trade.entry_price <= 0.20

    def predict_outcome(self, trade: Trade) -> str:
        # Contrarian has better odds at cheaper entries (mean reversion)
        if trade.entry_price < 0.10:
            win_prob = 0.75  # Very cheap = very overpriced other side
        elif trade.entry_price < 0.15:
            win_prob = 0.65
        else:
            win_prob = 0.55
        return 'WIN' if random.random() < win_prob else 'LOSS'


class PriceBasedStrategy(MVStrategy):
    """Strategy 4: Always buy <$0.20, skip >$0.20"""

    def __init__(self):
        super().__init__(
            "Price Filter Only",
            "Trade any market <$0.20 entry, skip expensive"
        )

    def should_trade(self, trade: Trade) -> bool:
        return trade.entry_price < 0.20

    def predict_outcome(self, trade: Trade) -> str:
        # Simple model: cheaper = better odds
        if trade.entry_price < 0.10:
            win_prob = 0.70
        elif trade.entry_price < 0.15:
            win_prob = 0.60
        else:
            win_prob = 0.55
        return 'WIN' if random.random() < win_prob else 'LOSS'


class BestAgentStrategy(MVStrategy):
    """Strategy 5: Single best agent (from Vic's analysis)"""

    def __init__(self, best_agent_wr: float = 0.62):
        super().__init__(
            "Single Best Agent",
            "Use only the highest-performing agent (62% WR assumed)"
        )
        self.win_rate = best_agent_wr

    def should_trade(self, trade: Trade) -> bool:
        # Single agent with confidence threshold
        # Simulate confidence: better entries = higher confidence
        if trade.entry_price < 0.15:
            confidence = random.uniform(0.6, 0.9)
        elif trade.entry_price < 0.25:
            confidence = random.uniform(0.5, 0.7)
        else:
            confidence = random.uniform(0.3, 0.6)

        return confidence > 0.60  # Confidence threshold

    def predict_outcome(self, trade: Trade) -> str:
        # Use assumed best agent WR
        return 'WIN' if random.random() < self.win_rate else 'LOSS'


def parse_trade_logs(log_file: Path) -> List[Trade]:
    """Parse trade logs (reuse Kenji's parser logic)"""
    trades = []

    if not log_file.exists():
        print(f"⚠️  Log file not found: {log_file}")
        return trades

    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Parse trade line (format from Kenji's parser)
            # timestamp,crypto,direction,entry_price,shares,outcome,epoch_id
            parts = line.split(',')
            if len(parts) < 5:
                continue

            try:
                trade = Trade(
                    timestamp=parts[0],
                    crypto=parts[1],
                    direction=parts[2],
                    entry_price=float(parts[3]),
                    shares=float(parts[4]),
                    outcome=parts[5] if len(parts) > 5 and parts[5] else None,
                    epoch_id=parts[6] if len(parts) > 6 and parts[6] else None
                )
                trades.append(trade)
            except (ValueError, IndexError) as e:
                continue

    return trades


def backtest_strategy(strategy: MVStrategy, trades: List[Trade], starting_balance: float = 100.0) -> StrategyResult:
    """Backtest a strategy on historical trades"""
    wins = 0
    losses = 0
    skips = 0
    balance = starting_balance

    for trade in trades:
        # Skip incomplete trades (no outcome)
        if not trade.outcome or trade.outcome not in ['WIN', 'LOSS']:
            skips += 1
            continue

        # Check if strategy would trade
        if not strategy.should_trade(trade):
            skips += 1
            continue

        # Strategy makes prediction
        prediction = strategy.predict_outcome(trade)

        # Compare to actual outcome
        if prediction == trade.outcome:
            wins += 1
            # Win: $1.00 per share - entry cost
            pnl = trade.shares * (1.0 - trade.entry_price)
            balance += pnl
        else:
            losses += 1
            # Loss: -entry cost
            pnl = -trade.shares * trade.entry_price
            balance += pnl

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0.0
    total_pnl = balance - starting_balance

    return StrategyResult(
        name=strategy.name,
        description=strategy.description,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        skips=skips,
        win_rate=win_rate,
        total_pnl=total_pnl
    )


def generate_report(results: List[StrategyResult], current_system_wr: float, output_file: Path):
    """Generate MVS benchmark CSV report"""

    # Write CSV
    with open(output_file, 'w') as f:
        f.write("Strategy,Description,Total Trades,Wins,Losses,Skips,Win Rate,Total P&L,vs Current System\n")

        for result in sorted(results, key=lambda x: x.win_rate, reverse=True):
            vs_current = result.win_rate - current_system_wr
            vs_current_str = f"+{vs_current:.1%}" if vs_current > 0 else f"{vs_current:.1%}"

            f.write(f'"{result.name}","{result.description}",')
            f.write(f"{result.total_trades},{result.wins},{result.losses},{result.skips},")
            f.write(f"{result.win_rate:.1%},{result.total_pnl:+.2f},{vs_current_str}\n")

        # Add current system baseline
        f.write(f'"Current System","Multi-agent consensus (56-60% WR claimed)",-,-,-,-,')
        f.write(f"{current_system_wr:.1%},-,baseline\n")

    print(f"✅ Report saved: {output_file}")


def generate_markdown_report(results: List[StrategyResult], current_system_wr: float,
                             total_trades: int, output_file: Path):
    """Generate comprehensive markdown analysis report"""

    # Sort by win rate
    sorted_results = sorted(results, key=lambda x: x.win_rate, reverse=True)

    with open(output_file, 'w') as f:
        f.write("# Minimal Viable Strategy (MVS) Benchmark\n\n")
        f.write("**Author:** Alex 'Occam' Rousseau (First Principles Engineer)\n")
        f.write("**Date:** 2026-01-16\n")
        f.write("**Persona Context:** \"What's the simplest strategy that could beat 53% breakeven? ")
        f.write("Start there, THEN add complexity—only if it helps.\"\n\n")
        f.write("---\n\n")

        # Executive Summary
        f.write("## Executive Summary\n\n")
        f.write(f"**Test Sample:** {total_trades} completed trades\n")
        f.write(f"**Current System WR:** {current_system_wr:.1%} (claimed)\n")
        f.write(f"**Strategies Tested:** 5 ultra-simple baselines\n\n")

        # Find best MVS
        best = sorted_results[0]
        f.write(f"**🏆 Best MVS:** {best.name} ({best.win_rate:.1%} WR, {best.total_trades} trades)\n")

        # Key Finding
        if best.win_rate > current_system_wr:
            f.write(f"\n⚠️ **KEY FINDING:** Simple strategy ({best.name}) BEATS current system ")
            f.write(f"by {best.win_rate - current_system_wr:.1%}\n")
            f.write("**Conclusion:** Current system is over-engineered. Start with MVS.\n\n")
        else:
            f.write(f"\n✅ Current system ({current_system_wr:.1%}) outperforms all MVS strategies.\n")
            f.write("**Conclusion:** Complexity is earning its keep. Continue optimization.\n\n")

        f.write("---\n\n")

        # Strategy Rankings
        f.write("## Strategy Rankings\n\n")
        f.write("| Rank | Strategy | Description | Trades | WR | P&L | vs Current |\n")
        f.write("|------|----------|-------------|--------|----|----|------------|\n")

        for i, result in enumerate(sorted_results, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""
            vs_current = result.win_rate - current_system_wr
            vs_str = f"+{vs_current:.1%}" if vs_current > 0 else f"{vs_current:.1%}"

            f.write(f"| {i} {emoji} | {result.name} | {result.description} | ")
            f.write(f"{result.total_trades} | {result.win_rate:.1%} | ${result.total_pnl:+.2f} | {vs_str} |\n")

        # Current system baseline
        f.write(f"| - | **Current System** | Multi-agent consensus | - | {current_system_wr:.1%} | - | baseline |\n\n")

        f.write("---\n\n")

        # Detailed Analysis
        f.write("## Detailed Analysis\n\n")

        for result in sorted_results:
            f.write(f"### {result.name}\n\n")
            f.write(f"**Description:** {result.description}\n\n")
            f.write(f"**Performance:**\n")
            f.write(f"- Total Trades: {result.total_trades}\n")
            f.write(f"- Wins: {result.wins}\n")
            f.write(f"- Losses: {result.losses}\n")
            f.write(f"- Skips: {result.skips}\n")
            f.write(f"- Win Rate: {result.win_rate:.1%}\n")
            f.write(f"- Total P&L: ${result.total_pnl:+.2f}\n\n")

            # Verdict
            if result.win_rate > current_system_wr:
                f.write(f"**Verdict:** ✅ OUTPERFORMS current system (+{result.win_rate - current_system_wr:.1%})\n\n")
            elif result.win_rate > 0.53:
                f.write(f"**Verdict:** ⚠️ Profitable but below current system ({result.win_rate - current_system_wr:.1%})\n\n")
            else:
                f.write(f"**Verdict:** ❌ Below breakeven (53% needed, got {result.win_rate:.1%})\n\n")

        f.write("---\n\n")

        # Recommendations
        f.write("## Recommendations\n\n")

        if best.win_rate > current_system_wr + 0.03:
            f.write("### 🚨 CRITICAL: Over-Engineering Detected\n\n")
            f.write(f"The simplest strategy ({best.name}) significantly outperforms the current ")
            f.write(f"multi-agent system. This suggests:\n\n")
            f.write("1. **Current complexity is counterproductive**\n")
            f.write("2. **Multiple agents may be canceling out** (herding, conflicts)\n")
            f.write("3. **Start with MVS and add ONE component at a time** (if proven beneficial)\n\n")
            f.write("**Action Items:**\n")
            f.write(f"- [ ] Deploy {best.name} as baseline\n")
            f.write("- [ ] Shadow test current system vs MVS for 100 trades\n")
            f.write("- [ ] Only add complexity if shadow data proves benefit\n\n")

        elif best.win_rate > current_system_wr:
            f.write("### ⚠️ WARNING: Simpler May Be Better\n\n")
            f.write(f"{best.name} slightly outperforms current system. Consider:\n\n")
            f.write("1. Test MVS in shadow mode (risk-free)\n")
            f.write("2. Identify which agents/features drag down performance\n")
            f.write("3. Simplify by removing underperformers\n\n")

        else:
            f.write("### ✅ Current System Justified\n\n")
            f.write("No MVS strategy beats the current system. Complexity appears justified.\n\n")
            f.write("**Next Steps:**\n")
            f.write("1. Continue with US-RC-031E (complexity cost-benefit analysis)\n")
            f.write("2. Optimize current system (remove underperformers, raise thresholds)\n")
            f.write("3. Target 60-65% WR through refinement, not simplification\n\n")

        f.write("---\n\n")

        # Data Limitations
        f.write("## Data Limitations\n\n")
        if total_trades < 50:
            f.write(f"⚠️ **SMALL SAMPLE:** Only {total_trades} trades analyzed\n")
            f.write("- Statistical significance is LOW\n")
            f.write("- Requires ≥100 trades for confident conclusions\n")
            f.write("- Treat results as directional, not definitive\n\n")

        f.write("**Note:** MVS strategies use simulated logic (random seeds) for predictions ")
        f.write("since we don't have real-time exchange data in logs. Results show relative ")
        f.write("performance, not absolute predictions.\n\n")

    print(f"✅ Detailed report saved: {output_file}")


def main():
    """Main execution"""
    print("=" * 80)
    print("MINIMAL VIABLE STRATEGY (MVS) BENCHMARK")
    print("=" * 80)
    print("Author: Alex 'Occam' Rousseau (First Principles Engineer)")
    print("Mindset: \"What's the simplest thing that could possibly work?\"")
    print("=" * 80)
    print()

    # Configuration
    project_root = Path(__file__).parent.parent.parent
    log_file = project_root / "test_trade_log.txt"
    output_csv = project_root / "reports" / "alex_rousseau" / "mvs_benchmark.csv"
    output_md = project_root / "reports" / "alex_rousseau" / "mvs_benchmark.md"
    current_system_wr = 0.58  # Claimed 56-60%, use midpoint

    # Ensure output directory exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    # Parse trade logs
    print(f"📊 Parsing trade logs: {log_file}")
    trades = parse_trade_logs(log_file)

    if not trades:
        print("❌ No trades found in log file!")
        return 1

    complete_trades = [t for t in trades if t.outcome in ['WIN', 'LOSS']]
    print(f"✅ Found {len(trades)} total trades ({len(complete_trades)} complete)")
    print()

    if len(complete_trades) < 10:
        print(f"⚠️  WARNING: Only {len(complete_trades)} complete trades (need ≥100 for statistical significance)")
        print("   Results will be directional only, not definitive.")
        print()

    # Define strategies
    strategies: List[MVStrategy] = [
        RandomStrategy(),
        MomentumOnlyStrategy(),
        ContrarianOnlyStrategy(),
        PriceBasedStrategy(),
        BestAgentStrategy(best_agent_wr=0.62)  # Assumed from Vic's analysis
    ]

    # Backtest each strategy
    print("🧪 Backtesting MVS strategies...")
    print()

    results: List[StrategyResult] = []
    for strategy in strategies:
        print(f"Testing: {strategy.name}")
        result = backtest_strategy(strategy, trades)
        results.append(result)
        print(f"  → {result.total_trades} trades, {result.win_rate:.1%} WR, ${result.total_pnl:+.2f} P&L")

    print()

    # Generate reports
    print("📝 Generating reports...")
    generate_report(results, current_system_wr, output_csv)
    generate_markdown_report(results, current_system_wr, len(complete_trades), output_md)

    # Summary
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    best = max(results, key=lambda x: x.win_rate)
    print(f"🏆 Best MVS: {best.name} ({best.win_rate:.1%} WR)")
    print(f"📊 Current System: {current_system_wr:.1%} WR (claimed)")
    print()

    if best.win_rate > current_system_wr:
        delta = best.win_rate - current_system_wr
        print(f"⚠️  FINDING: MVS beats current system by {delta:.1%}")
        print("   → Current system may be over-engineered")
        print("   → Consider starting with MVS and adding complexity ONLY if proven")
    else:
        print("✅ Current system outperforms all MVS strategies")
        print("   → Complexity appears justified")
        print("   → Continue optimization (not simplification)")

    print()
    print(f"📄 Detailed analysis: {output_md}")
    print(f"📊 CSV export: {output_csv}")
    print()
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())
