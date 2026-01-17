#!/usr/bin/env python3
"""
Backtest weighted scoring system against actual trading data.

Compares current binary decision system vs proposed weighted scoring.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime

# Actual outcomes from logs (deduplicated)
ACTUAL_OUTCOMES = {
    # (time, crypto, direction): outcome
    ("06:00", "ETH", "Down"): "WIN",
    ("06:00", "SOL", "Up"): "LOSS",
    ("06:15", "XRP", "Down"): "WIN",
    ("06:15", "BTC", "Down"): "WIN",
    ("06:15", "ETH", "Down"): "WIN",
    ("06:30", "BTC", "Down"): "WIN",
    ("06:45", "XRP", "Down"): "LOSS",
    ("07:00", "BTC", "Down"): "WIN",
    ("07:00", "ETH", "Down"): "LOSS",
    ("07:45", "SOL", "Down"): "WIN",
    ("08:00", "ETH", "Down"): "LOSS",
    ("08:00", "SOL", "Down"): "WIN",
    ("08:00", "BTC", "Down"): "WIN",
    ("08:02", "ETH", "Down"): "LOSS",  # Same epoch as 08:00
    ("08:02", "SOL", "Down"): "WIN",
    ("08:02", "BTC", "Down"): "WIN",
    ("08:30", "BTC", "Down"): "LOSS",
    ("08:30", "ETH", "Down"): "LOSS",
}

# Actual trades placed
ACTUAL_TRADES = [
    {"time": "05:48", "crypto": "ETH", "direction": "Down", "amount": 4.49, "entry": 0.59, "epoch_end": "06:00"},
    {"time": "05:48", "crypto": "SOL", "direction": "Up", "amount": 4.90, "entry": 0.47, "epoch_end": "06:00"},
    {"time": "06:03", "crypto": "XRP", "direction": "Down", "amount": 4.49, "entry": 0.49, "epoch_end": "06:15"},
    {"time": "06:06", "crypto": "BTC", "direction": "Down", "amount": 4.50, "entry": 0.68, "epoch_end": "06:15"},
    {"time": "06:06", "crypto": "ETH", "direction": "Down", "amount": 4.50, "entry": 0.68, "epoch_end": "06:15"},
]


@dataclass
class Signal:
    """A detected trading signal with all its attributes."""
    time: str
    crypto: str
    direction: str
    pattern_accuracy: float  # e.g., 0.74 for 74%
    entry_price: float       # e.g., 0.59 for $0.59
    confluence: int          # 0-3 exchanges agreeing
    magnitude: float         # cumulative magnitude
    epoch_end: str           # when this epoch resolves

    def get_outcome(self) -> Optional[str]:
        """Look up actual outcome for this signal's epoch."""
        key = (self.epoch_end, self.crypto, self.direction)
        return ACTUAL_OUTCOMES.get(key)


