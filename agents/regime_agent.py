#!/usr/bin/env python3
"""
Market Regime Expert Agent

Classifies market conditions (bull/bear/volatile/sideways) and adjusts
agent weights and strategy parameters based on the current regime.
"""

import logging
import statistics
from collections import deque
from typing import Dict, Optional

from .base_agent import BaseAgent, Vote

log = logging.getLogger(__name__)


# Regime classification thresholds
HIGH_VOLATILITY_THRESHOLD = 0.015  # 1.5% std dev
TREND_THRESHOLD = 0.0005           # 0.05% mean return (lowered from 0.10% per US-BF-017)
STRONG_TREND_RATIO = 0.75          # 3 out of 4 cryptos agreeing


class RegimeAgent(BaseAgent):
    """
    Market Regime Expert Agent.

    Analyzes:
    - Overall market trend (bull/bear/sideways)
    - Volatility levels
    - Trend strength and consistency
    - Per-crypto regime alignment

    Doesn't predict direction - instead adjusts other agents' weights:
    - Bull momentum → Boost TechAgent, reduce SentimentAgent
    - Bear momentum → Boost TechAgent, reduce SentimentAgent
    - Sideways → Boost SentimentAgent (contrarian works)
    - Volatile → Boost RiskAgent (more conservative)

    Returns Neutral vote with weight adjustment recommendations.
    """

    def __init__(self,
                 name: str = "RegimeAgent",
                 weight: float = 1.0,
                 lookback_windows: int = 20):
        super().__init__(name, weight)

        self.lookback = lookback_windows
        self.price_history: Dict[str, deque] = {}

        # Current regime state
        self.current_regime: Optional[str] = None
        self.regime_confidence: float = 0.0
        self.avg_volatility: float = 0.0

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze market regime and return vote with weight adjustments.

        Args:
            crypto: Crypto symbol
            epoch: Current epoch
            data: Shared context with:
                - prices: Current prices for all cryptos
                - price_history: Historical price data (optional)

        Returns:
            Vote with Neutral direction but includes weight_adjustments in details
        """
        try:
            # Update price history
            prices = data.get('prices', {})
            self._update_price_history(prices)
        except Exception as e:
            # If price update fails, return low-confidence Up vote
            return Vote(
                direction="Up",
                confidence=0.15,
                quality=0.2,
                agent_name=self.name,
                reasoning=f"Price history error → defaulting to Up",
                details={'error': str(e)}
            )

        # Detect regime
        regime_data = self._detect_regime()

        self.current_regime = regime_data['regime']
        self.regime_confidence = regime_data['confidence']
        self.avg_volatility = regime_data['volatility']

        # Get weight adjustments for other agents
        weight_adjustments = self._calculate_weight_adjustments(regime_data)

        # Confidence is regime_confidence (how sure we are of the classification)
        confidence = regime_data['confidence']

        # Quality based on data sufficiency
        quality = self._calculate_quality(regime_data)

        reasoning = (
            f"Regime: {self.current_regime} ({confidence:.0%} confident), "
            f"volatility: {self.avg_volatility*100:.2f}%, "
            f"adjusting weights for regime"
        )

        # CRITICAL FIX: Always pick a direction based on regime
        # Get this crypto's trend from details
        crypto_details = regime_data.get('crypto_details', {})
        crypto_trend = crypto_details.get(crypto, {})
        mean_return = crypto_trend.get('mean_return', 0.0)

        # Pick direction based on regime
        # In sideways regime, ABSTAIN instead of picking a direction
        if self.current_regime == 'sideways':
            vote = Vote(
                direction="Skip",
                confidence=0.0,
                quality=0.0,
                agent_name=self.name,
                reasoning=f"Sideways regime detected → ABSTAINING",
                details={
                    'regime': self.current_regime,
                    'confidence': confidence,
                    'volatility': self.avg_volatility,
                    'weight_adjustments': weight_adjustments,
                    'crypto_details': regime_data.get('crypto_details', {}),
                    'trend_strength': 'sideways',  # US-BF-017: Add trend_strength even for Skip votes
                    'mean_return': mean_return
                }
            )
            self.log.debug(f"[{self.name}] {crypto}: {vote.direction} (conf={vote.confidence:.2f}) - {vote.reasoning}")
            return vote

        # For non-sideways regimes, pick direction based on this crypto's trend
        # US-BF-017: Updated thresholds to use 0.05% (0.0005) instead of 0.10% (0.001)
        if mean_return > 0.001:  # Strong positive trend > 0.10%
            direction = "Up"
            trend_strength = "strong_bull"
        elif mean_return > 0.0005:  # Weak positive trend 0.05-0.10%
            direction = "Up"
            trend_strength = "weak_bull"
        elif mean_return < -0.001:  # Strong negative trend < -0.10%
            direction = "Down"
            trend_strength = "strong_bear"
        elif mean_return < -0.0005:  # Weak negative trend -0.10 to -0.05%
            direction = "Down"
            trend_strength = "weak_bear"
        else:
            # Sideways trend -0.05 to +0.05%
            # Use overall regime to break tie
            trend_strength = "sideways"
            if self.current_regime in ['bull_momentum']:
                direction = "Up"
            elif self.current_regime in ['bear_momentum']:
                direction = "Down"
            else:
                # Should not reach here (sideways handled above)
                # But safety fallback: Skip
                direction = "Skip"

        # Adjust confidence based on regime clarity
        vote_confidence = confidence * 0.3  # Lower confidence since regime is slow

        reasoning = (
            f"Regime: {self.current_regime} ({confidence:.0%}), "
            f"{crypto} trend: {mean_return*100:+.2f}% ({trend_strength}) → {direction}, "
            f"volatility: {self.avg_volatility*100:.2f}%"
        )

        # Log trend strength classification (US-BF-017)
        self.log.debug(f"[{self.name}] RegimeAgent classified {trend_strength} regime (mean: {mean_return:+.3%})")

        vote = Vote(
            direction=direction,  # ALWAYS pick Up or Down
            confidence=vote_confidence,
            quality=quality,
            agent_name=self.name,
            reasoning=reasoning,
            details={
                'regime': self.current_regime,
                'confidence': confidence,
                'volatility': self.avg_volatility,
                'weight_adjustments': weight_adjustments,
                'crypto_details': regime_data.get('crypto_details', {}),
                'trend_strength': trend_strength,  # US-BF-017: Add trend strength field
                'mean_return': mean_return
            }
        )
        self.log.debug(f"[{self.name}] {crypto}: {vote.direction} (conf={vote.confidence:.2f}) - {vote.reasoning}")
        return vote

    def _update_price_history(self, prices: Dict[str, float]):
        """Update price history for all cryptos."""
        for crypto, price in prices.items():
            if crypto not in self.price_history:
                self.price_history[crypto] = deque(maxlen=self.lookback)

            self.price_history[crypto].append(price)

    def _detect_regime(self) -> dict:
        """
        Detect overall market regime.

        Returns:
            dict with regime, confidence, volatility, crypto_details
        """
        if not self.price_history:
            return {
                'regime': 'unknown',
                'confidence': 0.0,
                'volatility': 0.0,
                'crypto_details': {}
            }

        crypto_analysis = {}

        for crypto, prices in self.price_history.items():
            crypto_analysis[crypto] = self._calculate_trend(crypto, list(prices))

        # Aggregate trends
        trends = [a['trend'] for a in crypto_analysis.values()]
        strengths = [a['strength'] for a in crypto_analysis.values()]
        volatilities = [a['volatility'] for a in crypto_analysis.values()]

        if not trends:
            return {
                'regime': 'unknown',
                'confidence': 0.0,
                'volatility': 0.0,
                'crypto_details': {}
            }

        avg_strength = statistics.mean(strengths) if strengths else 0
        avg_volatility = statistics.mean(volatilities) if volatilities else 0

        # Count trend directions
        bullish_count = sum(1 for t in trends if t == 'bullish')
        bearish_count = sum(1 for t in trends if t == 'bearish')
        total_count = len(trends)

        # Determine regime
        if avg_volatility > HIGH_VOLATILITY_THRESHOLD:
            regime = 'volatile'
            confidence = min(avg_volatility / 0.025, 1.0)

        elif bullish_count >= (total_count * STRONG_TREND_RATIO):
            regime = 'bull_momentum'
            confidence = avg_strength

        elif bearish_count >= (total_count * STRONG_TREND_RATIO):
            regime = 'bear_momentum'
            confidence = avg_strength

        else:  # Mixed signals
            regime = 'sideways'
            confidence = 1.0 - avg_strength  # High confidence when low directional strength

        return {
            'regime': regime,
            'confidence': confidence,
            'volatility': avg_volatility,
            'crypto_details': crypto_analysis
        }

    def _calculate_trend(self, crypto: str, prices: list) -> dict:
        """Calculate trend metrics for a crypto."""
        if len(prices) < 3:
            return {
                'trend': 'unknown',
                'strength': 0,
                'volatility': 0,
                'mean_return': 0
            }

        # Calculate returns
        try:
            returns = [(prices[i] - prices[i-1]) / prices[i-1]
                       for i in range(1, len(prices))
                       if prices[i-1] != 0]  # Skip zero prices to avoid division by zero
        except (TypeError, ZeroDivisionError) as e:
            # If prices contains non-numeric data or zero prices, return unknown
            return {
                'trend': 'unknown',
                'strength': 0,
                'volatility': 0,
                'mean_return': 0
            }

        # Check if we have enough returns data
        if len(returns) == 0:
            return {
                'trend': 'unknown',
                'strength': 0,
                'volatility': 0,
                'mean_return': 0
            }

        # Trend direction
        mean_return = statistics.mean(returns)

        if mean_return > TREND_THRESHOLD:
            trend = 'bullish'
        elif mean_return < -TREND_THRESHOLD:
            trend = 'bearish'
        else:
            trend = 'sideways'

        # Trend strength (how consistent the direction is)
        positive_returns = sum(1 for r in returns if r > 0)
        # Guard against division by zero (though should be caught above)
        strength = abs(positive_returns / len(returns) - 0.5) * 2 if len(returns) > 0 else 0  # 0-1 scale

        # Volatility (std dev of returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0

        return {
            'trend': trend,
            'strength': strength,
            'volatility': volatility,
            'mean_return': mean_return
        }

    def _calculate_weight_adjustments(self, regime_data: dict) -> Dict[str, float]:
        """
        Calculate weight adjustments for other agents based on regime.

        Returns:
            Dict mapping agent_name → weight_multiplier (0.5 to 1.5)
        """
        regime = regime_data['regime']
        volatility = regime_data['volatility']

        adjustments = {
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RiskAgent': 1.0,
            'FutureAgent': 1.0,
            'HistoryAgent': 1.0
        }

        if regime == 'bull_momentum':
            # Boost momentum-based agents
            adjustments['TechAgent'] = 1.3
            adjustments['SentimentAgent'] = 0.7  # Contrarian less useful in trends
            adjustments['RiskAgent'] = 1.0

        elif regime == 'bear_momentum':
            # Boost momentum-based agents
            adjustments['TechAgent'] = 1.3
            adjustments['SentimentAgent'] = 0.7  # Contrarian less useful in trends
            adjustments['RiskAgent'] = 1.0

        elif regime == 'volatile':
            # Boost risk management, reduce everything else
            adjustments['TechAgent'] = 0.8
            adjustments['SentimentAgent'] = 0.6  # Too risky
            adjustments['RiskAgent'] = 1.5       # Critical in volatile markets
            adjustments['FutureAgent'] = 0.7

        elif regime == 'sideways':
            # Boost contrarian, normal tech
            adjustments['TechAgent'] = 0.9
            adjustments['SentimentAgent'] = 1.4  # Contrarian works well
            adjustments['RiskAgent'] = 1.0

        return adjustments

    def _calculate_quality(self, regime_data: dict) -> float:
        """
        Calculate quality score based on data sufficiency.

        Returns:
            Quality score 0.0-1.0
        """
        # Check how many cryptos have sufficient data
        crypto_details = regime_data.get('crypto_details', {})

        cryptos_with_data = sum(
            1 for details in crypto_details.values()
            if details.get('trend') != 'unknown'
        )

        total_cryptos = len(crypto_details) if crypto_details else 4

        data_ratio = cryptos_with_data / total_cryptos if total_cryptos > 0 else 0

        # Quality also depends on price history length
        avg_history_length = 0
        if self.price_history:
            avg_history_length = statistics.mean(
                len(prices) for prices in self.price_history.values()
            )

        history_quality = min(avg_history_length / self.lookback, 1.0)

        # Combined quality
        quality = (data_ratio * 0.6) + (history_quality * 0.4)

        return quality

    def get_regime_parameters(self) -> dict:
        """
        Get recommended parameter adjustments for current regime.

        Returns dict of parameter overrides for the bot.
        """
        if not self.current_regime:
            return {}

        params = {}

        if self.current_regime == 'bull_momentum':
            params.update({
                'CONTRARIAN_ENABLED': False,
                'MIN_SIGNAL_STRENGTH': 0.60,
                'EARLY_MAX_ENTRY': 0.35,
                'CONTRARIAN_MAX_ENTRY': 0.10,
                'strategy_focus': 'momentum_following'
            })

        elif self.current_regime == 'bear_momentum':
            params.update({
                'CONTRARIAN_ENABLED': False,
                'MIN_SIGNAL_STRENGTH': 0.60,
                'EARLY_MAX_ENTRY': 0.35,
                'CONTRARIAN_MAX_ENTRY': 0.10,
                'strategy_focus': 'momentum_following'
            })

        elif self.current_regime == 'volatile':
            params.update({
                'CONTRARIAN_ENABLED': False,
                'MIN_SIGNAL_STRENGTH': 0.80,
                'EARLY_MAX_ENTRY': 0.20,
                'CONTRARIAN_MAX_ENTRY': 0.10,
                'MAX_POSITION_USD': 10,
                'strategy_focus': 'ultra_conservative'
            })

        elif self.current_regime == 'sideways':
            params.update({
                'CONTRARIAN_ENABLED': True,
                'MIN_SIGNAL_STRENGTH': 0.65,
                'EARLY_MAX_ENTRY': 0.30,
                'CONTRARIAN_MAX_ENTRY': 0.20,
                'CONTRARIAN_PRICE_THRESHOLD': 0.70,
                'strategy_focus': 'mean_reversion'
            })

        return params

    def get_regime_summary(self) -> str:
        """Get human-readable regime summary."""
        if not self.current_regime:
            return "Regime: Unknown (insufficient data)"

        return (
            f"Regime: {self.current_regime.replace('_', ' ').title()} "
            f"({self.regime_confidence:.0%} confident), "
            f"Volatility: {self.avg_volatility*100:.2f}%"
        )
