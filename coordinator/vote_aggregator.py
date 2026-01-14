#!/usr/bin/env python3
"""
Vote Aggregator for Multi-Expert Trading System

Aggregates votes from expert agents using weighted consensus.
Handles veto checks, direction determination, and threshold validation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import logging
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from agents.base_agent import Vote, VetoAgent

log = logging.getLogger(__name__)


@dataclass
class AggregatePrediction:
    """
    Aggregated prediction from multiple expert agents.

    Combines individual votes into a consensus prediction with
    weighted scoring and confidence metrics.
    """
    direction: str  # "Up", "Down", or "Neutral"
    weighted_score: float  # Total weighted score
    confidence: float  # Average confidence across votes
    quality: float  # Average quality across votes

    # Vote breakdown
    up_votes: int
    down_votes: int
    neutral_votes: int

    # Agent participation
    total_agents: int
    participating_agents: List[str]

    # Individual votes for transparency
    votes: List[Vote] = field(default_factory=list)

    # Consensus metrics
    agreement_rate: float = 0.0  # % of agents agreeing on direction
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> dict:
        """Export for logging and analysis."""
        return {
            'direction': self.direction,
            'weighted_score': self.weighted_score,
            'confidence': self.confidence,
            'quality': self.quality,
            'up_votes': self.up_votes,
            'down_votes': self.down_votes,
            'neutral_votes': self.neutral_votes,
            'total_agents': self.total_agents,
            'participating_agents': self.participating_agents,
            'agreement_rate': self.agreement_rate,
            'timestamp': self.timestamp,
            'votes': [v.to_dict() for v in self.votes]
        }


class VoteAggregator:
    """
    Aggregates votes from expert agents using weighted consensus.

    Core voting formula:
        Total Score = Σ(confidence × quality × agent_weight)

    Direction is determined by:
        - Up if up_score > down_score
        - Down if down_score > up_score
        - Neutral if scores are equal or below threshold
    """

    def __init__(self,
                 consensus_threshold: float = 0.70,
                 min_agents: int = 2,
                 enable_vetoes: bool = True):
        """
        Initialize vote aggregator.

        Args:
            consensus_threshold: Minimum weighted score to take action
            min_agents: Minimum number of agents required for consensus
            enable_vetoes: Whether veto agents can block trades
        """
        self.consensus_threshold = consensus_threshold
        self.min_agents = min_agents
        self.enable_vetoes = enable_vetoes
        self.log = logging.getLogger(f"{__name__}.VoteAggregator")

    def aggregate_votes(self,
                       votes: List[Vote],
                       weights: Dict[str, float]) -> AggregatePrediction:
        """
        Aggregate expert votes using weighted consensus.

        Args:
            votes: List of Vote objects from expert agents
            weights: Dict mapping agent_name → weight multiplier

        Returns:
            AggregatePrediction with consensus direction and scores
        """
        if not votes:
            self.log.warning("No votes to aggregate")
            return self._empty_prediction()

        if len(votes) < self.min_agents:
            self.log.warning(f"Only {len(votes)} agents voted (min: {self.min_agents})")

        # Filter votes below minimum individual confidence (quality control)
        MIN_INDIVIDUAL_CONFIDENCE = 0.30
        valid_votes = [v for v in votes if v.confidence >= MIN_INDIVIDUAL_CONFIDENCE]

        # Check if we have enough high-quality votes
        if len(valid_votes) < 2:
            self.log.warning(
                f"Only {len(valid_votes)} agents meet {MIN_INDIVIDUAL_CONFIDENCE:.0%} confidence threshold "
                f"(filtered {len(votes) - len(valid_votes)} low-confidence votes)"
            )
            return self._empty_prediction()

        # Use filtered votes for aggregation
        votes = valid_votes

        # Count votes by direction
        up_votes = [v for v in votes if v.direction == "Up"]
        down_votes = [v for v in votes if v.direction == "Down"]
        neutral_votes = [v for v in votes if v.direction == "Neutral"]

        # Calculate weighted scores for each direction
        up_score = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in up_votes)
        down_score = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in down_votes)
        neutral_score = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in neutral_votes)

        # Determine winning direction
        if up_score > down_score and up_score > neutral_score:
            direction = "Up"
            weighted_score = up_score
            majority_votes = up_votes
        elif down_score > up_score and down_score > neutral_score:
            direction = "Down"
            weighted_score = down_score
            majority_votes = down_votes
        else:
            direction = "Neutral"
            weighted_score = neutral_score
            majority_votes = neutral_votes

        # Calculate consensus metrics
        avg_confidence = sum(v.confidence for v in majority_votes) / max(len(majority_votes), 1)
        avg_quality = sum(v.quality for v in majority_votes) / max(len(majority_votes), 1)
        agreement_rate = len(majority_votes) / len(votes)

        prediction = AggregatePrediction(
            direction=direction,
            weighted_score=weighted_score,
            confidence=avg_confidence,
            quality=avg_quality,
            up_votes=len(up_votes),
            down_votes=len(down_votes),
            neutral_votes=len(neutral_votes),
            total_agents=len(votes),
            participating_agents=[v.agent_name for v in votes],
            votes=votes,
            agreement_rate=agreement_rate
        )

        self.log.info(
            f"Aggregated {len(votes)} votes: {direction} "
            f"(score: {weighted_score:.3f}, agreement: {agreement_rate:.1%})"
        )

        return prediction

    def meets_threshold(self, prediction: AggregatePrediction) -> bool:
        """
        Check if weighted score exceeds consensus threshold.

        Args:
            prediction: AggregatePrediction to validate

        Returns:
            True if score meets threshold, False otherwise
        """
        meets = prediction.weighted_score >= self.consensus_threshold

        if not meets:
            self.log.info(
                f"Consensus not met: {prediction.weighted_score:.3f} < {self.consensus_threshold:.3f}"
            )

        return meets

    def check_vetoes(self,
                    veto_agents: List[VetoAgent],
                    crypto: str,
                    data: dict) -> Tuple[bool, List[str]]:
        """
        Check if any veto agents block the trade.

        Args:
            veto_agents: List of VetoAgent instances
            crypto: Crypto symbol being traded
            data: Trading context data

        Returns:
            (is_vetoed, reasons): (True, [reasons]) if blocked, (False, []) if allowed
        """
        if not self.enable_vetoes:
            return False, []

        veto_reasons = []

        for agent in veto_agents:
            should_veto, reason = agent.can_veto(crypto, data)

            if should_veto:
                veto_reasons.append(f"{agent.name}: {reason}")
                self.log.warning(f"❌ VETO by {agent.name}: {reason}")

        is_vetoed = len(veto_reasons) > 0

        if is_vetoed:
            self.log.warning(f"Trade VETOED by {len(veto_reasons)} agent(s)")

        return is_vetoed, veto_reasons

    def determine_direction(self, votes: List[Vote]) -> str:
        """
        Calculate final direction based on simple vote majority.

        This is a simpler alternative to weighted aggregation.
        Useful for sanity checks or fallback logic.

        Args:
            votes: List of Vote objects

        Returns:
            "Up", "Down", or "Neutral"
        """
        if not votes:
            return "Neutral"

        up_count = sum(1 for v in votes if v.direction == "Up")
        down_count = sum(1 for v in votes if v.direction == "Down")

        if up_count > down_count:
            return "Up"
        elif down_count > up_count:
            return "Down"
        else:
            return "Neutral"

    def validate_votes(self, votes: List[Vote]) -> Tuple[bool, str]:
        """
        Validate that votes are properly formed.

        Args:
            votes: List of Vote objects to validate

        Returns:
            (is_valid, error_message)
        """
        if not votes:
            return False, "No votes provided"

        if len(votes) < self.min_agents:
            return False, f"Only {len(votes)} votes (min: {self.min_agents})"

        # Check for duplicate agents
        agent_names = [v.agent_name for v in votes]
        if len(agent_names) != len(set(agent_names)):
            return False, "Duplicate votes from same agent"

        # Validate vote structure (already validated in __post_init__, but double-check)
        for vote in votes:
            if vote.direction not in ["Up", "Down", "Neutral"]:
                return False, f"Invalid direction: {vote.direction}"

            if not (0.0 <= vote.confidence <= 1.0):
                return False, f"Invalid confidence: {vote.confidence}"

            if not (0.0 <= vote.quality <= 1.0):
                return False, f"Invalid quality: {vote.quality}"

        return True, ""

    def _empty_prediction(self) -> AggregatePrediction:
        """Create empty prediction for error cases."""
        return AggregatePrediction(
            direction="Neutral",
            weighted_score=0.0,
            confidence=0.0,
            quality=0.0,
            up_votes=0,
            down_votes=0,
            neutral_votes=0,
            total_agents=0,
            participating_agents=[],
            votes=[],
            agreement_rate=0.0
        )

    def get_vote_summary(self, prediction: AggregatePrediction) -> str:
        """
        Generate human-readable summary of voting results.

        Args:
            prediction: AggregatePrediction to summarize

        Returns:
            Formatted string with vote breakdown
        """
        summary = f"""
