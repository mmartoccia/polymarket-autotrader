#!/usr/bin/env python3
"""
Epoch Outcome Autocorrelation Analysis
Author: Prof. Eleanor Nash (Game Theory Economist)
Persona Context: "Are consecutive epoch outcomes independent? Or is there momentum?"

Tests if winning epochs predict future winning epochs (momentum) or if outcomes are independent.
Uses time series analysis to detect patterns that violate i.i.d. assumptions.
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple
import py_compile

def extract_sequential_outcomes(db_path: str) -> List[int]:
    """
    Extract sequential trade outcomes from database, ordered by timestamp.

    Returns:
        List of outcomes: 1 = win, 0 = loss (chronologically ordered)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query resolved outcomes, ordered by timestamp
    query = """
    SELECT
        o.predicted_direction,
        o.actual_direction,
        o.crypto,
        o.timestamp
    FROM outcomes o
    WHERE o.strategy = 'default'  -- Live strategy only
    ORDER BY o.timestamp ASC
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    # Convert to binary outcomes: 1 = win, 0 = loss
    outcomes = []
    for pred_dir, actual_dir, crypto, timestamp in rows:
        win = 1 if pred_dir == actual_dir else 0
        outcomes.append(win)

    return outcomes


def calculate_autocorrelation(outcomes: List[int], lag: int = 1) -> float:
    """
    Calculate autocorrelation at specified lag.

    Autocorrelation formula:
        r(k) = Σ(x_t - μ)(x_{t-k} - μ) / Σ(x_t - μ)²

    Args:
        outcomes: Binary sequence (1 = win, 0 = loss)
        lag: Time lag (1 = consecutive, 2 = skip one, etc.)

    Returns:
        Autocorrelation coefficient (-1 to 1)
    """
    if len(outcomes) < lag + 1:
        return 0.0

    n = len(outcomes)
    mean = sum(outcomes) / n

    # Numerator: Σ(x_t - μ)(x_{t-k} - μ)
    numerator = 0.0
    for t in range(lag, n):
        numerator += (outcomes[t] - mean) * (outcomes[t - lag] - mean)

    # Denominator: Σ(x_t - μ)²
    denominator = sum((x - mean) ** 2 for x in outcomes)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def ljung_box_test(outcomes: List[int], max_lag: int = 5) -> Tuple[float, float]:
    """
    Ljung-Box test for independence (tests multiple lags simultaneously).

    H0: Outcomes are independent (no autocorrelation)
    H1: Outcomes exhibit autocorrelation (momentum/pattern exists)

    Formula:
        Q = n(n+2) Σ[r²(k) / (n-k)] for k=1 to max_lag

    Q follows chi-squared distribution with 'max_lag' degrees of freedom.

    Returns:
        (Q statistic, p-value approximation)
    """
    n = len(outcomes)
    if n < max_lag + 1:
        return 0.0, 1.0

    # Calculate Q statistic
    Q = 0.0
    for k in range(1, max_lag + 1):
        r_k = calculate_autocorrelation(outcomes, lag=k)
        Q += (r_k ** 2) / (n - k)

    Q = n * (n + 2) * Q

    # Approximate p-value using chi-squared distribution
    # Degrees of freedom = max_lag
    # Simple approximation: p-value ≈ 1 if Q < df, 0 if Q >> df
    df = max_lag

    # Chi-squared critical values (df=5, α=0.05 → critical=11.07)
    critical_values = {
        1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07,
        6: 12.59, 7: 14.07, 8: 15.51, 9: 16.92, 10: 18.31
    }

    critical_val = critical_values.get(df, 15.0)  # Default fallback

    # Rough p-value estimation
    if Q < critical_val * 0.5:
        p_value = 0.9  # Very likely independent
    elif Q < critical_val:
        p_value = 0.2  # Likely independent
    elif Q < critical_val * 1.5:
        p_value = 0.05  # Borderline
    elif Q < critical_val * 2.0:
        p_value = 0.01  # Significant autocorrelation
    else:
        p_value = 0.001  # Highly significant autocorrelation

    return Q, p_value


def interpret_autocorrelation(r: float) -> str:
    """
    Interpret autocorrelation coefficient magnitude and direction.
    """
    if abs(r) < 0.05:
        return "No correlation (independent)"
    elif abs(r) < 0.15:
        return "Weak correlation (minimal momentum)"
    elif abs(r) < 0.30:
        return "Moderate correlation (noticeable momentum)"
    else:
        return "Strong correlation (significant momentum)"

    # Direction
    direction = "Positive (wins beget wins)" if r > 0 else "Negative (mean reversion)"
    return f"{magnitude} - {direction}"


def generate_report(outcomes: List[int], output_path: str):
    """
    Generate autocorrelation analysis report.
    """
    if len(outcomes) < 10:
        # Insufficient data
        report = f"""# Epoch Outcome Autocorrelation Analysis