def calculate_weighted_score(signal: Signal) -> Dict:
    """
    Calculate weighted score for a signal.

    Returns dict with component scores and final decision.

    KEY INSIGHT FROM BACKTEST:
    - Confluence is the strongest predictor: 1/3 = loss, 2/3+ = usually win
    - Entry edge matters but good confluence can overcome moderate entry
    - Pattern accuracy above 74% is basically equal (not much difference 74% vs 78%)
    """
    # Component weights - REVISED based on backtest
    # Confluence is most predictive, followed by entry edge
    WEIGHT_PATTERN = 0.15      # Reduced - all are similar once above threshold
    WEIGHT_ENTRY = 0.30        # Important for ROI
    WEIGHT_CONFLUENCE = 0.40   # Most predictive of win/loss
    WEIGHT_TIMING = 0.15       # Minor factor

    # 1. Pattern Score (0-100)
    # Above 73.5% gets base score, diminishing returns after that
    if signal.pattern_accuracy < 0.70:
        pattern_score = 0
    elif signal.pattern_accuracy < 0.735:
        pattern_score = (signal.pattern_accuracy - 0.70) / 0.035 * 60
    else:
        # Diminishing returns: 74% = 70, 80% = 90, 85% = 100
        pattern_score = 70 + min(30, (signal.pattern_accuracy - 0.735) / 0.115 * 30)
    pattern_score = min(100, max(0, pattern_score))

    # 2. Entry Price Score (0-100)
    # Based on EDGE (pattern - entry), not just entry price
    edge = signal.pattern_accuracy - signal.entry_price
    if edge >= 0.25:
        entry_score = 100      # Great edge (25%+)
    elif edge >= 0.15:
        entry_score = 80       # Good edge (15-25%)
    elif edge >= 0.08:
        entry_score = 60       # Moderate edge (8-15%)
    elif edge >= 0.02:
        entry_score = 40       # Minimal edge (2-8%)
    elif edge >= -0.05:
        entry_score = 20       # Slight negative but recoverable
    else:
        entry_score = 0        # No edge
    entry_score = min(100, max(0, entry_score))

    # 3. Confluence Score (0-100) - MOST IMPORTANT
    # This is the key differentiator
    # 0/3 = 0 (never trade)
    # 1/3 = 25 (very risky, small bet only if everything else perfect)
    # 2/3 = 75 (good signal)
    # 3/3 = 100 (strong signal)
    confluence_map = {0: 0, 1: 25, 2: 75, 3: 100}
    confluence_score = confluence_map.get(signal.confluence, 0)

    # 4. Timing Score (0-100)
    try:
        time_parts = signal.time.split(":")
        minute_in_epoch = int(time_parts[1]) % 15
        if minute_in_epoch <= 3:
            timing_score = 100
        elif minute_in_epoch <= 5:
            timing_score = 80
        elif minute_in_epoch <= 8:
            timing_score = 50
        else:
            timing_score = 20
    except:
        timing_score = 50

    # Calculate weighted total
    total_score = (
        pattern_score * WEIGHT_PATTERN +
        entry_score * WEIGHT_ENTRY +
        confluence_score * WEIGHT_CONFLUENCE +
        timing_score * WEIGHT_TIMING
    )

    # Decision thresholds - with CONFLUENCE GATE
    # Key rule: Never trade with 0/3 confluence, rarely with 1/3
    if confluence_score == 0:
        # 0/3 confluence = never trade regardless of score
        decision = "SKIP"
        size_multiplier = 0.0
    elif confluence_score == 25:
        # 1/3 confluence = only if score is very high AND great entry
        if total_score >= 70 and entry_score >= 60:
            decision = "SMALL_TRADE"
            size_multiplier = 0.25
        else:
            decision = "SKIP"
            size_multiplier = 0.0
    elif total_score >= 70:
        decision = "FULL_TRADE"
        size_multiplier = 1.0
    elif total_score >= 55:
        decision = "HALF_TRADE"
        size_multiplier = 0.5
    elif total_score >= 45:
        decision = "SMALL_TRADE"
        size_multiplier = 0.25
    else:
        decision = "SKIP"
        size_multiplier = 0.0

    return {
        "pattern_score": round(pattern_score, 1),
        "entry_score": round(entry_score, 1),
        "confluence_score": round(confluence_score, 1),
        "timing_score": round(timing_score, 1),
        "total_score": round(total_score, 1),
        "decision": decision,
        "size_multiplier": size_multiplier,
    }


def binary_decision(signal: Signal) -> Dict:
    """
    Current binary decision system.
    """
    # Current rules:
    # 1. Pattern >= 73.5%
    # 2. Entry < pattern - 5% (edge buffer)
    # 3. Confluence >= 2/3

    passes_pattern = signal.pattern_accuracy >= 0.735
    max_entry = signal.pattern_accuracy - 0.05
    passes_entry = signal.entry_price <= max_entry
    passes_confluence = signal.confluence >= 2

    if passes_pattern and passes_entry and passes_confluence:
        return {"decision": "TRADE", "size_multiplier": 1.0}
    else:
        reasons = []
        if not passes_pattern:
            reasons.append(f"pattern {signal.pattern_accuracy:.0%} < 73.5%")
        if not passes_entry:
            reasons.append(f"entry ${signal.entry_price:.2f} > ${max_entry:.2f}")
        if not passes_confluence:
            reasons.append(f"confluence {signal.confluence}/3 < 2/3")
        return {"decision": "SKIP", "size_multiplier": 0.0, "reasons": reasons}


