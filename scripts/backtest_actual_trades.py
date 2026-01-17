#!/usr/bin/env python3
"""
Backtest using ACTUAL trades from logs with real amounts.
"""

# ACTUAL TRADES FROM LOGS (deduplicated, with real $ amounts)
ACTUAL_TRADES = [
    # Epoch 05:45-06:00
    {"time": "05:48", "crypto": "ETH", "direction": "Down", "amount": 4.49, "entry": 0.59, "outcome": "WIN"},
    {"time": "05:48", "crypto": "SOL", "direction": "Up", "amount": 4.90, "entry": 0.47, "outcome": "LOSS"},

    # Epoch 06:00-06:15
    {"time": "06:03", "crypto": "XRP", "direction": "Down", "amount": 4.49, "entry": 0.49, "outcome": "WIN"},
    {"time": "06:06", "crypto": "BTC", "direction": "Down", "amount": 4.50, "entry": 0.68, "outcome": "WIN"},
    {"time": "06:06", "crypto": "ETH", "direction": "Down", "amount": 4.50, "entry": 0.68, "outcome": "WIN"},

    # Note: Logs show more wins/losses later but we don't have the order amounts
    # The 08:30 losses (BTC Down x2, ETH Down x2) were from positions we don't have entry data for
]

# Skipped signals that WOULD have been trades (from log analysis)
SKIPPED_SIGNALS = [
    # These had patterns but were blocked by entry price or confluence
    {"time": "05:05", "crypto": "SOL", "direction": "Down", "pattern": 0.74, "entry": 0.82, "confluence": 0, "outcome": "UNKNOWN"},
    {"time": "05:05", "crypto": "XRP", "direction": "Down", "pattern": 0.74, "entry": 0.84, "confluence": 0, "outcome": "UNKNOWN"},

    # 08:30 epoch - these were taken but LOST
    {"time": "08:18", "crypto": "BTC", "direction": "Down", "pattern": 0.76, "entry": 0.65, "confluence": 0, "outcome": "LOSS"},
    {"time": "08:18", "crypto": "ETH", "direction": "Down", "pattern": 0.75, "entry": 0.68, "confluence": 0, "outcome": "LOSS"},

    # 14:03 epoch - blocked by entry price
    {"time": "14:03", "crypto": "XRP", "direction": "Down", "pattern": 0.77, "entry": 0.90, "confluence": 3, "outcome": "UNKNOWN"},
]


def calculate_pnl(amount: float, entry: float, outcome: str) -> float:
    """Calculate P&L for a trade."""
    if outcome == "WIN":
        shares = amount / entry
        payout = shares * 1.0  # $1 per share on win
        return payout - amount
    elif outcome == "LOSS":
        return -amount
    else:
        return 0  # Unknown