**Persona:** Prof. Eleanor Nash (Game Theory Economist)
**Date:** {Path(__file__).stat().st_mtime}

---

## Summary

⚠️ **INSUFFICIENT DATA FOR ANALYSIS**

**Sample Size:** {len(outcomes)} resolved trades

**Minimum Required:** 10 trades (preferably 50+)

**Why This Matters:**
Autocorrelation tests require sufficient data to detect patterns reliably.
With <10 trades, any correlation found is likely random noise, not true momentum.

**Timeline:**
- 10 trades: ~2 days of VPS trading (baseline analysis possible)
- 50 trades: ~1 week (reliable statistical significance)
- 100 trades: ~2 weeks (high confidence in findings)

---

## What Is Autocorrelation?

**Autocorrelation** measures if consecutive outcomes are related:
- **Independent (r ≈ 0):** Past outcomes don't predict future (coin flip)
- **Positive momentum (r > 0):** Wins predict future wins, losses predict losses
- **Mean reversion (r < 0):** Wins predict losses, losses predict wins

**Game Theory Perspective:**
If momentum exists (r > 0.15), it suggests:
1. Market inefficiency: Predictable patterns exist
2. Regime persistence: Bull/bear markets continue multi-epoch
3. Exploitable edge: Increase position size after wins

If independent (r ≈ 0), it suggests:
1. Efficient markets: No exploitable patterns
2. I.I.D. assumption valid: Each trade is independent
3. Risk management focus: Position sizing should be static

---

## Next Steps

1. **Wait for data:** Continue VPS trading for 7+ days
2. **Re-run analysis:** `python3 scripts/research/epoch_autocorrelation.py`
3. **Review findings:** Check if momentum exists (p < 0.05)
4. **Adjust strategy:** If momentum found, implement Kelly sizing or streak bonuses

---

**Prof. Eleanor Nash's Assessment:**
> "In game theory, we assume opponents adapt to patterns. If momentum exists,
> the market hasn't adapted yet—an exploitable inefficiency. But it won't last.
> Use it wisely before arbitrage erases the edge."

"""
    else:
        # Calculate autocorrelations at multiple lags
        r1 = calculate_autocorrelation(outcomes, lag=1)
        r2 = calculate_autocorrelation(outcomes, lag=2)
        r3 = calculate_autocorrelation(outcomes, lag=3)

        # Ljung-Box test
        Q, p_value = ljung_box_test(outcomes, max_lag=5)

        # Interpretation
        win_rate = sum(outcomes) / len(outcomes)
        win_count = sum(outcomes)
        loss_count = len(outcomes) - win_count

        # Conclusion
        if p_value < 0.05:
            conclusion = "❌ REJECT H0: Outcomes are NOT independent (momentum exists)"
            recommendation = "EXPLOIT: Increase position sizing after wins, reduce after losses"
        else:
            conclusion = "✅ ACCEPT H0: Outcomes are independent (no momentum)"
            recommendation = "STANDARD: Use static position sizing, no streak adjustments"

        # Direction interpretation
        if abs(r1) < 0.05:
            direction = "No correlation (random walk)"
        elif r1 > 0:
            direction = "Positive momentum (wins predict wins)"
        else:
            direction = "Negative momentum (mean reversion)"

        report = f"""# Epoch Outcome Autocorrelation Analysis
**Persona:** Prof. Eleanor Nash (Game Theory Economist)
**Date:** {Path(__file__).stat().st_mtime}

---

## Executive Summary

**Sample Size:** {len(outcomes)} resolved trades
**Win Rate:** {win_rate:.1%} ({win_count}W / {loss_count}L)
**Autocorrelation (lag=1):** r = {r1:.3f}
**Ljung-Box Test:** Q = {Q:.2f}, p-value = {p_value:.3f}

**Conclusion:** {conclusion}

