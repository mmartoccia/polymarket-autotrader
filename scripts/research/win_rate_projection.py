#!/usr/bin/env python3
"""
US-RC-033: Validate 60-65% Win Rate Feasibility

Persona: Prof. Eleanor Nash (Game Theory Economist)
Mindset: "Based on all research, can we realistically achieve 60-65% WR? Or should we adjust expectations?"

Monte Carlo simulation of improvement combinations to project achievable win rate.
"""

import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import statistics


def load_improvements() -> List[Dict[str, float]]:
    """
    Load identified improvements from research synthesis.
    Each improvement has: name, win_rate_delta, probability_of_success
    """
    improvements = [
        {
            "name": "Disable underperforming agents (TechAgent 48%, SentimentAgent 52%)",
            "wr_delta": 0.02,  # +2% WR improvement
            "probability": 0.90,  # 90% chance this helps
            "category": "SIMPLIFICATION"
        },
        {
            "name": "Raise consensus threshold (0.75 → 0.82-0.85)",
            "wr_delta": 0.03,  # +3% WR improvement
            "probability": 0.85,  # 85% chance this helps
            "category": "OPTIMIZATION"
        },
        {
            "name": "Optimize entry timing (focus on late trades 600-900s)",
            "wr_delta": 0.02,  # +2% WR improvement
            "probability": 0.75,  # 75% chance this helps
            "category": "OPTIMIZATION"
        },
        {
            "name": "Lower entry price threshold (<$0.15 sweet spot)",
            "wr_delta": 0.025,  # +2.5% WR improvement
            "probability": 0.80,  # 80% chance this helps
            "category": "OPTIMIZATION"
        },
        {
            "name": "Remove trend filter (prevent directional bias)",
            "wr_delta": 0.015,  # +1.5% WR improvement
            "probability": 0.95,  # 95% chance this helps (clear data)
            "category": "SIMPLIFICATION"
        },
        {
            "name": "Reduce agent count (11 → 3-5, remove redundancy)",
            "wr_delta": 0.01,  # +1% WR improvement
            "probability": 0.70,  # 70% chance this helps
            "category": "SIMPLIFICATION"
        },
        {
            "name": "Re-enable contrarian with higher confidence (0.85+)",
            "wr_delta": 0.02,  # +2% WR improvement
            "probability": 0.65,  # 65% chance this helps (less certain)
            "category": "OPTIMIZATION"
        },
        {
            "name": "Fix state tracking bugs (prevent false halts)",
            "wr_delta": 0.005,  # +0.5% WR improvement (indirect)
            "probability": 1.0,  # 100% this is necessary (bug fix)
            "category": "FIX"
        }
    ]
    return improvements


def run_simulation(
    current_wr: float,
    improvements: List[Dict[str, float]],
    num_simulations: int = 1000
) -> Tuple[List[float], Dict[str, int]]:
    """
    Run Monte Carlo simulation of improvement combinations.

    Each simulation:
    1. For each improvement, roll dice to see if it works (based on probability)
    2. If it works, add win_rate_delta to current WR
    3. Track final WR across all simulations

    Returns:
        - List of final win rates from all simulations
        - Count of how many simulations reached 60-65% target
    """
    final_wrs = []
    target_counts = {
        "below_60": 0,
        "60_to_65": 0,
        "above_65": 0
    }

    for sim_idx in range(num_simulations):
        sim_wr = current_wr

        # Apply each improvement (probabilistically)
        for improvement in improvements:
            # Roll dice: does this improvement work?
            if random.random() < improvement["probability"]:
                sim_wr += improvement["wr_delta"]

        final_wrs.append(sim_wr)

        # Categorize result
        if sim_wr < 0.60:
            target_counts["below_60"] += 1
        elif 0.60 <= sim_wr <= 0.65:
            target_counts["60_to_65"] += 1
        else:
            target_counts["above_65"] += 1

    return final_wrs, target_counts


