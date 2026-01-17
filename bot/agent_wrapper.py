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
from agents.time_pattern_agent import TimePatternAgent
from agents.gambler_agent import GamblerAgent
from agents.voting.orderbook_agent import OrderBookAgent
from agents.voting.funding_rate_agent import FundingRateAgent
from agents.voting.streak_agent import StreakAgent
from coordinator import DecisionEngine
from config import agent_config
from config.agent_config import get_enabled_agents
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
                 enabled: bool = None,
                 agent_weights: dict = None,
                 include_time_pattern: bool = None):
        """
        Initialize agent system.

        Args:
            consensus_threshold: Minimum weighted score to trade (uses config if None)
            min_confidence: Minimum average confidence (uses config if None)
            adaptive_weights: Enable performance-based weight tuning (uses config if None)
            enabled: If False, runs in LOG-ONLY mode (uses config if None)
            agent_weights: Dict of agent weights (e.g., {'TechAgent': 1.0, 'TimePatternAgent': 0.5})
            include_time_pattern: Whether to include TimePatternAgent (auto-detected from agent_weights if None)
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

        # Determine agent weights - load from config if not specified
        if agent_weights is None:
            agent_weights = agent_config.AGENT_WEIGHTS

        # Auto-detect if TimePatternAgent should be included
        if include_time_pattern is None:
            include_time_pattern = 'TimePatternAgent' in agent_weights and agent_weights['TimePatternAgent'] > 0

        # Get enabled agents from config
        enabled_agents = get_enabled_agents()

        # Initialize core agents (only if enabled)
        agents = []
        agent_names = []

        if 'TechAgent' in enabled_agents:
            self.tech_agent = TechAgent(name="TechAgent", weight=agent_weights.get('TechAgent', 1.0))
            agents.append(self.tech_agent)
            agent_names.append("Tech")
        else:
            self.tech_agent = None

        if 'SentimentAgent' in enabled_agents:
            self.sentiment_agent = SentimentAgent(name="SentimentAgent", weight=agent_weights.get('SentimentAgent', 1.0))
            agents.append(self.sentiment_agent)
            agent_names.append("Sentiment")
        else:
            self.sentiment_agent = None

        if 'RegimeAgent' in enabled_agents:
            self.regime_agent = RegimeAgent(name="RegimeAgent", weight=agent_weights.get('RegimeAgent', 1.0))
            agents.append(self.regime_agent)
            agent_names.append("Regime")
        else:
            self.regime_agent = None

        if 'CandlestickAgent' in enabled_agents:
            self.candle_agent = CandlestickAgent()  # Has its own default name
            agents.append(self.candle_agent)
            agent_names.append("Candlestick")
        else:
            self.candle_agent = None

        # Initialize veto agents (only if enabled)
        veto_agents = []
        veto_names = []

        if 'RiskAgent' in enabled_agents:
            self.risk_agent = RiskAgent(name="RiskAgent", weight=1.0)
            veto_agents.append(self.risk_agent)
            veto_names.append("Risk")
        else:
            self.risk_agent = None

        if 'GamblerAgent' in enabled_agents:
            self.gambler_agent = GamblerAgent(name="GamblerAgent", weight=1.0)
            veto_agents.append(self.gambler_agent)
            veto_names.append("Gambler")
        else:
            self.gambler_agent = None

        # Optionally add TimePatternAgent (if enabled)
        if include_time_pattern and 'TimePatternAgent' in enabled_agents:
            self.time_pattern_agent = TimePatternAgent(
                name="TimePatternAgent",
                weight=agent_weights.get('TimePatternAgent', 1.0)
            )
            agents.append(self.time_pattern_agent)
            agent_names.append("TimePattern")
        else:
            self.time_pattern_agent = None

        # Add OrderBookAgent if configured and enabled
        if ('OrderBookAgent' in agent_weights and agent_weights['OrderBookAgent'] > 0
            and 'OrderBookAgent' in enabled_agents):
            self.orderbook_agent = OrderBookAgent(
                name="OrderBookAgent",
                weight=agent_weights.get('OrderBookAgent', 1.0)
            )
            agents.append(self.orderbook_agent)
            agent_names.append("OrderBook")
        else:
            self.orderbook_agent = None

        # Add FundingRateAgent if configured and enabled
        if ('FundingRateAgent' in agent_weights and agent_weights['FundingRateAgent'] > 0
            and 'FundingRateAgent' in enabled_agents):
            self.funding_rate_agent = FundingRateAgent(
                name="FundingRateAgent",
                weight=agent_weights.get('FundingRateAgent', 1.0)
            )
            agents.append(self.funding_rate_agent)
            agent_names.append("FundingRate")
        else:
            self.funding_rate_agent = None

        # Add StreakAgent if configured and enabled (mean reversion after consecutive same-direction)
        if ('StreakAgent' in agent_weights and agent_weights['StreakAgent'] > 0
            and 'StreakAgent' in enabled_agents):
            self.streak_agent = StreakAgent()
            agents.append(self.streak_agent)
            agent_names.append("Streak")
        else:
            self.streak_agent = None

        # Build summary
        agent_count = f"{len(agents)} VOTING AGENTS"
        agent_list = ", ".join(agent_names) if agent_names else "None"

        if veto_names:
            veto_list = ", ".join(veto_names)
            full_summary = f"{agent_list} (+ {veto_list} veto)"
        else:
            full_summary = agent_list

        # Initialize decision engine
        self.engine = DecisionEngine(
            agents=agents,
            veto_agents=veto_agents,
            consensus_threshold=consensus_threshold,
            min_confidence=min_confidence,
            adaptive_weights=adaptive_weights
        )

        log.info("=" * 60)
        log.info(f"AGENT SYSTEM INITIALIZED - {agent_count}")
        log.info(f"  Mode: {'ENABLED' if enabled else 'LOG-ONLY'}")
        log.info(f"  Consensus Threshold: {consensus_threshold}")
        log.info(f"  Min Confidence: {min_confidence}")
        log.info(f"  Adaptive Weights: {adaptive_weights}")
        log.info(f"  Enabled Agents: {full_summary}")
        log.info(f"  Disabled Agents: {', '.join([a for a in ['TechAgent', 'SentimentAgent', 'RegimeAgent', 'CandlestickAgent', 'TimePatternAgent', 'OrderBookAgent', 'FundingRateAgent', 'StreakAgent', 'RiskAgent', 'GamblerAgent', 'OnChainAgent', 'SocialSentimentAgent'] if a not in enabled_agents]) or 'None'}")
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
            (should_trade, direction, confidence, reason, weighted_score)
            - should_trade: bool
            - direction: "Up", "Down", or None
            - confidence: float 0.0-1.0 (average agent confidence)
            - reason: str (explanation)
            - weighted_score: float 0.0-1.0 (consensus strength for position sizing)
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
            return False, None, 0.0, "Log-only mode", 0.0

        return (
            decision.should_trade,
            decision.direction,
            decision.confidence,
            decision.reason,
            decision.weighted_score  # Return weighted_score for position sizing
        )

    def get_position_size(self,
                         confidence: float,
                         balance: float,
                         consecutive_losses: int = 0,
                         weighted_score: float = None) -> float:
        """
        Calculate position size using RiskAgent with confidence-based scaling.

        Args:
            confidence: Signal confidence (0.0-1.0) - average agent confidence
            balance: Current balance
            consecutive_losses: Number of consecutive losses
            weighted_score: Weighted consensus score (0.0-1.0) - used for scaling

        Returns:
            Position size in USD
        """
        # Use weighted_score for position sizing if provided, otherwise use confidence
        # Weighted score represents the STRENGTH of consensus (quality × confidence × weight)
        signal_strength = weighted_score if weighted_score is not None else confidence

        # Apply confidence-based scaling:
        # - 0.10-0.20: 30% of normal size (very weak signal)
        # - 0.20-0.30: 50% of normal size (weak signal)
        # - 0.30-0.40: 70% of normal size (moderate signal)
        # - 0.40-0.60: 85% of normal size (good signal)
        # - 0.60+:     100% of normal size (strong signal)
        if signal_strength < 0.20:
            scale_multiplier = 0.30
        elif signal_strength < 0.30:
            scale_multiplier = 0.50
        elif signal_strength < 0.40:
            scale_multiplier = 0.70
        elif signal_strength < 0.60:
            scale_multiplier = 0.85
        else:
            scale_multiplier = 1.00

        # Calculate base position size
        base_size = self.risk_agent.calculate_position_size(
            signal_strength=signal_strength,
            balance=balance,
            consecutive_losses=consecutive_losses
        )

        # Apply confidence scaling
        scaled_size = base_size * scale_multiplier

        # CRITICAL: Ensure minimum bet size ($1.10)
        # Polymarket rejects orders below this threshold
        MIN_BET_USD = 1.10
        if scaled_size < MIN_BET_USD and scaled_size > 0:
            # If we can't afford minimum, return 0 (skip trade)
            # Otherwise, use minimum
            max_pct = 0.10 if balance < 75 else 0.05  # Tier-appropriate max
            if MIN_BET_USD <= (balance * max_pct):
                scaled_size = MIN_BET_USD
            else:
                scaled_size = 0.0  # Can't afford minimum

        return scaled_size

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