**Interpretation:** {direction}

**Recommendation:** {recommendation}

---

## Autocorrelation Results

### Lag Analysis

| Lag | Description | r | Interpretation |
|-----|-------------|---|----------------|
| 1 | Consecutive epochs | {r1:.3f} | {interpret_autocorrelation(r1)} |
| 2 | Skip one epoch | {r2:.3f} | {interpret_autocorrelation(r2)} |
| 3 | Skip two epochs | {r3:.3f} | {interpret_autocorrelation(r3)} |

**Key Insight:**
- **Lag 1** (consecutive): {abs(r1):.3f} {'> 0.15 → Momentum exists' if abs(r1) > 0.15 else '< 0.15 → Minimal correlation'}
- **Lag 2-3**: {abs(r2):.3f}, {abs(r3):.3f} (persistence beyond 1 epoch)

---

## Ljung-Box Test for Independence

**Hypothesis:**
- H0: Outcomes are independent (no autocorrelation across lags 1-5)
- H1: Outcomes exhibit autocorrelation (momentum pattern exists)

**Test Statistic:** Q = {Q:.2f}
**P-value:** {p_value:.3f}
**Significance Level:** α = 0.05

**Conclusion:**
{conclusion}

**Interpretation:**
{'Consecutive outcomes are correlated—past results help predict future results.' if p_value < 0.05 else 'Consecutive outcomes are independent—past results do NOT predict future results.'}

---

## Practical Implications

### If Momentum Exists (p < 0.05):

**1. Adjust Position Sizing:**
- After win: Increase sizing by 10-20% (ride the streak)
- After loss: Decrease sizing by 10-20% (avoid chasing losses)

**2. Implement Streak Bonuses:**
- 2+ consecutive wins: Lower consensus threshold (0.75 → 0.70)
- 2+ consecutive losses: Raise consensus threshold (0.75 → 0.80)

**3. Monitor for Regime Shifts:**
- Momentum may disappear when market regime changes
- Re-run analysis monthly to detect shifts

**4. Kelly Criterion Enhancement:**
- Standard Kelly: f = (p*b - q) / b
- Momentum-adjusted Kelly: f = f * (1 + 0.2 * momentum_strength)

### If Independent (p ≥ 0.05):

**1. Static Position Sizing:**
- Use tiered sizing based on balance only
- Ignore recent win/loss history

**2. No Streak Adjustments:**
- Maintain consistent thresholds regardless of past outcomes
- Avoid gambler's fallacy (expecting reversal after losses)

**3. Focus on Per-Trade Edge:**
- Optimize individual trade quality (entry price, confidence)
- Ignore sequence effects

---

## Game Theory Perspective

**Nash Equilibrium Considerations:**

If momentum exists, the market is **exploitable**:
- Other traders haven't adapted to the pattern
- First-mover advantage: Exploit before arbitrage erases edge
- Competitive risk: As more bots detect momentum, it disappears

If outcomes are independent, the market is **efficient**:
- No exploitable patterns in outcome sequences
- Focus on fundamental edge (agent quality, entry timing)
- Position sizing should be risk-adjusted, not streak-adjusted

**Evolutionary Game Theory:**
Markets evolve. Today's momentum may be tomorrow's noise.
- Monitor autocorrelation monthly
- Adapt strategy as market dynamics change
- Expect competitors to copy successful momentum strategies

---

## Statistical Rigor Notes

**Sample Size Adequacy:**
- Current: {len(outcomes)} trades
- Minimum for reliability: 50 trades (margin of error ≈ ±0.20)
- Good confidence: 100+ trades (margin of error ≈ ±0.14)

**Confidence Intervals:**
For r = {r1:.3f} with n = {len(outcomes)}:
- 95% CI: [{r1 - 0.2:.3f}, {r1 + 0.2:.3f}] (approximate)
- Interpretation: True correlation likely in this range

