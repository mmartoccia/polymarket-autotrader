#!/usr/bin/env python3
"""
US-RC-013: Test win rate statistical significance

Persona: Dr. Sarah Chen (Probabilistic Mathematician)
Purpose: Determine if observed win rate is statistically significantly better than 50% coin flip

Statistical Test:
- Null Hypothesis (H0): p = 0.50 (coin flip, no edge)
- Alternative Hypothesis (H1): p > 0.50 (edge exists)
- Test: One-tailed binomial test (z-test approximation)
- Significance level: α = 0.05
- Formula: z = (p_obs - 0.50) / sqrt(0.50 * 0.50 / n)
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Trade:
    """Trade entry from bot logs"""
    timestamp: datetime
    crypto: str
    direction: str
    entry_price: float
    outcome: Optional[str] = None  # "WIN" or "LOSS"

    def is_complete(self) -> bool:
        return self.outcome is not None


@dataclass
class SignificanceResult:
    """Statistical significance test result"""
    observed_win_rate: float
    sample_size: int
    wins: int
    losses: int
    z_score: float
    p_value: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    is_significant: bool
    sample_size_needed_for_95_confidence: int
    verdict: str


class TradeLogParser:
    """Parse trades from bot.log"""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.trades: list[Trade] = []

    def parse(self) -> None:
        """Parse trades and outcomes"""
        if not self.log_path.exists():
            print(f"⚠️ Log file not found: {self.log_path}")
            return

        # Parse ORDER PLACED entries
        order_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*ORDER PLACED.*'
            r'(BTC|ETH|SOL|XRP)\s+(Up|Down).*Entry[:\s]+\$?([\d.]+)',
            re.IGNORECASE
        )

        # Parse WIN/LOSS entries
        outcome_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*'
            r'(WIN|LOSS).*'
            r'(BTC|ETH|SOL|XRP)\s+(Up|Down)',
            re.IGNORECASE
        )

        orders: dict[tuple, Trade] = {}  # (timestamp_str, crypto, direction) -> Trade

        with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Check for ORDER PLACED
                order_match = order_pattern.search(line)
                if order_match:
                    ts_str = order_match.group(1)
                    try:
                        timestamp = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        continue

                    crypto = order_match.group(2).upper()
                    direction = order_match.group(3).capitalize()
                    entry_price = float(order_match.group(4))

                    trade = Trade(timestamp, crypto, direction, entry_price)
                    key = (ts_str, crypto, direction)
                    orders[key] = trade

                # Check for WIN/LOSS
                outcome_match = outcome_pattern.search(line)
                if outcome_match:
                    ts_str = outcome_match.group(1)
                    outcome = outcome_match.group(2).upper()
                    crypto = outcome_match.group(3).upper()
                    direction = outcome_match.group(4).capitalize()

                    # Fuzzy match to order (within 20 min window)
                    try:
                        outcome_time = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        continue

                    # Try exact match first
                    key = (ts_str, crypto, direction)
                    if key in orders:
                        orders[key].outcome = outcome
                    else:
                        # Fuzzy match within 20 min window
                        for (order_ts_str, order_crypto, order_dir), trade in orders.items():
                            if order_crypto == crypto and order_dir == direction:
                                time_diff = abs((outcome_time - trade.timestamp).total_seconds())
                                if time_diff <= 1200:  # 20 minutes
                                    if trade.outcome is None:
                                        trade.outcome = outcome
                                        break

        # Store complete trades
        self.trades = [trade for trade in orders.values() if trade.is_complete()]


class StatisticalSignificanceTester:
    """Test if win rate is significantly better than 50%"""

    def __init__(self, trades: list[Trade]):
        self.trades = trades

    def run_test(self) -> SignificanceResult:
        """Run binomial test (z-test approximation)"""
        n = len(self.trades)
        wins = sum(1 for t in self.trades if t.outcome == "WIN")
        losses = n - wins

        if n == 0:
            return SignificanceResult(
                observed_win_rate=0.0,
                sample_size=0,
                wins=0,
                losses=0,
                z_score=0.0,
                p_value=1.0,
                confidence_interval_lower=0.0,
                confidence_interval_upper=0.0,
                is_significant=False,
                sample_size_needed_for_95_confidence=384,  # Standard formula
                verdict="INSUFFICIENT DATA"
            )

        p_obs = wins / n

        # Z-test for proportion
        # H0: p = 0.50 (coin flip)
        # H1: p > 0.50 (edge exists, one-tailed)
        p_null = 0.50
        se = math.sqrt(p_null * (1 - p_null) / n)
        z_score = (p_obs - p_null) / se

        # P-value (one-tailed, upper tail)
        p_value = self._normal_cdf(-z_score)  # P(Z > z_score)

        # 95% confidence interval (two-tailed)
        z_critical = 1.96  # For 95% CI
        se_obs = math.sqrt(p_obs * (1 - p_obs) / n)
        ci_lower = max(0.0, p_obs - z_critical * se_obs)
        ci_upper = min(1.0, p_obs + z_critical * se_obs)

        # Significance test
        is_significant = p_value < 0.05

        # Sample size needed for 95% confidence at observed win rate
        # Formula: n = (z^2 * p * (1-p)) / E^2, where E = 0.025 (±2.5% margin)
        margin = 0.025
        n_needed = int((z_critical ** 2) * p_obs * (1 - p_obs) / (margin ** 2))

        # Verdict
        if n < 30:
            verdict = "INSUFFICIENT DATA"
        elif not is_significant:
            verdict = "NO EDGE DETECTED"
        elif is_significant and p_obs < 0.53:
            verdict = "EDGE DETECTED (MARGINAL)"
        elif is_significant and p_obs < 0.60:
            verdict = "EDGE DETECTED (MODERATE)"
        else:
            verdict = "EDGE DETECTED (STRONG)"

        return SignificanceResult(
            observed_win_rate=p_obs,
            sample_size=n,
            wins=wins,
            losses=losses,
            z_score=z_score,
            p_value=p_value,
            confidence_interval_lower=ci_lower,
            confidence_interval_upper=ci_upper,
            is_significant=is_significant,
            sample_size_needed_for_95_confidence=n_needed,
            verdict=verdict
        )

    def _normal_cdf(self, z: float) -> float:
        """Approximate standard normal CDF using error function"""
        # For one-tailed upper test, we want P(Z > z) = 1 - Φ(z)
        # Φ(z) ≈ 0.5 * (1 + erf(z / sqrt(2)))
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def generate_report(result: SignificanceResult, output_path: Path) -> None:
    """Generate markdown report"""

    # Verdict emoji
    verdict_emoji = {
        "INSUFFICIENT DATA": "⚠️",
        "NO EDGE DETECTED": "🔴",
        "EDGE DETECTED (MARGINAL)": "🟡",
        "EDGE DETECTED (MODERATE)": "🟢",
        "EDGE DETECTED (STRONG)": "🟢"
    }.get(result.verdict, "⚪")

    report = f"""# Statistical Significance Analysis - Win Rate Validation

