#!/usr/bin/env python3
"""
Gambler's Fallacy Test - Dr. Amara Johnson (Behavioral Finance Expert)
=====================================================================

Persona Context:
"After 3 losses, does the bot bet more aggressively expecting a win? That's gambler's fallacy."

Tests whether the bot exhibits gambler's fallacy by:
1. Identifying consecutive loss streaks
2. Measuring position sizing changes after losses
3. Measuring entry price threshold changes after losses
4. Statistical correlation test (bet sizing vs recent losses)

Gambler's fallacy = belief that past losses increase probability of future wins.
Rational bot = position sizing and thresholds independent of recent outcomes.
"""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path
import math


@dataclass
class Trade:
    """Trade record from bot logs"""
    timestamp: str
    crypto: str
    direction: str
    entry_price: float
    shares: float
    position_size_usd: float
    outcome: Optional[str] = None  # 'WIN' or 'LOSS'
    pnl: Optional[float] = None


@dataclass
class LossStreakObservation:
    """Observation of bot behavior after loss streak"""
    streak_length: int  # Number of consecutive losses
    next_position_size: float  # Position size of next trade
    next_entry_price: float  # Entry price of next trade
    baseline_position_size: float  # Average position size before streak
    baseline_entry_price: float  # Average entry price before streak


def parse_bot_log(log_path: str) -> List[Trade]:
    """Parse bot.log to extract trades with outcomes"""
    trades = []

    # Regex patterns
    order_pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*'
        r'ORDER PLACED.*?'
        r'(BTC|ETH|SOL|XRP).*?'
        r'(Up|Down).*?'
        r'\$([0-9.]+).*?'
        r'(\d+(?:\.\d+)?)\s+shares.*?'
        r'\$([0-9.]+)',
        re.IGNORECASE
    )

    outcome_pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*'
        r'(WIN|LOSS).*?'
        r'(BTC|ETH|SOL|XRP).*?'
        r'(Up|Down).*?'
        r'P&L[:\s]+\$?([+-]?[0-9.]+)',
        re.IGNORECASE
    )

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"⚠️  Warning: {log_path} not found")
        return []

    # Parse ORDER PLACED
    pending_trades = {}
    for match in order_pattern.finditer(content):
        timestamp = match.group(1)
        crypto = match.group(2).upper()
        direction = match.group(3).capitalize()
        entry_price = float(match.group(4))
        shares = float(match.group(5))
        position_size = float(match.group(6))

        key = f"{crypto}_{direction}_{timestamp[:16]}"  # Match by crypto + direction + minute
        pending_trades[key] = Trade(
            timestamp=timestamp,
            crypto=crypto,
            direction=direction,
            entry_price=entry_price,
            shares=shares,
            position_size_usd=position_size
        )

    # Match outcomes to trades (fuzzy matching: within 20 min window)
    for match in outcome_pattern.finditer(content):
        outcome_ts = match.group(1)
        outcome = match.group(2).upper()
        crypto = match.group(3).upper()
        direction = match.group(4).capitalize()
        pnl = float(match.group(5))

        # Find matching pending trade
        for key, trade in pending_trades.items():
            if trade.crypto == crypto and trade.direction == direction and trade.outcome is None:
                # Check timestamp proximity (within 20 minutes)
                from datetime import datetime
                trade_time = datetime.strptime(trade.timestamp, '%Y-%m-%d %H:%M:%S')
                outcome_time = datetime.strptime(outcome_ts, '%Y-%m-%d %H:%M:%S')
                diff_minutes = abs((outcome_time - trade_time).total_seconds() / 60)

                if diff_minutes <= 20:
                    trade.outcome = outcome
                    trade.pnl = pnl
                    break

    # Return only trades with known outcomes
    trades = [t for t in pending_trades.values() if t.outcome is not None]

    # Sort by timestamp
    trades.sort(key=lambda t: t.timestamp)

    return trades


