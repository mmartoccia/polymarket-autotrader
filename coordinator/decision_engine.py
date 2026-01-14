#!/usr/bin/env python3
"""
Decision Engine for Multi-Expert Trading System

Orchestrates expert agents, aggregates their votes, and makes final
trade execution decisions with risk management integration.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent, VetoAgent, Vote
from coordinator.vote_aggregator import VoteAggregator, AggregatePrediction, calculate_agent_weights
from config.agent_config import CONSENSUS_THRESHOLD, MIN_CONFIDENCE

log = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    """
    Final trade decision from the decision engine.

    Contains all information needed to execute (or skip) a trade.
    """
    # Decision outcome
    should_trade: bool
    direction: Optional[str]  # "Up" or "Down" (if should_trade=True)
    reason: str  # Human-readable explanation

    # Consensus details
    prediction: Optional[AggregatePrediction]
    weighted_score: float
    confidence: float

    # Risk validation
    vetoed: bool = False
    veto_reasons: List[str] = None

    # Execution metadata
    crypto: str = ""
    epoch: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.veto_reasons is None:
            self.veto_reasons = []
        if self.timestamp == 0.0:
            self.timestamp = datetime.now().timestamp()

    def to_dict(self) -> dict:
        """Export for logging."""
        return {
            'should_trade': self.should_trade,
            'direction': self.direction,
            'reason': self.reason,
            'weighted_score': self.weighted_score,
            'confidence': self.confidence,
            'vetoed': self.vetoed,
            'veto_reasons': self.veto_reasons,
            'crypto': self.crypto,
            'epoch': self.epoch,
            'timestamp': self.timestamp,
            'prediction': self.prediction.to_dict() if self.prediction else None
        }


class DecisionEngine:
    """
    Orchestrates expert agents and makes final trade decisions.

    Workflow:
    1. Query all expert agents for votes
    2. Aggregate votes using weighted consensus
    3. Check veto agents for risk blocks
    4. Make final trade decision
    5. Track performance and adjust weights
    """

    def __init__(self,
                 agents: List[BaseAgent],
                 veto_agents: Optional[List[VetoAgent]] = None,
                 consensus_threshold: float = 0.70,
                 min_confidence: float = 0.60,
                 adaptive_weights: bool = True):
        """
        Initialize decision engine.

        Args:
            agents: List of expert agents (Tech, Sentiment, Regime, etc.)
            veto_agents: List of veto agents (Risk, etc.)
            consensus_threshold: Minimum weighted score to trade
            min_confidence: Minimum average confidence to trade
            adaptive_weights: Whether to adjust agent weights based on performance
        """
        self.agents = agents
        self.veto_agents = veto_agents or []
        self.consensus_threshold = consensus_threshold
        self.min_confidence = min_confidence
        self.adaptive_weights = adaptive_weights

        self.aggregator = VoteAggregator(
            consensus_threshold=consensus_threshold,
            min_agents=len(agents),
            enable_vetoes=True
        )

        self.log = logging.getLogger(f"{__name__}.DecisionEngine")

        # Initialize agent weights (start equal)
        self.agent_weights = {agent.name: agent.weight for agent in agents}

        self.log.info(f"Initialized with {len(agents)} experts + {len(self.veto_agents)} veto agents")

    def decide(self, crypto: str, epoch: int, data: dict) -> TradeDecision:
        """
        Make trading decision for given crypto/epoch.

        Args:
            crypto: Crypto symbol (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            data: Shared data context:
                - prices: Multi-exchange price data
                - orderbook: Current orderbook
                - positions: Open positions
                - balance: Current balance
                - regime: Current market regime
                - historical: Past trade data

        Returns:
            TradeDecision with should_trade flag and reasoning
        """
        self.log.info(f"Making decision for {crypto.upper()} epoch {epoch}")

        # Step 1: Query all expert agents
        votes = self._collect_votes(crypto, epoch, data)

        if not votes:
            return TradeDecision(
                should_trade=False,
                direction=None,
                reason="No votes collected from expert agents",
                prediction=None,
                weighted_score=0.0,
                confidence=0.0,
                crypto=crypto,
                epoch=epoch
            )

        # Step 2: Validate votes
        is_valid, error_msg = self.aggregator.validate_votes(votes)
        if not is_valid:
            self.log.warning(f"Vote validation failed: {error_msg}")
            return TradeDecision(
                should_trade=False,
                direction=None,
                reason=f"Invalid votes: {error_msg}",
                prediction=None,
                weighted_score=0.0,
                confidence=0.0,
                crypto=crypto,
                epoch=epoch
            )

        # Step 3: Update agent weights if adaptive
        if self.adaptive_weights:
            regime = data.get('regime', 'unknown')
            performances = {agent.name: agent.performance for agent in self.agents}
            self.agent_weights = calculate_agent_weights(performances, regime)

        # Step 4: Aggregate votes
        prediction = self.aggregator.aggregate_votes(votes, self.agent_weights)

        # Log vote summary
        summary = self.aggregator.get_vote_summary(prediction)
        self.log.info(f"\n{summary}")

        # Step 5: QUALITY-CONTROLLED TRADING
        # Trade only when both consensus (weighted_score) and confidence meet minimums:
        # - CONSENSUS_THRESHOLD = 0.40 (40% weighted consensus required)
        # - MIN_CONFIDENCE = 0.40 (40% average agent confidence required)
        #
        # Rationale: Low-confidence trades (18-33%) had 0% win rate in testing.
        # Quality control prevents weak signals from executing and losing money.
        #
        # Position sizing will scale with weighted_score:
        # - 0.40-0.50: 70% of max position (moderate signal)
        # - 0.50-0.60: 85% of max position (good signal)
        # - 0.60+:     100% of max position (strong signal)
        #
        # This ensures only quality trades execute while managing position risk

        # Check if consensus meets minimum threshold
        if prediction.weighted_score < CONSENSUS_THRESHOLD:
            return TradeDecision(
                should_trade=False,
                direction=None,
                reason=f"Consensus too weak to trade ({prediction.weighted_score:.3f} < {CONSENSUS_THRESHOLD})",
                prediction=prediction,
                weighted_score=prediction.weighted_score,
                confidence=prediction.confidence,
                crypto=crypto,
                epoch=epoch
            )

        # Check if average agent confidence meets minimum
        if prediction.confidence < MIN_CONFIDENCE:
            return TradeDecision(
                should_trade=False,
                direction=None,
                reason=f"Average confidence {prediction.confidence:.1%} below minimum {MIN_CONFIDENCE:.1%}",
                prediction=prediction,
                weighted_score=prediction.weighted_score,
                confidence=prediction.confidence,
                crypto=crypto,
                epoch=epoch
            )

        # Step 7: Check for Neutral consensus (no trade)
        if prediction.direction == "Neutral":
            return TradeDecision(
                should_trade=False,
                direction=None,
                reason="Expert consensus is Neutral (no clear direction)",
                prediction=prediction,
                weighted_score=prediction.weighted_score,
                confidence=prediction.confidence,
                crypto=crypto,
                epoch=epoch
            )

        # Step 8: Check veto agents
        # Add prediction data to context for veto checks
        veto_data = {
            **data,  # Include all original data
            'direction': prediction.direction,
            'weighted_score': prediction.weighted_score,
            'confidence': prediction.confidence
        }

        is_vetoed, veto_reasons = self.aggregator.check_vetoes(
            self.veto_agents,
            crypto,
            veto_data
        )

        if is_vetoed:
            return TradeDecision(
                should_trade=False,
                direction=None,
                reason=f"Trade vetoed by risk agents",
                prediction=prediction,
                weighted_score=prediction.weighted_score,
                confidence=prediction.confidence,
                vetoed=True,
                veto_reasons=veto_reasons,
                crypto=crypto,
                epoch=epoch
            )

        # Step 9: APPROVED - Execute trade
        reason = self._build_approval_reason(prediction)

        self.log.info(f"✅ APPROVED: {crypto.upper()} {prediction.direction} | {reason}")

        return TradeDecision(
            should_trade=True,
            direction=prediction.direction,
            reason=reason,
            prediction=prediction,
            weighted_score=prediction.weighted_score,
            confidence=prediction.confidence,
            crypto=crypto,
            epoch=epoch
        )

    def _collect_votes(self, crypto: str, epoch: int, data: dict) -> List[Vote]:
        """
        Query all expert agents for their votes.

        Args:
            crypto: Crypto symbol
            epoch: Current epoch
            data: Trading context

        Returns:
            List of Vote objects
        """
        votes = []

        for agent in self.agents:
            try:
                vote = agent.analyze(crypto, epoch, data)

                if vote:
                    votes.append(vote)
                    self.log.debug(
                        f"{agent.name}: {vote.direction} "
                        f"(C:{vote.confidence:.2f} Q:{vote.quality:.2f})"
                    )
                else:
                    self.log.warning(f"{agent.name} returned no vote")

            except Exception as e:
                self.log.error(f"Error getting vote from {agent.name}: {e}")

        self.log.info(f"Collected {len(votes)}/{len(self.agents)} votes")

        return votes

    def _build_approval_reason(self, prediction: AggregatePrediction) -> str:
        """
        Build human-readable reason for trade approval.

        Args:
            prediction: AggregatePrediction that was approved

        Returns:
            Formatted string explaining the decision
        """
        agent_summary = ", ".join([
            f"{v.agent_name}({v.confidence:.0%})"
            for v in prediction.votes
            if v.direction == prediction.direction
        ])

        reason = (
            f"{prediction.direction} consensus from {prediction.total_agents} experts | "
            f"Score: {prediction.weighted_score:.3f} | "
            f"Confidence: {prediction.confidence:.1%} | "
            f"Agreement: {prediction.agreement_rate:.0%} | "
            f"Votes: {agent_summary}"
        )

        return reason

    def record_outcome(self, decision: TradeDecision, actual_direction: str, regime: str = 'unknown'):
        """
        Record trade outcome and update agent performance.

        Args:
            decision: The TradeDecision that was executed
            actual_direction: What actually happened ("Up" or "Down")
            regime: Market regime at the time
        """
        if not decision.prediction:
            return

        # Update each agent's performance
        for vote in decision.prediction.votes:
            agent = self._get_agent_by_name(vote.agent_name)

            if agent:
                agent.record_outcome(vote, actual_direction, regime)
            else:
                self.log.warning(f"Could not find agent {vote.agent_name} to record outcome")

        self.log.info(
            f"Recorded outcome for {decision.crypto.upper()}: "
            f"Predicted {decision.direction} | Actual {actual_direction}"
        )

    def _get_agent_by_name(self, name: str) -> Optional[BaseAgent]:
        """Find agent by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def get_performance_report(self) -> dict:
        """
        Generate performance report for all agents.

        Returns:
            Dict with per-agent performance metrics
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'agents': {},
            'weights': self.agent_weights.copy()
        }

        for agent in self.agents:
            report['agents'][agent.name] = agent.get_performance_summary()

        return report

    def adjust_consensus_threshold(self, new_threshold: float):
        """
        Dynamically adjust consensus threshold.

        Useful for regime-specific tuning:
        - Bull/Bear: Lower threshold (more trades)
        - Sideways/Volatile: Higher threshold (selective trades)

        Args:
            new_threshold: New consensus threshold (0.0 to 1.0)
        """
        old_threshold = self.consensus_threshold
        self.consensus_threshold = new_threshold
        self.aggregator.consensus_threshold = new_threshold

        self.log.info(
            f"Consensus threshold adjusted: {old_threshold:.3f} → {new_threshold:.3f}"
        )

    def add_agent(self, agent: BaseAgent):
        """
        Add a new expert agent to the system.

        Args:
            agent: New agent to add
        """
        if agent not in self.agents:
            self.agents.append(agent)
            self.agent_weights[agent.name] = agent.weight
            self.log.info(f"Added agent: {agent.name} (weight: {agent.weight})")

    def remove_agent(self, agent_name: str):
        """
        Remove an expert agent from the system.

        Args:
            agent_name: Name of agent to remove
        """
        self.agents = [a for a in self.agents if a.name != agent_name]
        self.agent_weights.pop(agent_name, None)
        self.log.info(f"Removed agent: {agent_name}")
