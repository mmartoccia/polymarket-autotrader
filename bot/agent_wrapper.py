#!/usr/bin/env python3
"""
Agent System Wrapper for Existing Bot

Provides a simple interface to integrate the 4-agent expert system
with the existing momentum_bot_v12.py without major refactoring.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents import TechAgent, RiskAgent, SentimentAgent, RegimeAgent, CandlestickAgent
from coordinator import DecisionEngine
from config import agent_config
import logging

log = logging.getLogger(__name__)


class AgentSystemWrapper:
    """
    Wrapper that integrates expert agents into existing bot.

    Usage in momentum_bot_v12.py:
        from bot.agent_wrapper import AgentSystemWrapper

        # Initialize once at startup
        agent_system = AgentSystemWrapper(
            consensus_threshold=0.40,
            enabled=True  # Set False for log-only mode
        )

        # In trading loop, replace hardcoded logic:
        should_trade, direction, confidence, reason = agent_system.make_decision(
            crypto=crypto,
            epoch=epoch,
            prices=prices,
            orderbook=orderbook,
            positions=positions,
            balance=balance,
            time_in_epoch=time_in_epoch,
            rsi=rsi_value,
            regime=current_regime,
            mode=trading_mode
        )

        if should_trade:
            size = agent_system.get_position_size(
                confidence=confidence,
                balance=balance,
                consecutive_losses=consecutive_losses
            )
            # Place order...
    """

    def __init__(self,
                 consensus_threshold: float = None,
                 min_confidence: float = None,
                 adaptive_weights: bool = None,
                 enabled: bool = None):
        """
        Initialize agent system.

        Args:
            consensus_threshold: Minimum weighted score to trade (uses config if None)
            min_confidence: Minimum average confidence (uses config if None)
            adaptive_weights: Enable performance-based weight tuning (uses config if None)
            enabled: If False, runs in LOG-ONLY mode (uses config if None)
        """
        # Load from config if not specified
        if consensus_threshold is None:
            consensus_threshold = agent_config.CONSENSUS_THRESHOLD
        if min_confidence is None:
            min_confidence = agent_config.MIN_CONFIDENCE
        if adaptive_weights is None:
            adaptive_weights = agent_config.ADAPTIVE_WEIGHTS
        if enabled is None:
            enabled = agent_config.AGENT_SYSTEM_ENABLED

        self.enabled = enabled

        # Initialize agents
        self.tech_agent = TechAgent(name="TechAgent", weight=1.0)
        self.sentiment_agent = SentimentAgent(name="SentimentAgent", weight=1.0)
        self.regime_agent = RegimeAgent(name="RegimeAgent", weight=1.0)
        self.candle_agent = CandlestickAgent()  # Has its own default name
        self.risk_agent = RiskAgent(name="RiskAgent", weight=1.0)

        # Initialize decision engine with 4 expert agents
        self.engine = DecisionEngine(
            agents=[self.tech_agent, self.sentiment_agent, self.regime_agent, self.candle_agent],
            veto_agents=[self.risk_agent],
            consensus_threshold=consensus_threshold,
            min_confidence=min_confidence,
            adaptive_weights=adaptive_weights
        )

        log.info("=" * 60)
        log.info("AGENT SYSTEM INITIALIZED - 4 AGENTS")
        log.info(f"  Mode: {'ENABLED' if enabled else 'LOG-ONLY'}")
        log.info(f"  Consensus Threshold: {consensus_threshold}")
        log.info(f"  Min Confidence: {min_confidence}")
        log.info(f"  Adaptive Weights: {adaptive_weights}")
        log.info(f"  Agents: Tech, Sentiment, Regime, Candlestick (+ Risk veto)")
        log.info("=" * 60)

    def make_decision(self,
                     crypto: str,
                     epoch: int,
                     prices: dict,
                     orderbook: dict,
                     positions: list,
                     balance: float,
                     time_in_epoch: int = 0,
                     rsi: float = 50.0,
                     regime: str = 'unknown',
                     mode: str = 'normal') -> tuple:
        """
        Make trading decision using agent consensus.

        Args:
            crypto: Crypto symbol (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            prices: Multi-exchange prices {'btc': 94350, 'eth': 3215, ...}
            orderbook: Current orderbook {'yes': {...}, 'no': {...}}
            positions: List of open positions
            balance: Current balance
            time_in_epoch: Seconds into epoch
            rsi: Current RSI value
            regime: Current market regime
            mode: Trading mode (normal, conservative, etc.)

        Returns:
            (should_trade, direction, confidence, reason)
            - should_trade: bool
            - direction: "Up", "Down", or None
            - confidence: float 0.0-1.0
            - reason: str (explanation)
        """
        # Prepare data for agents
        data = {
            'prices': prices,
            'orderbook': orderbook,
            'positions': positions,
            'balance': balance,
            'time_in_epoch': time_in_epoch,
            'rsi': rsi,
            'regime': regime,
            'mode': mode,
            'direction': None,  # Will be set if agents vote Up/Down
            'epoch': epoch
        }

        # Get decision from engine
        decision = self.engine.decide(crypto, epoch, data)

        # Log decision (always, even in log-only mode)
        self._log_decision(crypto, decision)

        # If not enabled, return False (log-only mode)
        if not self.enabled:
            log.info(f"  [LOG-ONLY] Would have traded: {decision.should_trade}")
            return False, None, 0.0, "Log-only mode"

        return (
            decision.should_trade,
            decision.direction,
            decision.confidence,
            decision.reason
        )

    def get_position_size(self,
                         confidence: float,
                         balance: float,
                         consecutive_losses: int = 0) -> float:
        """
        Calculate position size using RiskAgent.

        Args:
            confidence: Signal confidence (0.0-1.0)
            balance: Current balance
            consecutive_losses: Number of consecutive losses

        Returns:
            Position size in USD
        """
        return self.risk_agent.calculate_position_size(
            signal_strength=confidence,
            balance=balance,
            consecutive_losses=consecutive_losses
        )

    def record_outcome(self,
                      crypto: str,
                      epoch: int,
                      predicted_direction: str,
                      actual_direction: str,
                      regime: str = 'unknown'):
        """
        Record trade outcome for performance tracking.

        Args:
            crypto: Crypto symbol
            epoch: Epoch timestamp
            predicted_direction: What agents predicted
            actual_direction: What actually happened
            regime: Market regime at the time
        """
        # This would be called after epoch resolution
        # to update agent performance metrics

        # Note: Would need to retrieve the original decision
        # For now, just log it
        log.info(
            f"[{crypto.upper()}] Trade outcome: "
            f"Predicted {predicted_direction} | Actual {actual_direction} | "
            f"{'✅' if predicted_direction == actual_direction else '❌'}"
        )

    def get_performance_report(self) -> dict:
        """Get performance metrics for all agents."""
        return self.engine.get_performance_report()

    def adjust_consensus_threshold(self, new_threshold: float):
        """
        Dynamically adjust consensus threshold.

        Higher = more selective (fewer trades, higher confidence)
        Lower = more aggressive (more trades, lower confidence)

        Args:
            new_threshold: New threshold (0.5-0.9 recommended)
        """
        self.engine.adjust_consensus_threshold(new_threshold)
        log.info(f"Consensus threshold adjusted to {new_threshold}")

    def _log_decision(self, crypto: str, decision):
        """Log decision details for monitoring."""
        log.info(f"[{crypto.upper()}] Agent Decision:")
        log.info(f"  Should Trade: {decision.should_trade}")
        log.info(f"  Direction: {decision.direction}")
        log.info(f"  Confidence: {decision.confidence:.2%}")
        log.info(f"  Weighted Score: {decision.weighted_score:.3f}")
        log.info(f"  Vetoed: {decision.vetoed}")

        if decision.prediction:
            log.info(f"  Vote Breakdown: Up={decision.prediction.up_votes} "
                    f"Down={decision.prediction.down_votes} "
                    f"Neutral={decision.prediction.neutral_votes}")

        log.info(f"  Reason: {decision.reason}")


# Example usage
if __name__ == "__main__":
    import time

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize wrapper
    wrapper = AgentSystemWrapper(
        consensus_threshold=0.65,
        enabled=True
    )

    # Simulate a decision
    test_data = {
        'btc': 94350.00,
        'eth': 3215.00,
        'sol': 144.15,
        'xrp': 2.14
    }

    orderbook = {
        'yes': {'price': 0.85, 'ask': 0.85},
        'no': {'price': 0.15, 'ask': 0.15}
    }

    should_trade, direction, confidence, reason = wrapper.make_decision(
        crypto='btc',
        epoch=int(time.time() // 900) * 900,
        prices=test_data,
        orderbook=orderbook,
        positions=[],
        balance=150.0,
        time_in_epoch=300,
        rsi=65.0,
        regime='sideways',
        mode='normal'
    )

    print(f"\nFinal Decision:")
    print(f"  Should Trade: {should_trade}")
    print(f"  Direction: {direction}")
    print(f"  Confidence: {confidence:.2%}")

    if should_trade:
        size = wrapper.get_position_size(confidence, 150.0)
        print(f"  Position Size: ${size:.2f}")