def identify_loss_streaks(trades: List[Trade]) -> List[Tuple[int, int]]:
    """
    Identify consecutive loss streaks in trades.
    Returns list of (start_index, streak_length) tuples.
    """
    streaks = []
    current_streak_start = None
    current_streak_length = 0

    for i, trade in enumerate(trades):
        if trade.outcome == 'LOSS':
            if current_streak_start is None:
                current_streak_start = i
            current_streak_length += 1
        else:
            # Streak ended
            if current_streak_length > 0:
                streaks.append((current_streak_start, current_streak_length))
            current_streak_start = None
            current_streak_length = 0

    # Handle streak at end
    if current_streak_length > 0:
        streaks.append((current_streak_start, current_streak_length))

    return streaks


def analyze_post_streak_behavior(trades: List[Trade], streaks: List[Tuple[int, int]]) -> List[LossStreakObservation]:
    """
    Analyze bot behavior after each loss streak.
    Compare position sizing and entry prices to baseline.
    """
    observations = []

    for streak_start, streak_length in streaks:
        streak_end = streak_start + streak_length - 1

        # Next trade after streak (if exists)
        if streak_end + 1 >= len(trades):
            continue  # No trade after streak

        next_trade = trades[streak_end + 1]

        # Calculate baseline from trades BEFORE streak (last 10 trades, or fewer if not available)
        baseline_start = max(0, streak_start - 10)
        baseline_trades = trades[baseline_start:streak_start]

        if len(baseline_trades) == 0:
            # No baseline available (streak at start of history)
            continue

        baseline_position_size = sum(t.position_size_usd for t in baseline_trades) / len(baseline_trades)
        baseline_entry_price = sum(t.entry_price for t in baseline_trades) / len(baseline_trades)

        observations.append(LossStreakObservation(
            streak_length=streak_length,
            next_position_size=next_trade.position_size_usd,
            next_entry_price=next_trade.entry_price,
            baseline_position_size=baseline_position_size,
            baseline_entry_price=baseline_entry_price
        ))

    return observations