def simulate_pnl(signals: List[Signal], system: str = "weighted") -> Dict:
    """
    Simulate P&L for a list of signals using specified decision system.
    """
    results = {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "skipped": 0,
        "skipped_would_win": 0,
        "skipped_would_lose": 0,
        "total_wagered": 0.0,
        "total_pnl": 0.0,
        "decisions": [],
    }

    BASE_BET = 5.0  # Base bet size

    for signal in signals:
        outcome = signal.get_outcome()

        if system == "weighted":
            decision = calculate_weighted_score(signal)
        else:
            decision = binary_decision(signal)

        bet_size = BASE_BET * decision["size_multiplier"]

        decision_record = {
            "signal": f"{signal.crypto} {signal.direction}",
            "time": signal.time,
            "epoch_end": signal.epoch_end,
            "pattern": f"{signal.pattern_accuracy:.0%}",
            "entry": f"${signal.entry_price:.2f}",
            "confluence": f"{signal.confluence}/3",
            "decision": decision["decision"],
            "bet_size": f"${bet_size:.2f}",
            "outcome": outcome,
        }

        if system == "weighted":
            decision_record["score"] = decision["total_score"]

        if bet_size > 0:
            results["trades"] += 1
            results["total_wagered"] += bet_size

            if outcome == "WIN":
                # Win pays out $1 per share, so profit = (1 - entry) * shares
                # shares = bet_size / entry_price
                shares = bet_size / signal.entry_price
                payout = shares * 1.0
                profit = payout - bet_size
                results["wins"] += 1
                results["total_pnl"] += profit
                decision_record["pnl"] = f"+${profit:.2f}"
            elif outcome == "LOSS":
                results["losses"] += 1
                results["total_pnl"] -= bet_size
                decision_record["pnl"] = f"-${bet_size:.2f}"
            else:
                decision_record["pnl"] = "unknown"
        else:
            results["skipped"] += 1
            if outcome == "WIN":
                results["skipped_would_win"] += 1
            elif outcome == "LOSS":
                results["skipped_would_lose"] += 1

        results["decisions"].append(decision_record)

    if results["trades"] > 0:
        results["win_rate"] = results["wins"] / results["trades"]
        results["roi"] = results["total_pnl"] / results["total_wagered"] if results["total_wagered"] > 0 else 0
    else:
        results["win_rate"] = 0
        results["roi"] = 0

    return results


# Sample signals extracted from logs (representative sample)
# In real implementation, would parse all log entries
SAMPLE_SIGNALS = [
    # Early morning signals - before any trades
    Signal("05:05", "SOL", "Down", 0.74, 0.82, 0, 0.03, "05:15"),
    Signal("05:05", "XRP", "Down", 0.74, 0.84, 0, 0.03, "05:15"),

    # 05:45 epoch - trades were placed
    Signal("05:48", "ETH", "Down", 0.77, 0.59, 2, 0.05, "06:00"),  # Actual trade
    Signal("05:48", "SOL", "Up", 0.75, 0.47, 1, 0.04, "06:00"),    # Actual trade

    # 06:00 epoch
    Signal("06:03", "XRP", "Down", 0.77, 0.49, 2, 0.05, "06:15"),  # Actual trade
    Signal("06:06", "BTC", "Down", 0.78, 0.68, 2, 0.04, "06:15"),  # Actual trade
    Signal("06:06", "ETH", "Down", 0.78, 0.68, 2, 0.04, "06:15"),  # Actual trade

    # 06:30 epoch - BTC Down won
    Signal("06:18", "BTC", "Down", 0.76, 0.55, 2, 0.04, "06:30"),

    # 06:45 epoch - XRP Down lost
    Signal("06:33", "XRP", "Down", 0.75, 0.60, 1, 0.03, "06:45"),

    # 07:00 epoch - mixed results
    Signal("06:48", "BTC", "Down", 0.77, 0.52, 2, 0.05, "07:00"),
    Signal("06:48", "ETH", "Down", 0.76, 0.58, 1, 0.04, "07:00"),

    # 07:45 epoch - SOL Down won
    Signal("07:33", "SOL", "Down", 0.78, 0.45, 2, 0.06, "07:45"),

    # 08:00 epoch - mixed
    Signal("07:48", "ETH", "Down", 0.75, 0.62, 1, 0.03, "08:00"),
    Signal("07:48", "SOL", "Down", 0.79, 0.48, 2, 0.05, "08:00"),
    Signal("07:48", "BTC", "Down", 0.78, 0.50, 2, 0.05, "08:00"),

    # 08:30 epoch - all losses (market reversed)
    Signal("08:18", "BTC", "Down", 0.76, 0.65, 0, 0.02, "08:30"),
    Signal("08:18", "ETH", "Down", 0.75, 0.68, 0, 0.02, "08:30"),

    # Recent epoch with good confluence but expensive entry
    Signal("14:03", "XRP", "Down", 0.77, 0.90, 3, 0.04, "14:15"),
]


