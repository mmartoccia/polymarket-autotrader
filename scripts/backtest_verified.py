#!/usr/bin/env python3
"""
VERIFIED Backtest using ACTUAL data from logs.

CRITICAL FINDINGS FROM LOG VERIFICATION:
1. Confluence feature was NOT active during early trades (05:48-06:06)
   - First confluence log entry: 14:03:05
   - All early trades were made WITHOUT confluence checking

2. ACTUAL pattern accuracies from logs:
   - ETH Down @ 05:48: 73.9% (not 77%)
   - SOL Up @ 05:48: 78.0% (not 75%)
   - XRP Down @ 06:03: 73.9% (not 77%)
   - BTC Down @ 06:06: 74.0% (not 78%)
   - ETH Down @ 06:06: 74.0% (not 78%)

3. We DON'T KNOW what the confluence was for early trades
   - Cannot retroactively determine exchange agreement
   - The weighted scoring assumptions about confluence were GUESSES
"""

# VERIFIED ACTUAL TRADES FROM LOGS
ACTUAL_TRADES = [
    # Trade 1: ETH Down - WIN
    {
        "time": "05:48",
        "crypto": "ETH",
        "direction": "Down",
        "pattern": "All 3 first minutes DOWN",
        "accuracy": 0.739,  # VERIFIED from log
        "entry": 0.59,
        "amount": 4.49,
        "outcome": "WIN",
        "confluence": "UNKNOWN",  # Feature not deployed yet
    },
    # Trade 2: SOL Up - LOSS
    {
        "time": "05:48",
        "crypto": "SOL",
        "direction": "Up",
        "pattern": "All 3 first minutes UP",
        "accuracy": 0.780,  # VERIFIED from log
        "entry": 0.47,
        "amount": 4.90,
        "outcome": "LOSS",
        "confluence": "UNKNOWN",  # Feature not deployed yet
    },
    # Trade 3: XRP Down - WIN
    {
        "time": "06:03",
        "crypto": "XRP",
        "direction": "Down",
        "pattern": "All 3 first minutes DOWN",
        "accuracy": 0.739,  # VERIFIED from log
        "entry": 0.49,
        "amount": 4.49,
        "outcome": "WIN",
        "confluence": "UNKNOWN",  # Feature not deployed yet
    },
    # Trade 4: BTC Down - WIN
    {
        "time": "06:06",
        "crypto": "BTC",
        "direction": "Down",
        "pattern": "4/5 first minutes DOWN",
        "accuracy": 0.740,  # VERIFIED from log
        "entry": 0.68,
        "amount": 4.50,
        "outcome": "WIN",
        "confluence": "UNKNOWN",  # Feature not deployed yet
    },
    # Trade 5: ETH Down - WIN
    {
        "time": "06:06",
        "crypto": "ETH",
        "direction": "Down",
        "pattern": "4/5 first minutes DOWN",
        "accuracy": 0.740,  # VERIFIED from log
        "entry": 0.68,
        "amount": 4.50,
        "outcome": "WIN",
        "confluence": "UNKNOWN",  # Feature not deployed yet
    },
]


def calculate_pnl(amount: float, entry: float, outcome: str) -> float:
    """Calculate P&L for a trade."""
    if outcome == "WIN":
        shares = amount / entry
        payout = shares * 1.0
        return payout - amount
    elif outcome == "LOSS":
        return -amount
    return 0