**Limitations:**
1. Assumes stationarity (market conditions don't change)
2. Ignores crypto-specific patterns (BTC vs ETH)
3. Ignores regime-specific patterns (bull vs bear)
4. Assumes linear correlation (may miss nonlinear patterns)

---

## Recommendations

**Immediate Actions:**
1. {'Implement streak-based position sizing' if p_value < 0.05 else 'Keep static position sizing (no changes needed)'}
2. {'Lower thresholds after 2+ wins, raise after 2+ losses' if p_value < 0.05 else 'Maintain consistent thresholds'}
3. Re-run analysis after 100 trades to confirm findings

**Long-term Monitoring:**
1. Track autocorrelation over time (monthly snapshots)
2. Alert if p-value crosses 0.05 threshold (regime change)
3. Compare momentum strength across cryptos (BTC vs ETH patterns)

**Further Research:**
1. Crypto-specific autocorrelation (does BTC have momentum but ETH doesn't?)
2. Regime-specific autocorrelation (momentum in bull markets only?)
3. Nonlinear patterns (Markov chains, hidden states)

---

**Prof. Eleanor Nash's Assessment:**
> "{('Momentum exists—a rare inefficiency. Exploit it now, but know it wont last. Markets punish predictable patterns. Use this edge while competitors sleep.' if p_value < 0.05 else 'Outcomes are independent—the market is efficient at this timeframe. No free lunch. Focus on per-trade quality, not sequence patterns.')}"

**Bottom Line:**
{('Adjust sizing based on recent outcomes. Momentum is real, but fleeting.' if p_value < 0.05 else 'Ignore recent outcomes. Each trade stands alone. Optimize individual trade quality.')}

"""

    # Write report
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"✅ Report generated: {output_path}")
    print(f"   Sample size: {len(outcomes)} trades")
    if len(outcomes) >= 10:
        print(f"   Autocorrelation (lag=1): r = {r1:.3f}")
        print(f"   Ljung-Box test: p = {p_value:.3f}")
        print(f"   Conclusion: {conclusion}")


def test_autocorrelation_calculation():
    """
    Unit test: Verify autocorrelation calculation on known sequences.
    """
    # Test 1: Perfect positive autocorrelation (all wins or all losses)
    seq1 = [1, 1, 1, 1, 1]
    r1 = calculate_autocorrelation(seq1, lag=1)
    assert abs(r1 - 0.0) < 0.01, f"Expected r ≈ 0.0 for constant sequence, got {r1}"

    # Test 2: Perfect alternating (win-loss-win-loss)
    seq2 = [1, 0, 1, 0, 1, 0, 1, 0]
    r2 = calculate_autocorrelation(seq2, lag=1)
    assert r2 < -0.8, f"Expected strong negative correlation for alternating, got {r2}"

    # Test 3: Random-like sequence
    seq3 = [1, 0, 1, 1, 0, 0, 1, 0, 1, 0]
    r3 = calculate_autocorrelation(seq3, lag=1)
    assert abs(r3) < 0.5, f"Expected weak correlation for random-like, got {r3}"

    print("✅ Autocorrelation calculation tests passed")


def main():
    # Paths
    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / "simulation" / "trade_journal.db"
    report_path = project_root / "reports" / "eleanor_nash" / "epoch_autocorrelation.md"

    # Check database exists
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("   Database will be created when bot starts shadow trading.")

        # Generate report with "NO DATA" message
        generate_report([], str(report_path))
        return 0

    # Extract outcomes
    print("Extracting sequential outcomes from database...")
    outcomes = extract_sequential_outcomes(str(db_path))

    if len(outcomes) == 0:
        print("⚠️  No resolved trades found in database")
        print("   Wait for bot to complete 10+ trades, then re-run analysis")

        # Generate report with "NO DATA" message
        generate_report([], str(report_path))
        return 0

    print(f"✅ Extracted {len(outcomes)} resolved trades")
    print(f"   Win rate: {sum(outcomes) / len(outcomes):.1%}")

    # Run test
    print("\nRunning autocorrelation calculation tests...")
    test_autocorrelation_calculation()

    # Generate report
    print("\nGenerating autocorrelation analysis report...")
    generate_report(outcomes, str(report_path))

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Report: {report_path}")
    print("\nKey Questions Answered:")
    print("1. Are consecutive epoch outcomes independent?")
    print("2. Does winning predict future winning (momentum)?")
    print("3. Should we adjust position sizing based on recent outcomes?")
    print("\nNext Steps:")
    print("1. Review report for autocorrelation findings")
    print("2. If p < 0.05: Implement streak-based position adjustments")
    print("3. If p ≥ 0.05: Keep static position sizing (current approach)")
    print("4. Re-run after 100 trades for confirmation")

    return 0


if __name__ == "__main__":
    sys.exit(main())
