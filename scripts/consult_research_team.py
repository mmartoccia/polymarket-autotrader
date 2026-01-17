#!/usr/bin/env python3
"""
Research Team Consultation Tool

Simulates consulting with the 9 research personas about threshold optimization.
Uses their documented methodologies and perspectives to provide recommendations.

Usage:
    python3 scripts/consult_research_team.py --question "Should we lower thresholds?" --data "70 skipped signals at 0.75-0.82"
"""

import argparse
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class ResearcherResponse:
    """Response from a research persona"""
    name: str
    role: str
    recommendation: str
    rationale: str
    confidence: str  # LOW, MEDIUM, HIGH
    data_needed: List[str]


class ResearchTeam:
    """Simulates the 9-persona research team"""
    
    def __init__(self):
        self.researchers = {
            'kenji': {
                'name': 'Dr. Kenji Nakamoto',
                'role': 'Data Forensics',
                'focus': 'Historical trade data, win rate validation'
            },
            'dmitri': {
                'name': 'Dmitri "The Hammer" Volkov',
                'role': 'System Reliability',
                'focus': 'Production stability, edge cases'
            },
            'sarah': {
                'name': 'Dr. Sarah Chen',
                'role': 'Statistical Analysis',
                'focus': 'Statistical significance, sample size'
            },
            'jimmy': {
                'name': 'James "Jimmy the Greek" Martinez',
                'role': 'Market Microstructure',
                'focus': 'Entry timing, price action'
            },
            'vic': {
                'name': 'Victor "Vic" Ramanujan',
                'role': 'Quantitative Strategy',
                'focus': 'Backtesting, shadow testing'
            },
            'rita': {
                'name': 'Colonel Rita "The Guardian" Stevens',
                'role': 'Risk Management',
                'focus': 'Drawdown protection, position sizing'
            },
            'amara': {
                'name': 'Dr. Amara Johnson',
                'role': 'Behavioral Finance',
                'focus': 'Psychology, discipline, bias'
            },
            'eleanor': {
                'name': 'Prof. Eleanor Nash',
                'role': 'Strategic Synthesis',
                'focus': 'Integration, trade-offs, decision framework'
            },
            'alex': {
                'name': 'Alex "Occam" Rousseau',
                'role': 'First Principles Engineer',
                'focus': 'Simplification, complexity reduction'
            }
        }
    
    def consult_on_threshold_lowering(self, skipped_count: int, 
                                       threshold_range: tuple,
                                       current_wr: float) -> List[ResearcherResponse]:
        """Get recommendations from all researchers on lowering thresholds"""
        
        responses = []
        
        # Dr. Kenji Nakamoto (Data Forensics)
        responses.append(ResearcherResponse(
            name="Dr. Kenji Nakamoto",
            role="Data Forensics",
            recommendation="SHADOW TEST FIRST",
            rationale=f"""Need to validate that {skipped_count} skipped signals would have been 
profitable. Check historical outcomes:
- What direction were they?
- Did market move in that direction?
- What was entry price vs final outcome?
- Were they clustered in specific regimes?

Current WR is {current_wr:.1%}. If skipped signals have >60% historical WR, 
lowering threshold could improve performance. But MUST verify with data first.""",
            confidence="HIGH",
            data_needed=[
                "Historical outcomes of skipped signals (WIN/LOSS)",
                "Direction distribution (UP vs DOWN)",
                "Entry price distribution",
                "Time-in-epoch when signals occurred"
            ]
        ))
        
        # Dmitri Volkov (System Reliability)
        responses.append(ResearcherResponse(
            name="Dmitri 'The Hammer' Volkov",
            role="System Reliability",
            recommendation="INCREMENTAL ROLLOUT",
            rationale=f"""Lowering threshold from 0.82 → 0.78 increases trade frequency by ~30-40%. 
System impact:
- More API calls (order placement)
- Higher gas costs (more transactions)
- Increased exposure (more simultaneous positions)

Recommend gradual approach:
1. Week 1: Lower to 0.80 (10% increase)
2. Week 2: If stable, lower to 0.78 (20% increase)
3. Monitor system load, API rate limits, error rates

Rollback plan: Revert to 0.82 if error rate >5% or WR drops >2%""",
            confidence="HIGH",
            data_needed=[
                "System resource usage (CPU, memory, API limits)",
                "Current error rate baseline",
                "Position concurrency limits"
            ]
        ))
        
        # Dr. Sarah Chen (Statistical Analysis)
        responses.append(ResearcherResponse(
            name="Dr. Sarah Chen",
            role="Statistical Analysis",
            recommendation="CALCULATE CONFIDENCE INTERVALS",
            rationale=f"""With {skipped_count} skipped signals, need statistical validation:

Current threshold: 0.82 (n={int(current_wr * 100)} trades, WR={current_wr:.1%})
Proposed threshold: 0.78 (projected n={int(current_wr * 100 + skipped_count//2)})

Key question: What's the WR of signals in 0.75-0.82 range?

If 0.75-0.82 signals have:
- WR >60%: LOWER threshold (adds positive edge)
- WR 53-60%: NEUTRAL (depends on risk tolerance)
- WR <53%: KEEP current (below breakeven)

Need 30+ samples in 0.75-0.82 range for significance.""",
            confidence="MEDIUM",
            data_needed=[
                "Win rate of signals in 0.75-0.82 range (historical)",
                "Sample size in that range",
                "Variance (are results consistent or noisy?)"
            ]
        ))
        
        # Jimmy Martinez (Market Microstructure)
        responses.append(ResearcherResponse(
            name="James 'Jimmy the Greek' Martinez",
            role="Market Microstructure",
            recommendation="CONTEXT MATTERS",
            rationale=f"""Not all skipped signals are equal. Need to analyze:

Entry Price Distribution:
- Cheap entries (<$0.15): Lower threshold OK (high WR)
- Expensive entries (>$0.25): Keep high threshold (low WR)

Timing Context:
- Late epoch (600-900s): Lower threshold OK (62% WR)
- Early epoch (0-300s): Keep high threshold (54% WR)

Regime Context:
- BULL/BEAR: Lower threshold OK (trend continuation)
- CHOPPY: Keep high threshold (noise, no edge)

Recommend: CONDITIONAL thresholds instead of global lowering.""",
            confidence="HIGH",
            data_needed=[
                "Entry price of skipped signals",
                "Time-in-epoch distribution",
                "Regime when signals occurred",
                "Direction alignment with regime"
            ]
        ))
        
        # Victor Ramanujan (Quantitative Strategy)
        responses.append(ResearcherResponse(
            name="Victor 'Vic' Ramanujan",
            role="Quantitative Strategy",
            recommendation="SHADOW TEST FOR 7 DAYS",
            rationale=f"""Use shadow trading system to test threshold variations:

Strategy Configs to Test:
1. 'threshold_0.80' (CONSENSUS=0.80, MIN_CONF=0.63)
2. 'threshold_0.78' (CONSENSUS=0.78, MIN_CONF=0.60)
3. 'threshold_0.75' (CONSENSUS=0.75, MIN_CONF=0.58)
4. 'conditional_entry' (0.78 if entry<$0.15, else 0.82)
5. 'conditional_timing' (0.78 if late epoch, else 0.82)

Run all 5 in parallel with live (0.82). After 50+ trades each:
- Compare WR: which beats live by ≥3%?
- Compare trade quality: entry price, timing distribution
- Statistical test: p-value <0.05 for significance

ONLY promote if shadow consistently beats live.""",
            confidence="HIGH",
            data_needed=[
                "Shadow trading database access",
                "7+ days of parallel testing",
                "Minimum 50 trades per shadow strategy"
            ]
        ))
        
        # Colonel Rita Stevens (Risk Management)
        responses.append(ResearcherResponse(
            name="Colonel Rita 'The Guardian' Stevens",
            role="Risk Management",
            recommendation="TIGHTEN RISK LIMITS FIRST",
            rationale=f"""Lowering threshold = more trades = more exposure = higher risk.

Before lowering threshold:
1. Validate current drawdown protection (30% limit working?)
2. Check position correlation limits (4 max, 8% same direction)
3. Verify daily loss limit (20% or $30)

If lowering threshold from 0.82 → 0.78:
- Trade frequency +30-40% (e.g., 5 → 7 trades/day)
- Max simultaneous positions: 4 → 6 (need to increase limit?)
- Daily capital at risk: $50 → $70 (acceptable?)

Recommend: Keep same risk limits, let position count adjust naturally. 
If hit limits too often, threshold is too low.""",
            confidence="HIGH",
            data_needed=[
                "Current position limit utilization",
                "Daily loss limit hit frequency",
                "Correlation limit hit frequency"
            ]
        ))
        
        # Dr. Amara Johnson (Behavioral Finance)
        responses.append(ResearcherResponse(
            name="Dr. Amara Johnson",
            role="Behavioral Finance",
            recommendation="AVOID REGRET BIAS",
            rationale=f"""Seeing {skipped_count} skipped signals creates psychological pressure:
"We're missing opportunities!"

But ask: Are we REALLY missing opportunities or avoiding losses?

Regret Bias Indicators:
- Lowering threshold after losing streak (reactive, not analytical)
- Focusing on missed winners, ignoring avoided losers
- Changing thresholds too frequently (<1 month apart)

Current threshold (0.82) was set Jan 16 based on research. 
Has market regime changed? Or are we just seeing normal variance?

Recommend: 
- Wait 2 weeks minimum after threshold change
- Collect 100+ trades at new threshold
- THEN evaluate (not after 20 trades when variance is high)""",
            confidence="MEDIUM",
            data_needed=[
                "When was threshold last changed?",
                "How many trades since last change?",
                "Is this request reactive (after losses) or proactive?"
            ]
        ))
        
        # Prof. Eleanor Nash (Strategic Synthesis)
        responses.append(ResearcherResponse(
            name="Prof. Eleanor Nash",
            role="Strategic Synthesis",
            recommendation="STRUCTURED EXPERIMENT",
            rationale=f"""Team consensus emerging: Shadow test is the right approach.

Decision Framework:
1. Data Collection (2-3 days)
   - Analyze historical skipped signals
   - Validate they would have been profitable
   - Jimmy: Check entry price, timing, regime context

2. Shadow Testing (7 days)
   - Vic: Run 5 threshold variations in parallel
   - Target: 50+ trades per variation
   - Measure: WR, trade quality, risk metrics

3. Statistical Analysis (1 day)
   - Sarah: Calculate significance (p<0.05)
   - Identify best performer (≥3% WR advantage)
   - Check consistency (not regime-dependent)

4. Production Deployment (if validated)
   - Dmitri: Incremental rollout (0.82 → 0.80 → 0.78)
   - Rita: Monitor risk limits
   - Rollback if WR drops >1%

Timeline: 10-14 days from decision to production""",
            confidence="HIGH",
            data_needed=[
                "Buy-in from all stakeholders",
                "Shadow trading system operational",
                "Monitoring dashboard ready"
            ]
        ))
        
        # Alex Rousseau (First Principles Engineer)
        responses.append(ResearcherResponse(
            name="Alex 'Occam' Rousseau",
            role="First Principles Engineer",
            recommendation="QUESTION THE PREMISE",
            rationale=f"""Before optimizing thresholds, ask: Are agents finding correct signals?

If agents identify correct direction but scores are too low:
- Problem: Agent WEIGHTS are miscalibrated (not threshold)
- Solution: Increase weights of high-performing agents
- Example: If RegimeAgent has 80% WR, increase its weight from 1.0 → 1.5

If agents identify wrong direction at high confidence:
- Problem: Agent LOGIC is broken (not threshold)
- Solution: Disable broken agents (we did this: TechAgent, SentimentAgent)

Threshold tuning is LAST resort. First:
1. Verify agent per-vote accuracy (which agents are right?)
2. Boost weights of accurate agents
3. Disable agents with <53% accuracy
4. THEN consider threshold if still skipping good signals

Lowering threshold = accepting lower-quality signals. 
Better to FIX signal quality first.""",
            confidence="HIGH",
            data_needed=[
                "Per-agent vote accuracy (when RegimeAgent says UP, is it UP?)",
                "Agent weight distribution",
                "Correlation matrix (are agents redundant?)"
            ]
        ))
        
        return responses
    
    def print_consultation_summary(self, responses: List[ResearcherResponse]):
        """Print formatted consultation summary"""
        print("\n" + "="*80)
        print("🎓 RESEARCH TEAM CONSULTATION SUMMARY")
        print("="*80)
        
        # Count recommendations
        recommendations = {}
        for r in responses:
            rec = r.recommendation.split()[0]  # First word
            recommendations[rec] = recommendations.get(rec, 0) + 1
        
        print("\n📊 Recommendation Breakdown:")
        for rec, count in sorted(recommendations.items(), key=lambda x: x[1], reverse=True):
            print(f"   {rec}: {count} researchers")
        
        print("\n" + "-"*80)
        
        for i, response in enumerate(responses, 1):
            print(f"\n{i}. {response.name} ({response.role})")
            print(f"   Recommendation: {response.recommendation}")
            print(f"   Confidence: {response.confidence}")
            print(f"\n   Rationale:")
            for line in response.rationale.split('\n'):
                if line.strip():
                    print(f"   {line}")
            
            if response.data_needed:
                print(f"\n   Data Needed:")
                for item in response.data_needed:
                    print(f"   - {item}")
            
            print("\n" + "-"*80)
        
        print("\n💡 CONSENSUS RECOMMENDATION:")
        print("""
The research team recommends a STRUCTURED EXPERIMENTAL APPROACH:

Phase 1: Data Validation (2-3 days)
- Analyze historical outcomes of skipped signals
- Verify they would have been profitable (>60% WR)
- Check entry price, timing, regime context

Phase 2: Shadow Testing (7 days)  
- Run 5 threshold variations (0.75, 0.78, 0.80 + conditionals)
- Collect 50+ trades per variation
- Measure WR, entry quality, risk metrics

Phase 3: Statistical Analysis (1 day)
- Calculate significance (p<0.05 required)
- Identify best performer (≥3% WR advantage over live)
- Validate consistency across regimes

Phase 4: Production Rollout (if validated)
- Incremental deployment (0.82 → 0.80 → 0.78)
- Monitor for 7 days at each level
- Rollback if WR drops >1%

ALTERNATIVE APPROACH (Alex Rousseau):
Before lowering threshold, try REWEIGHTING AGENTS:
- Boost weights of high-accuracy agents
- May improve signal quality without lowering bar
""")


def main():
    parser = argparse.ArgumentParser(description="Consult research team on threshold optimization")
    parser.add_argument('--skipped', type=int, default=70,
                        help='Number of skipped signals observed')
    parser.add_argument('--current-wr', type=float, default=0.58,
                        help='Current win rate (0-1)')
    parser.add_argument('--threshold-range', default='0.75-0.82',
                        help='Threshold range where signals were skipped')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🔍 CONSULTING RESEARCH TEAM ON THRESHOLD OPTIMIZATION")
    print("="*80)
    print(f"\nContext:")
    print(f"- Skipped signals: {args.skipped}")
    print(f"- Current WR: {args.current_wr:.1%}")
    print(f"- Threshold range: {args.threshold_range}")
    
    team = ResearchTeam()
    responses = team.consult_on_threshold_lowering(
        skipped_count=args.skipped,
        threshold_range=(0.75, 0.82),
        current_wr=args.current_wr
    )
    
    team.print_consultation_summary(responses)
    
    print("\n" + "="*80)
    print("✅ Consultation complete!")
    print("="*80)
    
    return 0


if __name__ == '__main__':
    exit(main())