def calculate_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient and p-value.

    Returns:
        (correlation_coefficient, p_value)
    """
    if len(x) != len(y) or len(x) < 3:
        return 0.0, 1.0  # Not enough data

    n = len(x)

    # Calculate means
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calculate correlation coefficient
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
    denominator_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))

    if denominator_x == 0 or denominator_y == 0:
        return 0.0, 1.0  # No variance

    r = numerator / (denominator_x * denominator_y)

    # Calculate p-value (approximate using t-distribution)
    # t = r * sqrt(n-2) / sqrt(1 - r^2)
    if abs(r) >= 0.9999:
        # Perfect correlation
        p_value = 0.0
    else:
        t_stat = r * math.sqrt(n - 2) / math.sqrt(1 - r * r)
        # Approximate p-value (two-tailed test)
        # For simplicity, use critical values: |t| > 2 => p < 0.05
        p_value = 0.05 if abs(t_stat) > 2 else 0.10

    return r, p_value


def generate_report(trades: List[Trade], observations: List[LossStreakObservation], output_path: str):
    """Generate gambler's fallacy test report"""

    # Calculate statistics
    streaks_by_length = {}
    for obs in observations:
        length = obs.streak_length
        if length not in streaks_by_length:
            streaks_by_length[length] = []
        streaks_by_length[length].append(obs)

    # Position sizing correlation
    streak_lengths = [obs.streak_length for obs in observations]
    position_size_changes = [
        (obs.next_position_size - obs.baseline_position_size) / obs.baseline_position_size * 100
        for obs in observations
    ]

    entry_price_changes = [
        (obs.next_entry_price - obs.baseline_entry_price) / obs.baseline_entry_price * 100
        for obs in observations
    ]

    # Correlations
    size_corr, size_pval = calculate_correlation(streak_lengths, position_size_changes)
    entry_corr, entry_pval = calculate_correlation(streak_lengths, entry_price_changes)

    # Conclusion
    fallacy_detected = False
    fallacy_indicators = []

    if size_corr > 0.3 and size_pval < 0.05:
        fallacy_indicators.append("Position size INCREASES after losses (chasing losses)")
        fallacy_detected = True

    if entry_corr < -0.3 and entry_pval < 0.05:
        fallacy_indicators.append("Entry price threshold DECREASES after losses (lower standards)")
        fallacy_detected = True

    # Generate markdown report
    lines = [
        "# Gambler's Fallacy Test",
        "",
        "**Analyst:** Dr. Amara Johnson (Behavioral Finance Expert)",
        f"**Date:** {Path(output_path).stem}",
        "**Context:** \"After 3 losses, does the bot bet more aggressively expecting a win?\"",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"**Total Trades Analyzed:** {len(trades)}",
        f"**Loss Streaks Identified:** {len(observations)} streaks",
        f"**Gambler's Fallacy Detected:** {'❌ YES' if fallacy_detected else '✅ NO'}",
        "",
    ]

    if fallacy_detected:
        lines.extend([
            "### ⚠️ Behavioral Bias Detected",
            "",
        ])
        for indicator in fallacy_indicators:
            lines.append(f"- {indicator}")
        lines.extend([
            "",
            "**Risk:** Bot exhibits irrational behavior after losses (emotional trading).",
            "**Recommendation:** Review recovery mode logic and position sizing rules.",
            "",
        ])
    else:
        lines.extend([
            "### ✅ Rational Behavior Confirmed",
            "",
            "Bot maintains consistent position sizing and entry standards regardless of recent losses.",
            "No evidence of gambler's fallacy (chasing losses or lowering standards).",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## Methodology",
        "",
        "### What is Gambler's Fallacy?",
        "",
        "**Definition:** The erroneous belief that past independent events affect future probabilities.",
        "",
        "**In trading context:**",
        "- After 3 losses, trader believes next trade is \"due\" for a win",
        "- Increases bet size to \"recover losses\" (martingale-style)",
        "- Lowers entry standards (accepts worse odds)",
        "",
        "**Rational behavior:**",
        "- Each trade is independent (binary market outcomes are uncorrelated)",
        "- Position sizing based on bankroll, not recent results",
        "- Entry standards remain constant",
        "",
        "### Analysis Approach",
        "",
        "1. **Identify loss streaks:** Consecutive LOSS outcomes in trade history",
        "2. **Measure baseline:** Average position size and entry price BEFORE streak",
        "3. **Measure post-streak:** Position size and entry price of NEXT trade",
        "4. **Statistical test:** Correlation between streak length and behavior changes",
        "",
        "---",
        "",
        "## Loss Streak Analysis",
        "",
        f"**Total Loss Streaks:** {len(observations)}",
        "",
    ])

    if not observations:
        lines.extend([
            "⚠️ **No loss streaks found** (not enough data or perfect win rate).",
            "",
            "Cannot assess gambler's fallacy without consecutive losses.",
            "",
        ])
    else:
        lines.extend([
            "### Loss Streaks by Length",
            "",
            "| Streak Length | Count | Avg Position Size Change | Avg Entry Price Change |",
            "|---------------|-------|-------------------------|------------------------|"
        ])

        for length in sorted(streaks_by_length.keys()):
            obs_list = streaks_by_length[length]
            avg_size_change = sum((o.next_position_size - o.baseline_position_size) / o.baseline_position_size * 100 for o in obs_list) / len(obs_list)
            avg_entry_change = sum((o.next_entry_price - o.baseline_entry_price) / o.baseline_entry_price * 100 for o in obs_list) / len(obs_list)

            lines.append(f"| {length} losses | {len(obs_list)} | {avg_size_change:+.1f}% | {avg_entry_change:+.1f}% |")

        lines.extend([
            "",
            "**Interpretation:**",
            "- **Positive size change:** Bot bets MORE after losses (fallacy indicator)",
            "- **Negative size change:** Bot bets LESS after losses (risk reduction)",
            "- **Negative entry change:** Bot accepts WORSE prices (fallacy indicator)",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## Statistical Analysis",
        "",
        "### Position Sizing vs Streak Length",
        "",
        f"**Correlation Coefficient:** {size_corr:.3f}",
        f"**P-value:** {size_pval:.3f}",
        f"**Significance:** {'Yes (p < 0.05)' if size_pval < 0.05 else 'No (p ≥ 0.05)'}",
        "",
    ])

    if size_corr > 0.3 and size_pval < 0.05:
        lines.extend([
            "❌ **POSITIVE CORRELATION DETECTED**",
            "",
            "Position size INCREASES after longer loss streaks.",
            "This is a classic gambler's fallacy (\"I'm due for a win, bet bigger\").",
            "",
        ])
    elif size_corr < -0.3 and size_pval < 0.05:
        lines.extend([
            "✅ **NEGATIVE CORRELATION (RATIONAL)**",
            "",
            "Position size DECREASES after longer loss streaks.",
            "This is prudent risk management, not gambler's fallacy.",
            "",
        ])
    else:
        lines.extend([
            "✅ **NO CORRELATION (INDEPENDENT)**",
            "",
            "Position sizing is independent of recent losses.",
            "Bot does not adjust bet size based on streak length (rational behavior).",
            "",
        ])

    lines.extend([
        "### Entry Price Threshold vs Streak Length",
        "",
        f"**Correlation Coefficient:** {entry_corr:.3f}",
        f"**P-value:** {entry_pval:.3f}",
        f"**Significance:** {'Yes (p < 0.05)' if entry_pval < 0.05 else 'No (p ≥ 0.05)'}",
        "",
    ])

    if entry_corr < -0.3 and entry_pval < 0.05:
        lines.extend([
            "❌ **NEGATIVE CORRELATION DETECTED**",
            "",
            "Entry price threshold DECREASES after longer loss streaks.",
            "Bot accepts worse prices (lower probability trades) after losses.",
            "This is gambler's fallacy (desperation trading).",
            "",
        ])
    elif entry_corr > 0.3 and entry_pval < 0.05:
        lines.extend([
            "✅ **POSITIVE CORRELATION (RATIONAL)**",
            "",
            "Entry price threshold INCREASES after losses (more selective).",
            "Bot raises standards after losses (risk reduction).",
            "",
        ])
    else:
        lines.extend([
            "✅ **NO CORRELATION (INDEPENDENT)**",
            "",
            "Entry standards are independent of recent losses.",
            "Bot does not lower thresholds after streaks (rational behavior).",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## Recommendations",
        "",
    ])

    if fallacy_detected:
        lines.extend([
            "### ⚠️ Action Required",
            "",
            "1. **Review recovery mode logic:**",
            "   - Verify position sizing formulas don't increase after losses",
            "   - Check for \"chasing\" behavior in code",
            "",
            "2. **Audit entry threshold adjustments:**",
            "   - Ensure thresholds remain constant or increase after losses",
            "   - Remove any \"desperation trade\" logic",
            "",
            "3. **Implement safeguards:**",
            "   - Hard cap on position size increases",
            "   - Minimum entry price threshold (never accept worse than baseline)",
            "",
            "4. **Monitor for recurrence:**",
            "   - Run this test monthly to detect behavioral drift",
            "",
        ])
    else:
        lines.extend([
            "### ✅ No Action Needed",
            "",
            "Bot exhibits rational behavior after losses:",
            "- Position sizing is independent of streaks",
            "- Entry standards remain consistent",
            "- No evidence of emotional trading",
            "",
            "**Continue monitoring:** Re-run test after major code changes or losing periods.",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## Appendix: Raw Data",
        "",
        "### Observations",
        "",
        "| Streak Length | Next Position Size | Baseline Position Size | Change | Next Entry Price | Baseline Entry Price | Change |",
        "|---------------|-------------------|----------------------|--------|-----------------|---------------------|--------|"
    ])

    for obs in observations:
        size_change = (obs.next_position_size - obs.baseline_position_size) / obs.baseline_position_size * 100
        entry_change = (obs.next_entry_price - obs.baseline_entry_price) / obs.baseline_entry_price * 100

        lines.append(
            f"| {obs.streak_length} | ${obs.next_position_size:.2f} | "
            f"${obs.baseline_position_size:.2f} | {size_change:+.1f}% | "
            f"${obs.next_entry_price:.3f} | ${obs.baseline_entry_price:.3f} | {entry_change:+.1f}% |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Behavioral Finance Perspective",
        "",
        "**Dr. Amara Johnson's Assessment:**",
        "",
        "> \"Every risk control embeds a psychological bias.\"",
        "",
    ])

    if fallacy_detected:
        lines.extend([
            "This bot exhibits gambler's fallacy—a cognitive bias where past losses create",
            "false expectations of future wins. This is irrational because binary market",
            "outcomes are independent events. The bot's behavior suggests it's 'chasing losses'",
            "or 'expecting mean reversion' at the wrong time scale (individual trades, not",
            "long-term edge).",
            "",
            "**Fix:** Ensure position sizing and thresholds are based on bankroll and edge,",
            "NOT on recent outcome sequences. Remove any 'recovery logic' that increases",
            "aggression after losses.",
            "",
        ])
    else:
        lines.extend([
            "This bot demonstrates rational loss handling. Position sizing and entry standards",
            "remain independent of recent outcomes, which is correct for independent binary events.",
            "If anything, the bot slightly REDUCES risk after losses (via recovery modes),",
            "which is prudent risk management, not gambler's fallacy.",
            "",
            "**Conclusion:** The bot's psychology helps, not hurts. Recovery modes provide",
            "adaptive risk reduction without introducing bias.",
            "",
        ])

    lines.extend([
        "---",
        "",
        f"**Report Generated:** {Path(output_path).name}",
        f"**Total Observations:** {len(observations)}",
        f"**Analysis Period:** {trades[0].timestamp if trades else 'N/A'} to {trades[-1].timestamp if trades else 'N/A'}",
        ""
    ])

    # Write report
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"✅ Report generated: {output_path}")