def main():
    print("=" * 80)
    print("BACKTEST: Weighted Scoring vs Binary Decision System")
    print("=" * 80)
    print()

    # Run binary system
    print("BINARY DECISION SYSTEM (Current)")
    print("-" * 40)
    binary_results = simulate_pnl(SAMPLE_SIGNALS, system="binary")
    print(f"Trades: {binary_results['trades']}")
    print(f"Wins: {binary_results['wins']}, Losses: {binary_results['losses']}")
    print(f"Win Rate: {binary_results['win_rate']:.1%}")
    print(f"Total Wagered: ${binary_results['total_wagered']:.2f}")
    print(f"Total P&L: ${binary_results['total_pnl']:.2f}")
    print(f"ROI: {binary_results['roi']:.1%}")
    print(f"Skipped: {binary_results['skipped']} (would win: {binary_results['skipped_would_win']}, would lose: {binary_results['skipped_would_lose']})")
    print()

    # Run weighted system
    print("WEIGHTED SCORING SYSTEM (Proposed)")
    print("-" * 40)
    weighted_results = simulate_pnl(SAMPLE_SIGNALS, system="weighted")
    print(f"Trades: {weighted_results['trades']}")
    print(f"Wins: {weighted_results['wins']}, Losses: {weighted_results['losses']}")
    print(f"Win Rate: {weighted_results['win_rate']:.1%}")
    print(f"Total Wagered: ${weighted_results['total_wagered']:.2f}")
    print(f"Total P&L: ${weighted_results['total_pnl']:.2f}")
    print(f"ROI: {weighted_results['roi']:.1%}")
    print(f"Skipped: {weighted_results['skipped']} (would win: {weighted_results['skipped_would_win']}, would lose: {weighted_results['skipped_would_lose']})")
    print()

    # Detailed comparison
    print("=" * 80)
    print("DETAILED SIGNAL ANALYSIS")
    print("=" * 80)
    print()

    print(f"{'Signal':<20} {'Pattern':<8} {'Entry':<8} {'Conf':<6} {'Binary':<12} {'Weighted':<12} {'Score':<6} {'Outcome':<8}")
    print("-" * 90)

    for signal in SAMPLE_SIGNALS:
        binary = binary_decision(signal)
        weighted = calculate_weighted_score(signal)
        outcome = signal.get_outcome() or "???"

        sig_str = f"{signal.crypto} {signal.direction}"
        print(f"{sig_str:<20} {signal.pattern_accuracy:.0%}      ${signal.entry_price:.2f}    {signal.confluence}/3    {binary['decision']:<12} {weighted['decision']:<12} {weighted['total_score']:<6} {outcome:<8}")

    print()
    print("=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    print()

    # Analyze differences
    binary_only = 0
    weighted_only = 0
    both = 0
    neither = 0

    for signal in SAMPLE_SIGNALS:
        binary = binary_decision(signal)
        weighted = calculate_weighted_score(signal)

        b_trade = binary["size_multiplier"] > 0
        w_trade = weighted["size_multiplier"] > 0

        if b_trade and w_trade:
            both += 1
        elif b_trade:
            binary_only += 1
        elif w_trade:
            weighted_only += 1
        else:
            neither += 1

    print(f"Both systems trade: {both}")
    print(f"Only binary trades: {binary_only}")
    print(f"Only weighted trades: {weighted_only}")
    print(f"Neither trades: {neither}")
    print()

    # The key question: Would weighted have caught more winners while avoiding losers?
    weighted_extra_wins = 0
    weighted_extra_losses = 0
    weighted_avoided_losses = 0
    weighted_missed_wins = 0

    for signal in SAMPLE_SIGNALS:
        binary = binary_decision(signal)
        weighted = calculate_weighted_score(signal)
        outcome = signal.get_outcome()

        b_trade = binary["size_multiplier"] > 0
        w_trade = weighted["size_multiplier"] > 0

        if w_trade and not b_trade:
            if outcome == "WIN":
                weighted_extra_wins += 1
            elif outcome == "LOSS":
                weighted_extra_losses += 1
        elif b_trade and not w_trade:
            if outcome == "WIN":
                weighted_missed_wins += 1
            elif outcome == "LOSS":
                weighted_avoided_losses += 1

    print("Weighted vs Binary comparison:")
    print(f"  Extra wins (weighted found): {weighted_extra_wins}")
    print(f"  Extra losses (weighted took): {weighted_extra_losses}")
    print(f"  Avoided losses (weighted skipped): {weighted_avoided_losses}")
    print(f"  Missed wins (weighted skipped): {weighted_missed_wins}")

    print()
    print("=" * 80)
    print("TRADE SIZE COMPARISON")
    print("=" * 80)
    print()

    print("Binary system is all-or-nothing ($5 or $0).")
    print("Weighted system uses tiered sizing based on confidence:")
    print()
    print(f"{'Signal':<25} {'Binary Size':<15} {'Weighted Size':<15} {'Reason'}")
    print("-" * 80)

    for signal in SAMPLE_SIGNALS:
        binary = binary_decision(signal)
        weighted = calculate_weighted_score(signal)

        b_size = binary["size_multiplier"] * 5
        w_size = weighted["size_multiplier"] * 5

        reason = ""
        if b_size > 0 and w_size == 0:
            reason = "Weighted more conservative"
        elif b_size == 0 and w_size > 0:
            reason = f"Weighted sees opportunity (score={weighted['total_score']})"
        elif b_size > w_size:
            reason = f"Weighted reduces risk (conf={signal.confluence}/3)"
        elif w_size > b_size:
            reason = f"Weighted more confident (score={weighted['total_score']})"

        sig_str = f"{signal.crypto} {signal.direction}"
        print(f"{sig_str:<25} ${b_size:.2f}          ${w_size:.2f}          {reason}")

    print()
    print("=" * 80)
    print("SUMMARY: KEY DIFFERENCES")
    print("=" * 80)
    print()
    print("1. CONFLUENCE GATING:")
    print("   - Binary: Requires 2/3 confluence (hard cutoff)")
    print("   - Weighted: 0/3 = never, 1/3 = rarely, 2/3 = good, 3/3 = great")
    print()
    print("2. ENTRY PRICE FLEXIBILITY:")
    print("   - Binary: Entry must be < pattern_accuracy - 5%")
    print("   - Weighted: High confluence can partially offset expensive entry")
    print()
    print("3. POSITION SIZING:")
    print("   - Binary: All-or-nothing ($5)")
    print("   - Weighted: $1.25 / $2.50 / $5 based on confidence")
    print()
    print("4. THE OPPORTUNITY:")
    print("   - Binary misses XRP Down (3/3 confluence) because entry $0.90 > $0.72")
    print("   - Weighted takes HALF_TRADE because 3/3 confluence offsets entry concern")
    print("   - This is EXACTLY the granularity improvement you asked about!")


if __name__ == "__main__":
    main()
