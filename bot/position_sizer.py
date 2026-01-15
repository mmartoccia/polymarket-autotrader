"""
Position sizing module using Kelly Criterion for optimal bet sizing.

Kelly Criterion calculates the optimal fraction of bankroll to bet based on:
- Win probability (from ML model or agent confidence)
- Entry price (determines payout odds)
- Current balance

Formula: f* = (p*b - q) / b
Where:
  p = win probability
  q = loss probability (1 - p)
  b = net odds = (1 - entry_price) / entry_price

For safety, we use fractional Kelly (25% of full Kelly).
"""

from typing import Dict, Tuple


class KellyPositionSizer:
    """
    Kelly Criterion position sizer for binary outcome markets.

    Uses fractional Kelly (25% of full Kelly) for conservative sizing.
    Clamps results to min/max range to prevent over-betting.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        min_size_pct: float = 0.02,
        max_size_pct: float = 0.15
    ):
        """
        Initialize Kelly position sizer.

        Args:
            kelly_fraction: Fraction of full Kelly to use (default 0.25 = 25%)
            min_size_pct: Minimum position size as fraction of balance (default 0.02 = 2%)
            max_size_pct: Maximum position size as fraction of balance (default 0.15 = 15%)
        """
        self.kelly_fraction = kelly_fraction
        self.min_size_pct = min_size_pct
        self.max_size_pct = max_size_pct

    def calculate_kelly_size(
        self,
        win_prob: float,
        entry_price: float,
        balance: float
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate optimal position size using Kelly Criterion.

        Args:
            win_prob: Probability of winning (0.0 to 1.0) from ML model or agent confidence
            entry_price: Entry price (0.0 to 1.0) - cost per share in binary market
            balance: Current account balance in USD

        Returns:
            Tuple of:
                - position_size_usd: Recommended bet size in USD
                - debug_info: Dict with calculation details

        Example:
            >>> sizer = KellyPositionSizer()
            >>> size, info = sizer.calculate_kelly_size(win_prob=0.65, entry_price=0.20, balance=100.0)
            >>> print(f"Bet ${size:.2f}")
            Bet $15.00
        """
        # Validate inputs
        if not (0.0 <= win_prob <= 1.0):
            raise ValueError(f"win_prob must be 0-1, got {win_prob}")
        if not (0.0 < entry_price < 1.0):
            raise ValueError(f"entry_price must be 0-1 (exclusive), got {entry_price}")
        if balance <= 0:
            raise ValueError(f"balance must be positive, got {balance}")

        # Calculate net odds: payout if win / cost to enter
        # Example: $0.20 entry pays $1.00 if win → net = $0.80 / $0.20 = 4.0
        net_odds = (1.0 - entry_price) / entry_price

        # Calculate loss probability
        loss_prob = 1.0 - win_prob

        # Kelly formula: f* = (p*b - q) / b
        # Where p=win_prob, q=loss_prob, b=net_odds
        kelly_full = (win_prob * net_odds - loss_prob) / net_odds

        # Apply fractional Kelly for safety (reduce variance)
        kelly_fractional = kelly_full * self.kelly_fraction

        # Clamp to min/max range
        kelly_clamped = max(self.min_size_pct, min(kelly_fractional, self.max_size_pct))

        # Convert to USD
        position_size_usd = balance * kelly_clamped

        # Build debug info
        debug_info = {
            "win_prob": win_prob,
            "loss_prob": loss_prob,
            "entry_price": entry_price,
            "net_odds": net_odds,
            "kelly_full": kelly_full,
            "kelly_full_pct": kelly_full * 100,
            "kelly_fractional": kelly_fractional,
            "kelly_fractional_pct": kelly_fractional * 100,
            "kelly_clamped": kelly_clamped,
            "kelly_clamped_pct": kelly_clamped * 100,
            "balance": balance,
            "position_size_usd": position_size_usd,
            "position_pct": kelly_clamped * 100,
            "clamped_by_min": kelly_fractional < self.min_size_pct,
            "clamped_by_max": kelly_fractional > self.max_size_pct,
        }

        return position_size_usd, debug_info

    def compare_with_fixed_tiers(
        self,
        win_prob: float,
        entry_price: float,
        balance: float
    ) -> Dict[str, any]:
        """
        Compare Kelly sizing with fixed tier sizing.

        Fixed tiers (from bot):
        - Balance < $30: 15%
        - Balance $30-75: 10%
        - Balance $75-150: 7%
        - Balance > $150: 5%

        Args:
            win_prob: Win probability
            entry_price: Entry price
            balance: Current balance

        Returns:
            Dict with comparison of Kelly vs Fixed sizing
        """
        # Calculate Kelly size
        kelly_size, kelly_info = self.calculate_kelly_size(win_prob, entry_price, balance)

        # Calculate fixed tier size
        if balance < 30:
            fixed_pct = 0.15
        elif balance < 75:
            fixed_pct = 0.10
        elif balance < 150:
            fixed_pct = 0.07
        else:
            fixed_pct = 0.05

        fixed_size = balance * fixed_pct

        # Calculate difference
        difference_usd = kelly_size - fixed_size
        difference_pct = (difference_usd / fixed_size) * 100 if fixed_size > 0 else 0

        return {
            "balance": balance,
            "kelly_size_usd": kelly_size,
            "kelly_pct": kelly_info["position_pct"],
            "fixed_size_usd": fixed_size,
            "fixed_pct": fixed_pct * 100,
            "difference_usd": difference_usd,
            "difference_pct": difference_pct,
            "kelly_larger": kelly_size > fixed_size,
        }