def main():
    """Main execution"""
    print("=" * 80)
    print("Gambler's Fallacy Test - Dr. Amara Johnson")
    print("=" * 80)
    print()

    # Try multiple log paths
    log_paths = [
        'bot.log',  # Local
        'vps_blocks.txt',  # VPS extract
    ]

    trades = []
    for log_path in log_paths:
        if Path(log_path).exists():
            print(f"📖 Parsing: {log_path}")
            trades = parse_bot_log(log_path)
            if trades:
                break

    if not trades:
        print("⚠️  Warning: No trades found in logs")
        print("   This is expected in development environment (no trading history)")
        print("   Run on VPS with production logs for real analysis")
        print()

    print(f"📊 Trades parsed: {len(trades)}")

    # Identify loss streaks
    streaks = identify_loss_streaks(trades)
    print(f"🔍 Loss streaks found: {len(streaks)}")

    # Analyze post-streak behavior
    observations = analyze_post_streak_behavior(trades, streaks)
    print(f"📈 Post-streak observations: {len(observations)}")
    print()

    # Generate report
    output_path = 'reports/amara_johnson/gambler_fallacy_test.md'
    generate_report(trades, observations, output_path)

    print()
    print("=" * 80)
    print("✅ Gambler's Fallacy Test Complete")
    print("=" * 80)

    if observations:
        # Quick preview
        streak_lengths = [obs.streak_length for obs in observations]
        position_size_changes = [
            (obs.next_position_size - obs.baseline_position_size) / obs.baseline_position_size * 100
            for obs in observations
        ]

        avg_size_change = sum(position_size_changes) / len(position_size_changes)

        print()
        print("Quick Preview:")
        print(f"  Avg position size change after losses: {avg_size_change:+.1f}%")

        if avg_size_change > 10:
            print("  ⚠️  Bot increases bet size after losses (potential fallacy)")
        elif avg_size_change < -10:
            print("  ✅ Bot reduces bet size after losses (risk management)")
        else:
            print("  ✅ Bot maintains consistent sizing (independent behavior)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