**Persona:** Dr. Sarah Chen (Probabilistic Mathematician)
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Verdict:** {verdict_emoji} **{result.verdict}**

---

## Executive Summary

**Hypothesis Test:**
- **Null Hypothesis (H0):** Win rate = 50% (coin flip, no edge)
- **Alternative Hypothesis (H1):** Win rate > 50% (edge exists)
- **Test Type:** One-tailed binomial test (z-test approximation)
- **Significance Level:** α = 0.05

**Results:**
- **Observed Win Rate:** {result.observed_win_rate * 100:.2f}%
- **Sample Size:** {result.sample_size} trades ({result.wins} wins, {result.losses} losses)
- **Z-Score:** {result.z_score:.4f}
- **P-Value:** {result.p_value:.4f}
- **Statistically Significant:** {"✅ YES" if result.is_significant else "❌ NO"} (p < 0.05)
- **95% Confidence Interval:** [{result.confidence_interval_lower * 100:.2f}%, {result.confidence_interval_upper * 100:.2f}%]

**Interpretation:**
{_get_interpretation(result)}

---

## Statistical Test Details

### Test Statistic Calculation

The z-score measures how many standard deviations the observed win rate is from the null hypothesis (50%):

```
z = (p_observed - p_null) / SE
  = ({result.observed_win_rate:.4f} - 0.50) / sqrt(0.50 × 0.50 / {result.sample_size})
  = {result.z_score:.4f}
```