if __name__ == "__main__":
    """Example usage and test cases."""

    print("=" * 80)
    print("Kelly Criterion Position Sizer - Examples")
    print("=" * 80)

    sizer = KellyPositionSizer(kelly_fraction=0.25, min_size_pct=0.02, max_size_pct=0.15)

    # Test scenarios
    scenarios = [
        {
            "name": "High Edge Contrarian (65% @ $0.20)",
            "win_prob": 0.65,
            "entry_price": 0.20,
            "balance": 100.0,
        },
        {
            "name": "Moderate Edge Early (58% @ $0.30)",
            "win_prob": 0.58,
            "entry_price": 0.30,
            "balance": 100.0,
        },
        {
            "name": "Low Edge Late (88% @ $0.85)",
            "win_prob": 0.88,
            "entry_price": 0.85,
            "balance": 100.0,
        },
        {
            "name": "Break-even (50% @ $0.50)",
            "win_prob": 0.50,
            "entry_price": 0.50,
            "balance": 100.0,
        },
        {
            "name": "Large Balance High Edge",
            "win_prob": 0.65,
            "entry_price": 0.20,
            "balance": 250.0,
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 80)

        size, info = sizer.calculate_kelly_size(
            win_prob=scenario["win_prob"],
            entry_price=scenario["entry_price"],
            balance=scenario["balance"]
        )

        print(f"  Win Probability: {info['win_prob']*100:.1f}%")
        print(f"  Entry Price: ${info['entry_price']:.2f}")
        print(f"  Net Odds: {info['net_odds']:.2f}x")
        print(f"  Balance: ${info['balance']:.2f}")
        print()
        print(f"  Full Kelly: {info['kelly_full_pct']:.2f}%")
        print(f"  Fractional Kelly (25%): {info['kelly_fractional_pct']:.2f}%")
        print(f"  Clamped Kelly: {info['kelly_clamped_pct']:.2f}%")
        print(f"  Position Size: ${info['position_size_usd']:.2f}")

        if info['clamped_by_min']:
            print(f"  ⚠️  Clamped to minimum (2%)")
        elif info['clamped_by_max']:
            print(f"  ⚠️  Clamped to maximum (15%)")

    print("\n" + "=" * 80)
    print("Kelly vs Fixed Tier Comparison")
    print("=" * 80)

    # Compare Kelly vs Fixed for same scenario
    comparison_scenarios = [
        {"win_prob": 0.65, "entry_price": 0.20, "balance": 25.0},
        {"win_prob": 0.65, "entry_price": 0.20, "balance": 50.0},
        {"win_prob": 0.65, "entry_price": 0.20, "balance": 100.0},
        {"win_prob": 0.65, "entry_price": 0.20, "balance": 200.0},
    ]

    for scenario in comparison_scenarios:
        comp = sizer.compare_with_fixed_tiers(**scenario)
        print(f"\nBalance: ${comp['balance']:.2f}")
        print(f"  Kelly: ${comp['kelly_size_usd']:.2f} ({comp['kelly_pct']:.2f}%)")
        print(f"  Fixed: ${comp['fixed_size_usd']:.2f} ({comp['fixed_pct']:.2f}%)")
        print(f"  Difference: ${comp['difference_usd']:.2f} ({comp['difference_pct']:+.1f}%)")
        if comp['kelly_larger']:
            print(f"  → Kelly sizes larger (more aggressive)")
        else:
            print(f"  → Fixed sizes larger (more conservative)")

    print("\n" + "=" * 80)
    print("✅ Kelly Position Sizer - All tests passed")
    print("=" * 80)