╔══════════════════════════════════════════════════════════════╗
║                     VOTE AGGREGATION SUMMARY                 ║
╠══════════════════════════════════════════════════════════════╣
║ Direction: {prediction.direction:8s}                                    ║
║ Weighted Score: {prediction.weighted_score:.3f}                                  ║
║ Confidence: {prediction.confidence:.1%}                                    ║
║ Quality: {prediction.quality:.1%}                                       ║
║                                                              ║
║ Vote Breakdown:                                              ║
║   Up: {prediction.up_votes:2d} | Down: {prediction.down_votes:2d} | Neutral: {prediction.neutral_votes:2d}              ║
║                                                              ║
║ Participating Agents ({prediction.total_agents}):                                ║
"""

        for vote in prediction.votes:
            direction_arrow = "⬆️" if vote.direction == "Up" else "⬇️" if vote.direction == "Down" else "➡️"
            summary += f"║   {direction_arrow} {vote.agent_name:12s} - C:{vote.confidence:.2f} Q:{vote.quality:.2f}          ║\n"

        summary += f"""║                                                              ║
║ Agreement Rate: {prediction.agreement_rate:.1%}                                   ║
║ Threshold: {self.consensus_threshold:.3f} {'✅ MET' if prediction.weighted_score >= self.consensus_threshold else '❌ NOT MET'}                        ║
╚══════════════════════════════════════════════════════════════╝
"""

        return summary


def calculate_agent_weights(performances: Dict[str, 'AgentPerformance'],
                           regime: str = 'unknown') -> Dict[str, float]:
    """
    Calculate agent weights based on historical performance.

    Agents with better accuracy get higher weights.
    Can be adjusted per market regime.

    Args:
        performances: Dict mapping agent_name → AgentPerformance
        regime: Current market regime ('bull', 'bear', 'sideways', 'unknown')

    Returns:
        Dict mapping agent_name → weight (0.5 to 1.5)
    """
    weights = {}

    for agent_name, perf in performances.items():
        # Base weight on overall accuracy
        accuracy = perf.accuracy()

        # Regime-specific adjustment
        if regime != 'unknown':
            regime_accuracy = perf.regime_accuracy(regime)
            if perf.total_votes > 10:  # Only adjust if enough data
                accuracy = 0.7 * accuracy + 0.3 * regime_accuracy

        # Weight formula: Scale from 0.5 to 1.5 based on accuracy
        # 50% accuracy = 0.5 weight
        # 75% accuracy = 1.0 weight (neutral)
        # 90% accuracy = 1.5 weight (boosted)
        if accuracy >= 0.50:
            weight = 0.5 + (accuracy - 0.50) * 2.5
        else:
            weight = 0.5  # Minimum weight for poor performers

        weights[agent_name] = min(max(weight, 0.5), 1.5)  # Clamp to [0.5, 1.5]

    return weights