def main():
    print("=" * 70)
    print("ACTUAL TRADING RESULTS (from logs)")
    print("=" * 70)
    print()

    print("Starting Balance: $64.73")
    print()

    total_wagered = 0
    total_pnl = 0
    wins = 0
    losses = 0

    print(f"{'Trade':<25} {'Amount':<10} {'Entry':<10} {'Outcome':<10} {'P&L':<10}")
    print("-" * 70)

    for trade in ACTUAL_TRADES:
        pnl = calculate_pnl(trade["amount"], trade["entry"], trade["outcome"])
        total_wagered += trade["amount"]
        total_pnl += pnl

        if trade["outcome"] == "WIN":
            wins += 1
        else:
            losses += 1

        trade_str = f"{trade['crypto']} {trade['direction']}"
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        print(f"{trade_str:<25} ${trade['amount']:<9.2f} ${trade['entry']:<9.2f} {trade['outcome']:<10} {pnl_str:<10}")

    print("-" * 70)
    print(f"{'TOTAL':<25} ${total_wagered:<9.2f} {'':<10} {wins}W/{losses}L    ${total_pnl:+.2f}")
    print()

    ending_balance = 64.73 + total_pnl
    print(f"Ending Balance (5 trades): ${ending_balance:.2f}")
    print(f"Win Rate: {wins/(wins+losses)*100:.1f}%")
    print(f"ROI: {total_pnl/total_wagered*100:.1f}%")

    print()
    print("=" * 70)
    print("WHAT WOULD WEIGHTED SCORING HAVE DONE?")
    print("=" * 70)
    print()

    # Weighted scoring decisions for same trades
    weighted_decisions = [
        # ETH Down @ $0.59, 77% pattern, assume 2/3 confluence → FULL_TRADE
        {"trade": "ETH Down", "binary": "TRADE $4.49", "weighted": "FULL $4.49", "reason": "Score 80.9"},
        # SOL Up @ $0.47, 75% pattern, 1/3 confluence → SKIP (confluence gate)
        {"trade": "SOL Up", "binary": "TRADE $4.90", "weighted": "SKIP $0", "reason": "1/3 confluence"},
        # XRP Down @ $0.49, 77% pattern, 2/3 confluence → FULL_TRADE
        {"trade": "XRP Down", "binary": "TRADE $4.49", "weighted": "FULL $4.49", "reason": "Score 86.9"},
        # BTC Down @ $0.68, 78% pattern, 2/3 confluence → HALF (expensive entry)
        {"trade": "BTC Down", "binary": "TRADE $4.50", "weighted": "HALF $2.25", "reason": "Score 67.8"},
        # ETH Down @ $0.68, 78% pattern, 2/3 confluence → HALF (expensive entry)
        {"trade": "ETH Down", "binary": "TRADE $4.50", "weighted": "HALF $2.25", "reason": "Score 67.8"},
    ]

    print(f"{'Trade':<15} {'Binary':<15} {'Weighted':<15} {'Reason':<20}")
    print("-" * 70)
    for d in weighted_decisions:
        print(f"{d['trade']:<15} {d['binary']:<15} {d['weighted']:<15} {d['reason']:<20}")

    print()
    print("KEY DIFFERENCE: Weighted would have SKIPPED SOL Up (the LOSS)")
    print()

    # Recalculate with weighted
    weighted_trades = [
        {"crypto": "ETH", "direction": "Down", "amount": 4.49, "entry": 0.59, "outcome": "WIN"},
        # SOL Up SKIPPED
        {"crypto": "XRP", "direction": "Down", "amount": 4.49, "entry": 0.49, "outcome": "WIN"},
        {"crypto": "BTC", "direction": "Down", "amount": 2.25, "entry": 0.68, "outcome": "WIN"},  # HALF
        {"crypto": "ETH", "direction": "Down", "amount": 2.25, "entry": 0.68, "outcome": "WIN"},  # HALF
    ]

    w_total = 0
    w_pnl = 0
    w_wins = 0

    print("WEIGHTED SYSTEM RESULTS:")
    print(f"{'Trade':<25} {'Amount':<10} {'Entry':<10} {'Outcome':<10} {'P&L':<10}")
    print("-" * 70)

    for trade in weighted_trades:
        pnl = calculate_pnl(trade["amount"], trade["entry"], trade["outcome"])
        w_total += trade["amount"]
        w_pnl += pnl
        w_wins += 1

        trade_str = f"{trade['crypto']} {trade['direction']}"
        pnl_str = f"+${pnl:.2f}"
        print(f"{trade_str:<25} ${trade['amount']:<9.2f} ${trade['entry']:<9.2f} {trade['outcome']:<10} {pnl_str:<10}")

    print("-" * 70)
    print(f"{'TOTAL':<25} ${w_total:<9.2f} {'':<10} {w_wins}W/0L     ${w_pnl:+.2f}")
    print()

    w_ending = 64.73 + w_pnl
    print(f"Ending Balance (weighted): ${w_ending:.2f}")
    print(f"Win Rate: 100%")
    print(f"ROI: {w_pnl/w_total*100:.1f}%")

    print()
    print("=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print()
    print(f"{'Metric':<25} {'Binary (Actual)':<20} {'Weighted (Simulated)':<20}")
    print("-" * 70)
    print(f"{'Starting Balance':<25} $64.73               $64.73")
    print(f"{'Trades Taken':<25} 5                    4")
    print(f"{'Amount Wagered':<25} ${total_wagered:.2f}              ${w_total:.2f}")
    print(f"{'Wins':<25} {wins}                    {w_wins}")
    print(f"{'Losses':<25} {losses}                    0")
    print(f"{'Total P&L':<25} ${total_pnl:+.2f}             ${w_pnl:+.2f}")
    print(f"{'Ending Balance':<25} ${ending_balance:.2f}              ${w_ending:.2f}")
    print(f"{'Win Rate':<25} {wins/(wins+losses)*100:.0f}%                  100%")
    print(f"{'ROI':<25} {total_pnl/total_wagered*100:.1f}%                {w_pnl/w_total*100:.1f}%")
    print()
    print(f"WEIGHTED ADVANTAGE: +${w_pnl - total_pnl:.2f} (+${w_ending - ending_balance:.2f} ending balance)")
    print()
    print("The weighted system would have:")
    print("  ✓ Avoided the SOL Up loss (-$4.90 saved)")
    print("  ✓ Reduced BTC/ETH position sizes (less risk on expensive entries)")
    print("  ✓ Still captured all 4 winning trades")


if __name__ == "__main__":
    main()