def generate_report(
    current_wr: float,
    improvements: List[Dict[str, float]],
    final_wrs: List[float],
    target_counts: Dict[str, int],
    num_simulations: int
) -> str:
    """Generate markdown report with findings."""

    # Calculate statistics
    mean_wr = statistics.mean(final_wrs)
    median_wr = statistics.median(final_wrs)
    stdev_wr = statistics.stdev(final_wrs)
    min_wr = min(final_wrs)
    max_wr = max(final_wrs)

    # Calculate probabilities
    prob_reach_60_65 = (target_counts["60_to_65"] + target_counts["above_65"]) / num_simulations
    prob_exact_60_65 = target_counts["60_to_65"] / num_simulations
    prob_exceed_65 = target_counts["above_65"] / num_simulations

    # Calculate best-case and worst-case scenarios
    best_case_wr = current_wr + sum([imp["wr_delta"] for imp in improvements])
    worst_case_wr = current_wr  # No improvements work
    expected_wr = current_wr + sum([imp["wr_delta"] * imp["probability"] for imp in improvements])

    report = f"""# Win Rate Feasibility Analysis (60-65% Target)

**Persona:** Prof. Eleanor Nash (Game Theory Economist)
**Date:** 2026-01-16
**Methodology:** Monte Carlo simulation (N={num_simulations:,})

---

## Question

Based on comprehensive research findings (48 reports, 8 researchers), can we realistically achieve **60-65% win rate** target?

---

## Current State

- **Current Win Rate:** {current_wr:.1%}
- **Target Range:** 60-65%
- **Gap to Close:** {0.60 - current_wr:.1%} to {0.65 - current_wr:.1%}

---

## Identified Improvements

{len(improvements)} improvements identified from research synthesis:

"""

    # List improvements
    for idx, imp in enumerate(improvements, 1):
        report += f"{idx}. **{imp['name']}**\n"
        report += f"   - Expected Impact: +{imp['wr_delta']:.1%} WR\n"
        report += f"   - Probability of Success: {imp['probability']:.0%}\n"
        report += f"   - Category: {imp['category']}\n\n"

    report += f"""---

## Scenario Analysis

### Best Case (All Improvements Work)
- **Win Rate:** {best_case_wr:.1%}
- **Scenario:** Every improvement succeeds at maximum impact
- **Probability:** {statistics.geometric_mean([imp['probability'] for imp in improvements]):.1%} (product of all probabilities)

### Worst Case (No Improvements Work)
- **Win Rate:** {worst_case_wr:.1%}
- **Scenario:** Status quo (no changes)
- **Probability:** Very low (state tracking bug fix is mandatory)

### Expected Case (Probability-Weighted)
- **Win Rate:** {expected_wr:.1%}
- **Calculation:** Current WR + Σ(delta × probability)
- **Interpretation:** Most likely outcome

---

## Monte Carlo Simulation Results

**Simulation Parameters:**
- Runs: {num_simulations:,}
- Method: For each run, apply each improvement with probability P(success)
- Aggregation: Independent improvements (no correlation assumed)

**Distribution of Final Win Rates:**

```
Min:     {min_wr:.2%}
25th %:  {statistics.quantiles(final_wrs, n=4)[0]:.2%}
Median:  {median_wr:.2%}
Mean:    {mean_wr:.2%}
75th %:  {statistics.quantiles(final_wrs, n=4)[2]:.2%}
Max:     {max_wr:.2%}
Std Dev: {stdev_wr:.2%}
```

**Target Achievement Probabilities:**

| Outcome | Count | Probability |
|---------|-------|-------------|
| Below 60% | {target_counts['below_60']:,} | {target_counts['below_60']/num_simulations:.1%} |
| **60-65% (TARGET)** | **{target_counts['60_to_65']:,}** | **{prob_exact_60_65:.1%}** |
| Above 65% | {target_counts['above_65']:,} | {prob_exceed_65:.1%} |

**Key Findings:**

✅ **Probability of Reaching ≥60% WR:** {prob_reach_60_65:.1%}
✅ **Probability of Staying Within 60-65% Target:** {prob_exact_60_65:.1%}
✅ **Probability of Exceeding 65% WR:** {prob_exceed_65:.1%}

---

## Feasibility Assessment

"""

    # Determine feasibility
    if prob_reach_60_65 >= 0.75:
        verdict = "✅ **FEASIBLE** (High Confidence)"
        explanation = f"""
The 60-65% win rate target is **highly achievable** with {prob_reach_60_65:.0%} probability.

**Rationale:**
- Multiple independent improvements identified
- Most improvements have high probability of success (>75%)
- Expected win rate ({expected_wr:.1%}) falls within target range
- Even with some failures, median outcome ({median_wr:.1%}) exceeds 60%

**Recommendation:** PROCEED with implementation roadmap.
"""
    elif prob_reach_60_65 >= 0.50:
        verdict = "⚠️ **FEASIBLE** (Moderate Confidence)"
        explanation = f"""
The 60-65% win rate target is **achievable but not guaranteed** ({prob_reach_60_65:.0%} probability).

**Rationale:**
- Improvements exist, but success depends on effective implementation
- Some improvements have moderate certainty (<75% probability)
- Mean outcome ({mean_wr:.1%}) near lower bound of target range
- Risk of falling short if multiple improvements underperform

**Recommendation:** PROCEED with caution. Monitor closely after each change.
"""
    else:
        verdict = "❌ **NOT FEASIBLE** (Low Confidence)"
        explanation = f"""
The 60-65% win rate target is **unlikely to be achieved** (only {prob_reach_60_65:.0%} probability).

**Rationale:**
- Identified improvements insufficient to reach target
- Expected outcome ({expected_wr:.1%}) below 60% threshold
- High risk of disappointment if pursuing this target

**Recommendation:** Adjust target to {expected_wr - 0.02:.0%}-{expected_wr + 0.02:.0%}% (more realistic).
"""

    report += f"""{verdict}

{explanation}

---

## Alternative Targets (If 60-65% Infeasible)

"""

    # Calculate percentiles for alternative targets
    p10 = statistics.quantiles(final_wrs, n=10)[1]  # 10th percentile (conservative)
    p90 = statistics.quantiles(final_wrs, n=10)[8]  # 90th percentile (optimistic)

    report += f"""
**Conservative Target (10th Percentile):**
- Win Rate: {p10:.1%}
- Probability of Achieving: 90%
- Interpretation: Very safe bet, likely to exceed

**Realistic Target (Median):**
- Win Rate: {median_wr:.1%}
- Probability of Achieving: 50%
- Interpretation: Balanced target, 50/50 odds

**Optimistic Target (90th Percentile):**
- Win Rate: {p90:.1%}
- Probability of Achieving: 10%
- Interpretation: Stretch goal, requires everything to go right

---

## Recommendations

"""

    if prob_reach_60_65 >= 0.75:
        report += """
1. **PROCEED** with Top 10 priorities from synthesis report
2. **Prioritize** high-probability improvements first:
   - Fix state tracking bugs (100% necessary)
   - Remove trend filter (95% helps)
   - Disable underperforming agents (90% helps)
3. **Phase deployment:** Implement one improvement at a time, measure impact
4. **Monitor:** Track win rate after each change (20+ trades minimum)
5. **Iterate:** If early improvements work, continue with lower-probability optimizations

"""
    elif prob_reach_60_65 >= 0.50:
        report += """
1. **PROCEED** with caution - implement highest-confidence improvements only
2. **Lower expectations:** Target 58-62% range initially, then reassess
3. **Fail-fast:** If first 3 improvements don't yield gains, halt roadmap
4. **Focus on simplification:** Remove bad agents BEFORE adding optimizations
5. **Re-evaluate:** After 50 trades post-improvements, run this projection again

"""
    else:
        report += f"""
1. **ADJUST TARGET** to {expected_wr - 0.02:.0%}-{expected_wr + 0.02:.0%}% (more achievable)
2. **Focus on stability:** Fix bugs, reduce complexity, prevent catastrophic losses
3. **Accept current performance:** 58% WR is profitable (5% edge after fees)
4. **Investigate new strategies:** Current improvements insufficient for 60-65% leap
5. **Consider alternative approaches:** Machine learning, regime-specific strategies, etc.

"""

    report += f"""---

## Assumptions and Limitations

**Assumptions:**
1. Improvements are **independent** (no synergies or conflicts)
2. Probabilities reflect **researcher confidence**, not empirical certainty
3. Win rate deltas are **additive** (linear impact model)
4. Market conditions remain stable (no regime shifts)

**Limitations:**
1. Actual results may vary (simulation ≠ reality)
2. Implementation quality affects outcomes (bugs can negate improvements)
3. Some improvements interact (e.g., fewer agents + higher threshold may be redundant)
4. Monte Carlo assumes probability distributions are accurate (garbage in, garbage out)

**Validation Plan:**
- After each improvement, measure actual win rate change
- Compare to projected delta (did it work as expected?)
- Update probabilities for future projections
- Re-run simulation after 100 trades to recalibrate

---

## Conclusion

Based on {num_simulations:,} Monte Carlo simulations, the **60-65% win rate target** has a **{prob_reach_60_65:.0%} probability** of being achieved.

{verdict}

**Next Steps:**
1. Review Top 10 priorities in Research Synthesis Report
2. Implement high-confidence improvements first (>85% probability)
3. Measure win rate impact after each change (20+ trades minimum)
4. Adjust roadmap based on actual results vs projections

---

**Generated by:** `scripts/research/win_rate_projection.py`
**Persona:** Prof. Eleanor Nash (Game Theory Economist)
**Methodology:** Monte Carlo simulation with probabilistic improvement modeling
"""

    return report