**Standard Error (SE):**
```
SE = sqrt(p × (1-p) / n)
   = sqrt(0.50 × 0.50 / {result.sample_size})
   = {math.sqrt(0.50 * 0.50 / result.sample_size) if result.sample_size > 0 else 0:.4f}
```

### P-Value Interpretation

The p-value represents the probability of observing a win rate this high (or higher) if the true win rate were 50% (coin flip).

- **P-value:** {result.p_value:.4f}
- **Threshold:** α = 0.05

{f"✅ **Conclusion:** Since p = {result.p_value:.4f} < 0.05, we **REJECT the null hypothesis**. The observed win rate is statistically significantly better than a coin flip." if result.is_significant else f"❌ **Conclusion:** Since p = {result.p_value:.4f} ≥ 0.05, we **FAIL TO REJECT the null hypothesis**. The observed win rate is NOT statistically significantly better than a coin flip."}

### Confidence Interval

The 95% confidence interval provides a range where the **true win rate** likely falls:

- **95% CI:** [{result.confidence_interval_lower * 100:.2f}%, {result.confidence_interval_upper * 100:.2f}%]

**Interpretation:**
We are 95% confident that the true long-term win rate lies within this interval.

{f"✅ The interval is **entirely above 50%**, further supporting that an edge exists." if result.confidence_interval_lower > 0.50 else f"⚠️ The interval **includes 50%**, meaning the true win rate might still be a coin flip." if result.confidence_interval_lower <= 0.50 <= result.confidence_interval_upper else "🔴 The interval is **entirely below 50%**, suggesting the system may be unprofitable."}

---

## Sample Size Analysis

### Current Sample Size: {result.sample_size} trades

**Adequacy Assessment:**
{_get_sample_size_assessment(result.sample_size)}

### Sample Size Required for 95% Confidence

To achieve a **±2.5% margin of error** at 95% confidence level with the observed win rate:

```
n_required = (z² × p × (1-p)) / E²
           = (1.96² × {result.observed_win_rate:.4f} × {1 - result.observed_win_rate:.4f}) / 0.025²
           = {result.sample_size_needed_for_95_confidence} trades
```

**Current Progress:** {result.sample_size} / {result.sample_size_needed_for_95_confidence} trades ({result.sample_size / max(result.sample_size_needed_for_95_confidence, 1) * 100:.1f}%)

{f"✅ **Sample size is adequate** for 95% confidence with narrow margin." if result.sample_size >= result.sample_size_needed_for_95_confidence else f"⚠️ **More data needed.** Collect {result.sample_size_needed_for_95_confidence - result.sample_size} more trades for statistical rigor."}

---

## Recommendations

### Immediate Actions
{_get_recommendations(result)}

---

## Methodology

### Data Source
- **Input:** bot.log (parsed trades with outcomes)
- **Filters:** Only complete trades (ORDER PLACED + WIN/LOSS outcome)
- **Sample:** {result.sample_size} trades

### Statistical Approach

**Test Selection:** One-tailed binomial test (z-test approximation)
- **Why one-tailed?** We only care if win rate is **better** than 50%, not different.
- **Why z-test?** Normal approximation valid for n ≥ 30 and np ≥ 5.

**Assumptions:**
1. Trades are independent (no autocorrelation)
2. Win probability is constant across trades (stationarity)
3. Sample size sufficient for normal approximation (n ≥ 30)