def main():
    print("=" * 80)
    print("VERIFIED BACKTEST - Using Actual Log Data")
    print("=" * 80)
    print()

    print("⚠️  CRITICAL ISSUES WITH PREVIOUS ANALYSIS:")
    print("-" * 80)
    print("1. Confluence feature was NOT ACTIVE during these trades")
    print("   - First confluence log: 14:03:05 UTC")
    print("   - All 5 trades placed: 05:48-06:06 UTC")
    print("   - We cannot know what confluence would have been")
    print()
    print("2. Pattern accuracies were WRONG in previous analysis:")
    print("   - Used: 77%, 75%, 77%, 78%, 78%")
    print("   - Actual: 73.9%, 78.0%, 73.9%, 74.0%, 74.0%")
    print()
    print("3. The 'weighted would skip SOL Up' claim was based on GUESSED confluence")
    print("   - We assumed SOL Up had 1/3 confluence")
    print("   - We have NO DATA to support this")
    print()
    print("-" * 80)
    print()

    print("VERIFIED ACTUAL RESULTS:")
    print("=" * 80)
    print()

    total_wagered = 0
    total_pnl = 0
    wins = 0
    losses = 0

    print(f"{'Trade':<15} {'Pattern':<30} {'Acc':<8} {'Entry':<8} {'Amount':<8} {'Outcome':<8} {'P&L':<10}")
    print("-" * 100)

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
        print(f"{trade_str:<15} {trade['pattern']:<30} {trade['accuracy']:.1%}    ${trade['entry']:<7.2f} ${trade['amount']:<7.2f} {trade['outcome']:<8} {pnl_str:<10}")

    print("-" * 100)
    print(f"{'TOTAL':<15} {'':<30} {'':<8} {'':<8} ${total_wagered:<7.2f} {wins}W/{losses}L  ${total_pnl:+.2f}")
    print()

    starting = 64.73
    ending = starting + total_pnl
    print(f"Starting Balance: ${starting:.2f}")
    print(f"Ending Balance:   ${ending:.2f}")
    print(f"Win Rate:         {wins/(wins+losses)*100:.1f}%")
    print(f"ROI:              {total_pnl/total_wagered*100:.1f}%")

    print()
    print("=" * 80)
    print("WHAT WE CAN ACTUALLY CONCLUDE")
    print("=" * 80)
    print()
    print("✓ The actual trades made +$7.13 profit (verified)")
    print("✓ 4 wins, 1 loss (80% win rate)")
    print("✓ SOL Up was the only loss")
    print()
    print("✗ We CANNOT say weighted scoring would have skipped SOL Up")
    print("  - We don't know what the confluence was")
    print("  - SOL Up had the HIGHEST pattern accuracy (78.0%)")
    print("  - SOL Up had a GREAT entry price ($0.47)")
    print()
    print("HONEST ASSESSMENT OF SOL Up TRADE:")
    print("-" * 80)
    sol_trade = ACTUAL_TRADES[1]
    edge = sol_trade["accuracy"] - sol_trade["entry"]
    print(f"  Pattern Accuracy: {sol_trade['accuracy']:.1%} (highest of all 5 trades!)")
    print(f"  Entry Price:      ${sol_trade['entry']:.2f} (cheapest entry!)")
    print(f"  Edge:             {edge:.1%} (31% edge - excellent!)")
    print(f"  Confluence:       UNKNOWN (feature not deployed)")
    print()
    print("  By pattern + entry alone, SOL Up looked like the BEST trade!")
    print("  It lost because the market reversed, not because signals were bad.")
    print()

    print("=" * 80)
    print("WHAT WEIGHTED SCORING COULD HELP WITH (GOING FORWARD)")
    print("=" * 80)
    print()
    print("Now that confluence IS deployed, weighted scoring could help by:")
    print()
    print("1. Using confluence as a strong signal filter")
    print("   - We saw 0/3 confluence correctly blocking trades at 14:03+")
    print("   - This is a real improvement")
    print()
    print("2. Sizing positions based on confidence")
    print("   - Trade 4 & 5 (BTC/ETH @ $0.68) had thin edge (6%)")
    print("   - Could reduce size on expensive entries")
    print()
    print("3. BUT we need MORE DATA to validate")
    print("   - Need to track confluence on actual trades")
    print("   - Need to see if low confluence = losses")
    print("   - Current sample size is too small")
    print()

    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()
    print("Before implementing weighted scoring:")
    print()
    print("1. Run the current bot WITH confluence logging for 24-48 hours")
    print("2. Collect data on:")
    print("   - What confluence levels lead to wins vs losses?")
    print("   - Does expensive entry + high confluence still work?")
    print("   - Does cheap entry + low confluence lose?")
    print()
    print("3. THEN we can make data-driven decisions about:")
    print("   - Confluence thresholds")
    print("   - Position sizing tiers")
    print("   - Entry price flexibility")
    print()
    print("The backtest was FLAWED because we guessed at confluence values.")
    print("We need REAL confluence data before making changes.")


if __name__ == "__main__":
    main()