def main():
    """Main execution."""
    print("=" * 80)
    print("US-RC-033: Win Rate Feasibility Analysis (60-65% Target)")
    print("Persona: Prof. Eleanor Nash (Game Theory Economist)")
    print("=" * 80)
    print()

    # Parameters
    current_wr = 0.58  # Current validated win rate
    num_simulations = 1000

    # Load improvements from research synthesis
    improvements = load_improvements()

    print(f"Current Win Rate: {current_wr:.1%}")
    print(f"Target Win Rate: 60-65%")
    print(f"Improvements Identified: {len(improvements)}")
    print(f"Simulations: {num_simulations:,}")
    print()

    # Run Monte Carlo simulation
    print("Running Monte Carlo simulation...")
    random.seed(42)  # For reproducibility
    final_wrs, target_counts = run_simulation(current_wr, improvements, num_simulations)
    print("✓ Simulation complete")
    print()

    # Generate report
    print("Generating report...")
    report = generate_report(current_wr, improvements, final_wrs, target_counts, num_simulations)

    # Save report
    output_dir = Path("reports/eleanor_nash")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "60_65_wr_feasibility.md"

    output_path.write_text(report)
    print(f"✓ Report saved: {output_path}")
    print()

    # Print summary
    prob_reach_60_65 = (target_counts["60_to_65"] + target_counts["above_65"]) / num_simulations
    mean_wr = sum(final_wrs) / len(final_wrs)

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Probability of reaching ≥60% WR: {prob_reach_60_65:.1%}")
    print(f"Expected final win rate: {mean_wr:.2%}")
    print()

    if prob_reach_60_65 >= 0.75:
        print("✅ VERDICT: Target is FEASIBLE (proceed with roadmap)")
        return 0
    elif prob_reach_60_65 >= 0.50:
        print("⚠️ VERDICT: Target is ACHIEVABLE but not guaranteed (proceed with caution)")
        return 0
    else:
        print("❌ VERDICT: Target is NOT FEASIBLE (adjust expectations)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