**Violations:**
- **Non-stationarity:** Strategy evolves (v12 vs v12.1)
- **Regime shifts:** Bull/bear markets affect win rate
- **Solution:** Use recent trades (last 100) for time-local estimation

---

## Statistical Formulas Reference

### Z-Test for Proportion
```
z = (p_obs - p_null) / SE
SE = sqrt(p_null × (1 - p_null) / n)
```

### Confidence Interval
```
CI = p_obs ± z_α/2 × SE_obs
SE_obs = sqrt(p_obs × (1 - p_obs) / n)
z_α/2 = 1.96 for 95% CI
```

### Sample Size Calculation
```
n = (z² × p × (1-p)) / E²
z = 1.96 for 95% confidence
E = desired margin of error
```

### P-Value (One-Tailed)
```
p-value = P(Z > z_obs) = 1 - Φ(z_obs)
Φ(z) = standard normal CDF
```

---

## Appendix: Trade Breakdown

| Metric | Value |
|--------|-------|
| Total Trades | {result.sample_size} |
| Wins | {result.wins} |
| Losses | {result.losses} |
| Win Rate | {result.observed_win_rate * 100:.2f}% |
| Z-Score | {result.z_score:.4f} |
| P-Value | {result.p_value:.4f} |
| Significant? | {"YES" if result.is_significant else "NO"} |

---

**Next Steps:**
1. Review fee economics (US-RC-011) to determine profitability threshold
2. Run Monte Carlo simulation (US-RC-012) to validate long-term stability
3. Compare to breakeven win rate calculated in fee analysis
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"✅ Report generated: {output_path}")


def _get_interpretation(result: SignificanceResult) -> str:
    """Get human-readable interpretation"""
    if result.sample_size < 30:
        return (
            "⚠️ **Insufficient data** for reliable statistical testing. "
            "Minimum sample size is 30 trades. Current results are unreliable."
        )

    if not result.is_significant:
        return (
            f"🔴 **No edge detected.** The observed win rate ({result.observed_win_rate * 100:.2f}%) "
            f"is NOT statistically significantly better than a coin flip (50%). "
            f"The system may not have an edge, or the sample size ({result.sample_size} trades) "
            f"is too small to detect a real edge. P-value = {result.p_value:.4f} ≥ 0.05."
        )

    if result.verdict == "EDGE DETECTED (MARGINAL)":
        return (
            f"🟡 **Marginal edge detected.** The observed win rate ({result.observed_win_rate * 100:.2f}%) "
            f"is statistically significantly better than 50% (p = {result.p_value:.4f}), "
            f"but the edge is small. After fees (~2-3%), profitability may be marginal. "
            f"Requires larger sample size for confirmation."
        )

    if result.verdict == "EDGE DETECTED (MODERATE)":
        return (
            f"🟢 **Moderate edge detected.** The observed win rate ({result.observed_win_rate * 100:.2f}%) "
            f"is statistically significantly better than 50% (p = {result.p_value:.4f}). "
            f"With proper position sizing and fee management, the system should be profitable. "
            f"Z-score = {result.z_score:.2f} indicates a robust edge."
        )

    # STRONG edge
    return (
        f"🟢 **Strong edge detected.** The observed win rate ({result.observed_win_rate * 100:.2f}%) "
        f"is far above 50% with high statistical confidence (p = {result.p_value:.4f}). "
        f"Z-score = {result.z_score:.2f} indicates a very robust edge. "
        f"System is highly likely to be profitable after fees."
    )


def _get_sample_size_assessment(n: int) -> str:
    """Assess sample size adequacy"""
    if n < 30:
        return (
            "🔴 **INADEQUATE** - Minimum 30 trades required for z-test validity. "
            "Current results are unreliable."
        )
    elif n < 100:
        return (
            "🟡 **MINIMAL** - Sufficient for z-test, but narrow confidence intervals require more data. "
            "Statistical power is limited."
        )
    elif n < 384:
        return (
            "🟢 **ADEQUATE** - Good sample size for detecting moderate effects. "
            "Confidence intervals are reasonably narrow."
        )
    else:
        return (
            "🟢 **EXCELLENT** - Large sample size provides high statistical power and narrow confidence intervals. "
            "Results are highly reliable."
        )


