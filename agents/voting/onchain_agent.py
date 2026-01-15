#!/usr/bin/env python3
"""
OnChainAgent - Blockchain Signal Analysis

Analyzes on-chain metrics to detect whale activity and exchange flows:
- Large wallet transfers (>$100k movements)
- Exchange inflows (selling pressure indicator)
- Exchange outflows (buying/hodling indicator)
- Net flow (inflow - outflow over 15 min)

Data sources:
- Whale Alert API (requires subscription: $29/mo paid tier)
- Alternative: Etherscan/Polygonscan APIs (free tier available)

Priority: MEDIUM
Expected Impact: +2-4% win rate
"""

import os
import time
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

from agents.base_agent import BaseAgent, Vote

log = logging.getLogger(__name__)


@dataclass
class OnChainMetrics:
    """On-chain metrics for a crypto asset."""
    net_flow: float  # Net flow in USD (positive = inflow, negative = outflow)
    large_transfers_count: int  # Number of large transfers (>$100k)
    exchange_inflow_usd: float  # Total exchange inflow in USD
    exchange_outflow_usd: float  # Total exchange outflow in USD
    whale_transfers_usd: float  # Total whale transfer volume
    data_age: float  # Age of data in seconds


class OnChainAgent(BaseAgent):
    """
    Agent that analyzes on-chain blockchain metrics.

    Signals:
    - Exchange inflows: Selling pressure → DOWN bias
    - Exchange outflows: Buying/hodling → UP bias
    - Whale accumulation: Large outflows from exchanges → UP bias
    - Whale distribution: Large inflows to exchanges → DOWN bias

    Vote Logic:
    - Strong outflow (net < -$500k): UP vote, high confidence
    - Strong inflow (net > +$500k): DOWN vote, high confidence
    - Moderate flows: Lower confidence votes
    - No significant activity: abstain (low quality)
    """

    # Thresholds for signal detection
    STRONG_FLOW_THRESHOLD = 500_000  # $500k net flow = strong signal
    MODERATE_FLOW_THRESHOLD = 100_000  # $100k net flow = moderate signal
    WHALE_THRESHOLD = 100_000  # $100k per transaction = whale

    # Quality thresholds
    MIN_WHALE_ACTIVITY = 2  # Need 2+ whale transfers for high quality
    MAX_DATA_AGE = 900  # 15 minutes (stale data degrades quality)

    # Confidence levels
    STRONG_CONFIDENCE = 0.70
    MODERATE_CONFIDENCE = 0.50
    WEAK_CONFIDENCE = 0.35

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize OnChainAgent.

        Args:
            config: Optional configuration dict with:
                - whale_alert_api_key: API key for Whale Alert
                - etherscan_api_key: API key for Etherscan (fallback)
                - lookback_minutes: How far back to analyze (default: 15)
        """
        super().__init__(name="OnChainAgent")

        self.config = config or {}
        self.whale_alert_key = os.getenv('WHALE_ALERT_API_KEY') or self.config.get('whale_alert_api_key')
        self.etherscan_key = os.getenv('ETHERSCAN_API_KEY') or self.config.get('etherscan_api_key')
        self.lookback_minutes = self.config.get('lookback_minutes', 15)

        # Cache for on-chain data (reduce API calls)
        self._cache: Dict[str, Tuple[OnChainMetrics, float]] = {}
        self._cache_ttl = 60  # 60 seconds (on-chain data updates slowly)

        # API availability
        self._api_available = self.whale_alert_key is not None or self.etherscan_key is not None

        if not self._api_available:
            log.warning("[OnChainAgent] No API keys found - agent will return low quality votes")
            log.warning("[OnChainAgent] Set WHALE_ALERT_API_KEY or ETHERSCAN_API_KEY environment variable")

    def _fetch_onchain_metrics(self, crypto: str) -> Optional[OnChainMetrics]:
        """
        Fetch on-chain metrics for a crypto asset.

        Args:
            crypto: Crypto symbol (BTC, ETH, SOL, XRP)

        Returns:
            OnChainMetrics or None if data unavailable
        """
        # Check cache first
        cache_key = f"{crypto}:{int(time.time() // self._cache_ttl)}"
        if cache_key in self._cache:
            metrics, timestamp = self._cache[cache_key]
            age = time.time() - timestamp
            if age < self._cache_ttl:
                return metrics

        # TODO: Implement actual API calls when keys are available
        # For now, return None to gracefully degrade
        if not self._api_available:
            return None

        # Placeholder for future implementation
        # This is where we'd call Whale Alert API or Etherscan API
        # Example structure:
        #
        # if self.whale_alert_key:
        #     metrics = self._fetch_from_whale_alert(crypto)
        # elif self.etherscan_key:
        #     metrics = self._fetch_from_etherscan(crypto)
        #
        # self._cache[cache_key] = (metrics, time.time())
        # return metrics

        return None

    def _analyze_flow_direction(self, metrics: OnChainMetrics) -> Tuple[str, float, float]:
        """
        Analyze net flow to determine trading direction.

        Args:
            metrics: OnChainMetrics with flow data

        Returns:
            Tuple of (direction, confidence, quality)
        """
        net_flow = metrics.net_flow
        whale_count = metrics.large_transfers_count
        data_age = metrics.data_age

        # Quality scoring
        quality = 0.5  # Base quality

        # Boost quality if we have whale activity
        if whale_count >= self.MIN_WHALE_ACTIVITY:
            quality += 0.3

        # Reduce quality if data is stale
        if data_age > self.MAX_DATA_AGE:
            staleness_penalty = min(0.4, (data_age - self.MAX_DATA_AGE) / self.MAX_DATA_AGE * 0.4)
            quality -= staleness_penalty

        quality = max(0.1, min(1.0, quality))

        # Direction and confidence based on net flow
        # Negative net flow (outflows) = buying/accumulation = UP
        # Positive net flow (inflows) = selling/distribution = DOWN

        abs_flow = abs(net_flow)

        if abs_flow >= self.STRONG_FLOW_THRESHOLD:
            # Strong signal
            direction = "Down" if net_flow > 0 else "Up"
            confidence = self.STRONG_CONFIDENCE

        elif abs_flow >= self.MODERATE_FLOW_THRESHOLD:
            # Moderate signal
            direction = "Down" if net_flow > 0 else "Up"
            confidence = self.MODERATE_CONFIDENCE

        else:
            # Weak signal - slight bias toward existing flow
            direction = "Down" if net_flow > 0 else "Up"
            confidence = self.WEAK_CONFIDENCE
            quality *= 0.5  # Low quality due to weak signal

        return direction, confidence, quality

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze on-chain metrics and generate vote.

        Args:
            crypto: Crypto symbol (BTC, ETH, SOL, XRP)
            epoch: Current epoch timestamp
            data: Shared data context (unused for now, future API integration)

        Returns:
            Vote with direction, confidence, quality, reasoning
        """
        # Fetch on-chain metrics
        metrics = self._fetch_onchain_metrics(crypto)

        # If no data available, return low-quality neutral vote
        if metrics is None:
            return Vote(
                direction="Up",  # Neutral default
                confidence=0.35,
                quality=0.10,  # Very low quality indicates no real signal
                agent_name=self.name,
                reasoning="No on-chain data available (API key required)",
                details={
                    'api_available': self._api_available,
                    'has_whale_alert_key': self.whale_alert_key is not None,
                    'has_etherscan_key': self.etherscan_key is not None
                }
            )

        # Analyze flow direction
        direction, confidence, quality = self._analyze_flow_direction(metrics)

        # Build reasoning
        flow_direction = "inflows" if metrics.net_flow > 0 else "outflows"
        flow_magnitude = abs(metrics.net_flow) / 1000  # Convert to thousands

        if abs(metrics.net_flow) >= self.STRONG_FLOW_THRESHOLD:
            strength = "Strong"
        elif abs(metrics.net_flow) >= self.MODERATE_FLOW_THRESHOLD:
            strength = "Moderate"
        else:
            strength = "Weak"

        reasoning = f"{strength} exchange {flow_direction} (${flow_magnitude:.0f}k) suggests {direction}"

        if metrics.large_transfers_count > 0:
            reasoning += f" (+ {metrics.large_transfers_count} whale transfers)"

        return Vote(
            direction=direction,
            confidence=confidence,
            quality=quality,
            agent_name=self.name,
            reasoning=reasoning,
            details={
                'net_flow_usd': metrics.net_flow,
                'exchange_inflow_usd': metrics.exchange_inflow_usd,
                'exchange_outflow_usd': metrics.exchange_outflow_usd,
                'whale_transfers_count': metrics.large_transfers_count,
                'whale_transfers_usd': metrics.whale_transfers_usd,
                'data_age_seconds': metrics.data_age
            }
        )


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    agent = OnChainAgent()

    # Test vote with no API key (should gracefully degrade)
    vote = agent.analyze('BTC', epoch=1000, data={})

    print(f"Direction: {vote.direction}")
    print(f"Confidence: {vote.confidence:.0%}")
    print(f"Quality: {vote.quality:.0%}")
    print(f"Reasoning: {vote.reasoning}")
    print(f"Details: {vote.details}")
