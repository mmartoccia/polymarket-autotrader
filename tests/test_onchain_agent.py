#!/usr/bin/env python3
"""
Tests for OnChainAgent
"""

import unittest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from agents.voting.onchain_agent import OnChainAgent, OnChainMetrics


class TestOnChainAgent(unittest.TestCase):
    """Test OnChainAgent class."""

    def setUp(self):
        """Create agent instance."""
        self.agent = OnChainAgent()

    def test_init(self):
        """Test agent initialization."""
        self.assertEqual(self.agent.name, "OnChainAgent")
        self.assertIsNotNone(self.agent.config)
        self.assertEqual(self.agent.lookback_minutes, 15)

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = {
            'whale_alert_api_key': 'test_key',
            'lookback_minutes': 30
        }
        agent = OnChainAgent(config=config)

        self.assertEqual(agent.lookback_minutes, 30)
        self.assertEqual(agent.whale_alert_key, 'test_key')

    def test_analyze_no_api_key(self):
        """Test analyze returns low quality when no API key available."""
        vote = self.agent.analyze('BTC', epoch=1000, data={})

        # Should return a vote (not None)
        self.assertIsNotNone(vote)

        # Should have very low quality
        self.assertLess(vote.quality, 0.15)

        # Should have reasoning explaining no data
        self.assertIn("No on-chain data", vote.reasoning)

        # Should have details
        self.assertIn('api_available', vote.details)

        # Should have agent name
        self.assertEqual(vote.agent_name, "OnChainAgent")

    def test_analyze_flow_strong_inflow(self):
        """Test analysis with strong exchange inflow (DOWN signal)."""
        metrics = OnChainMetrics(
            net_flow=600_000,  # Strong inflow
            large_transfers_count=3,
            exchange_inflow_usd=800_000,
            exchange_outflow_usd=200_000,
            whale_transfers_usd=500_000,
            data_age=300  # 5 minutes old
        )

        direction, confidence, quality = self.agent._analyze_flow_direction(metrics)

        self.assertEqual(direction, "Down")
        self.assertGreaterEqual(confidence, 0.70)  # Strong confidence
        self.assertGreater(quality, 0.5)  # Good quality (whale activity present)

    def test_analyze_flow_strong_outflow(self):
        """Test analysis with strong exchange outflow (UP signal)."""
        metrics = OnChainMetrics(
            net_flow=-700_000,  # Strong outflow
            large_transfers_count=5,
            exchange_inflow_usd=100_000,
            exchange_outflow_usd=800_000,
            whale_transfers_usd=1_000_000,
            data_age=120  # 2 minutes old
        )

        direction, confidence, quality = self.agent._analyze_flow_direction(metrics)

        self.assertEqual(direction, "Up")
        self.assertGreaterEqual(confidence, 0.70)  # Strong confidence
        self.assertGreater(quality, 0.7)  # High quality (fresh data + whale activity)

    def test_analyze_flow_moderate(self):
        """Test analysis with moderate flow."""
        metrics = OnChainMetrics(
            net_flow=250_000,  # Moderate inflow
            large_transfers_count=1,
            exchange_inflow_usd=300_000,
            exchange_outflow_usd=50_000,
            whale_transfers_usd=150_000,
            data_age=600  # 10 minutes old
        )

        direction, confidence, quality = self.agent._analyze_flow_direction(metrics)

        self.assertEqual(direction, "Down")
        self.assertLess(confidence, 0.70)  # Moderate confidence
        self.assertGreater(confidence, 0.40)
        self.assertGreater(quality, 0.3)

    def test_analyze_flow_weak(self):
        """Test analysis with weak flow (minimal activity)."""
        metrics = OnChainMetrics(
            net_flow=50_000,  # Weak flow
            large_transfers_count=0,
            exchange_inflow_usd=75_000,
            exchange_outflow_usd=25_000,
            whale_transfers_usd=0,
            data_age=200
        )

        direction, confidence, quality = self.agent._analyze_flow_direction(metrics)

        # Should return low confidence and quality
        self.assertLess(confidence, 0.40)
        self.assertLess(quality, 0.40)

    def test_analyze_flow_stale_data(self):
        """Test that stale data reduces quality."""
        fresh_metrics = OnChainMetrics(
            net_flow=600_000,
            large_transfers_count=3,
            exchange_inflow_usd=800_000,
            exchange_outflow_usd=200_000,
            whale_transfers_usd=500_000,
            data_age=60  # 1 minute old
        )

        stale_metrics = OnChainMetrics(
            net_flow=600_000,
            large_transfers_count=3,
            exchange_inflow_usd=800_000,
            exchange_outflow_usd=200_000,
            whale_transfers_usd=500_000,
            data_age=1800  # 30 minutes old (very stale)
        )

        _, _, fresh_quality = self.agent._analyze_flow_direction(fresh_metrics)
        _, _, stale_quality = self.agent._analyze_flow_direction(stale_metrics)

        # Stale data should have lower quality
        self.assertLess(stale_quality, fresh_quality)

    def test_whale_activity_boosts_quality(self):
        """Test that whale activity increases quality."""
        no_whales = OnChainMetrics(
            net_flow=600_000,
            large_transfers_count=0,  # No whale activity
            exchange_inflow_usd=700_000,
            exchange_outflow_usd=100_000,
            whale_transfers_usd=0,
            data_age=200
        )

        with_whales = OnChainMetrics(
            net_flow=600_000,
            large_transfers_count=5,  # Lots of whale activity
            exchange_inflow_usd=700_000,
            exchange_outflow_usd=100_000,
            whale_transfers_usd=2_000_000,
            data_age=200
        )

        _, _, quality_no_whales = self.agent._analyze_flow_direction(no_whales)
        _, _, quality_with_whales = self.agent._analyze_flow_direction(with_whales)

        # Whale activity should boost quality
        self.assertGreater(quality_with_whales, quality_no_whales)

    def test_thresholds(self):
        """Test threshold constants are sensible."""
        self.assertEqual(self.agent.STRONG_FLOW_THRESHOLD, 500_000)
        self.assertEqual(self.agent.MODERATE_FLOW_THRESHOLD, 100_000)
        self.assertEqual(self.agent.WHALE_THRESHOLD, 100_000)
        self.assertEqual(self.agent.MIN_WHALE_ACTIVITY, 2)
        self.assertEqual(self.agent.MAX_DATA_AGE, 900)

    def test_confidence_levels(self):
        """Test confidence level constants."""
        self.assertEqual(self.agent.STRONG_CONFIDENCE, 0.70)
        self.assertEqual(self.agent.MODERATE_CONFIDENCE, 0.50)
        self.assertEqual(self.agent.WEAK_CONFIDENCE, 0.35)

    def test_cache_ttl(self):
        """Test cache TTL is set correctly."""
        self.assertEqual(self.agent._cache_ttl, 60)  # 60 seconds


if __name__ == '__main__':
    unittest.main()