def _get_recommendations(result: SignificanceResult) -> str:
    """Get actionable recommendations"""
    if result.sample_size < 30:
        return """
1. 🔴 **Continue trading to collect ≥30 trades** for valid statistical testing
2. Monitor win rate trend (is it improving or degrading?)
3. Review individual trade outcomes for patterns
4. Do NOT make optimization decisions based on current data (unreliable)
"""

    if not result.is_significant:
        return f"""
1. 🔴 **System may not have an edge** - consider halting trading until root cause identified
2. Review strategy assumptions (agent performance, entry timing, regime filters)
3. Collect {result.sample_size_needed_for_95_confidence - result.sample_size} more trades for definitive conclusion
4. Compare to breakeven win rate (US-RC-011) - if above breakeven, fees may be consuming edge
5. Review shadow trading results (US-RC-018) - are alternative strategies performing better?
"""

    if result.verdict == "EDGE DETECTED (MARGINAL)":
        return f"""
1. 🟡 **Edge is small** - optimize fee management (cheaper entries <$0.25)
2. Collect {max(0, result.sample_size_needed_for_95_confidence - result.sample_size)} more trades for confirmation
3. Review fee economics (US-RC-011) - ensure edge exceeds breakeven threshold
4. Consider higher confidence filters to reduce trade frequency but improve win rate
5. Monitor closely for regression to 50% (edge may be fragile)
"""

    # MODERATE or STRONG edge
    return f"""
1. ✅ **Edge confirmed** - continue current strategy
2. Optimize position sizing using Kelly Criterion (US-RC-012)
3. Monitor win rate monthly - alert if drops below {result.confidence_interval_lower * 100:.1f}%
4. Scale up capital allocation (risk of ruin is low)
5. Continue collecting data to narrow confidence interval
6. Review shadow strategies (US-RC-018) for further optimization opportunities
"""


def main():
    parser = argparse.ArgumentParser(description="Test win rate statistical significance")
    parser.add_argument('--log-file', type=str, default='bot.log',
                       help='Path to bot log file (default: bot.log)')
    parser.add_argument('--output', type=str,
                       default='reports/sarah_chen/statistical_significance.md',
                       help='Output report path')
    args = parser.parse_args()

    log_path = Path(args.log_file)
    output_path = Path(args.output)

    print(f"📊 Statistical Significance Tester")
    print(f"   Log file: {log_path}")
    print(f"   Output: {output_path}")
    print()

    # Parse trades
    print("📖 Parsing trade log...")
    log_parser = TradeLogParser(log_path)
    log_parser.parse()
    trades = log_parser.trades
    print(f"   Found {len(trades)} complete trades")
    print()

    # Run statistical test
    print("🧮 Running statistical significance test...")
    tester = StatisticalSignificanceTester(trades)
    result = tester.run_test()
    print(f"   Observed WR: {result.observed_win_rate * 100:.2f}%")
    print(f"   Z-score: {result.z_score:.4f}")
    print(f"   P-value: {result.p_value:.4f}")
    print(f"   Significant: {'YES' if result.is_significant else 'NO'}")
    print(f"   Verdict: {result.verdict}")
    print()

    # Generate report
    print("📝 Generating report...")
    generate_report(result, output_path)
    print()

    # Exit code
    if result.sample_size < 30:
        print("⚠️ EXIT CODE 0: Insufficient data (non-blocking)")
        sys.exit(0)
    elif result.is_significant:
        print("✅ EXIT CODE 0: Edge detected (statistically significant)")
        sys.exit(0)
    else:
        print("⚠️ EXIT CODE 0: No edge detected (hypothesis test result)")
        sys.exit(0)


if __name__ == '__main__':
    main()
