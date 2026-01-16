#!/usr/bin/env python3
"""
Test: DirectionalBalanceTracker Integration (US-BF-009)

Verifies that:
1. Balance tracker is instantiated in DecisionEngine
2. tracker.record() is called after each decision
3. Warning logged when >70% bias detected
4. Balanced decisions (10 Up / 10 Down) → no warning
5. After 15 Up decisions, warning is logged
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from coordinator.decision_engine import DecisionEngine, TradeDecision
from agents.base_agent import BaseAgent, Vote
from typing import Dict, List
import logging

# Setup logging to capture warnings
logging.basicConfig(level=logging.DEBUG)

class MockAgent(BaseAgent):
    """Mock agent that returns predetermined votes."""

    def __init__(self, name: str, direction: str, confidence: float):
        super().__init__(name=name, weight=1.0)
        self.mock_direction = direction
        self.mock_confidence = confidence

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """Return predetermined vote."""
        return Vote(
            agent_name=self.name,
            direction=self.mock_direction,
            confidence=self.mock_confidence,
            quality=0.8,
            reasoning=f"{self.name} mock vote"
        )

def test_tracker_instantiation():
    """Test 1: Balance tracker instantiated in DecisionEngine."""
    print("\n=== Test 1: Tracker Instantiation ===")

    agents = [
        MockAgent("Agent1", "Up", 0.8),
        MockAgent("Agent2", "Up", 0.8)
    ]

    engine = DecisionEngine(
        agents=agents,
        consensus_threshold=0.40,
        min_confidence=0.40
    )

    assert hasattr(engine, 'balance_tracker'), "Engine should have balance_tracker attribute"
    assert engine.balance_tracker.window_size == 20, "Tracker should have window_size=20"
    assert engine.balance_tracker.bias_threshold == 0.70, "Tracker should have bias_threshold=0.70"

    print("✅ PASS: Balance tracker instantiated correctly")

def test_balanced_decisions_no_warning(capsys=None):
    """Test 2: Balanced decisions (10 Up / 10 Down) → no warning."""
    print("\n=== Test 2: Balanced Decisions (No Warning) ===")

    engine = DecisionEngine(
        agents=[],
        consensus_threshold=0.40,
        min_confidence=0.40
    )

    # Manually record balanced decisions
    for _ in range(10):
        engine.balance_tracker.record("Up")
    for _ in range(10):
        engine.balance_tracker.record("Down")

    balance = engine.balance_tracker.get_balance()

    assert balance['total_decisions'] == 20, f"Should have 20 decisions, got {balance['total_decisions']}"
    assert balance['up_pct'] == 0.5, f"Up should be 50%, got {balance['up_pct']:.1%}"
    assert balance['down_pct'] == 0.5, f"Down should be 50%, got {balance['down_pct']:.1%}"
    assert not engine.balance_tracker.has_bias(), "Balanced decisions should NOT have bias"

    print(f"✅ PASS: Balanced decisions (10 Up / 10 Down) → no bias detected")
    print(f"   Balance: Up {balance['up_pct']:.1%} | Down {balance['down_pct']:.1%}")

def test_biased_decisions_warning():
    """Test 3: After 15 Up decisions, warning logged."""
    print("\n=== Test 3: Biased Decisions (Warning Expected) ===")

    # Create agents that always vote Up
    agents = [
        MockAgent("Agent1", "Up", 0.8),
        MockAgent("Agent2", "Up", 0.8)
    ]

    engine = DecisionEngine(
        agents=agents,
        consensus_threshold=0.40,
        min_confidence=0.40
    )

    # Make 15 Up decisions
    data = {
        'prices': {'btc': {'binance': 50000}},
        'orderbook': {},
        'positions': [],
        'balance': 100.0,
        'regime': 'neutral'
    }

    for i in range(15):
        decision = engine.decide('btc', 1000 + i, data)
        # Engine should record the direction internally

    balance = engine.balance_tracker.get_balance()

    assert balance['total_decisions'] >= 15, f"Should have at least 15 decisions, got {balance['total_decisions']}"
    assert balance['up_pct'] > 0.70, f"Up should be >70%, got {balance['up_pct']:.1%}"
    assert engine.balance_tracker.has_bias(), "15 Up decisions should trigger bias detection"

    summary = engine.balance_tracker.get_balance_summary()
    assert "BIAS DETECTED" in summary, f"Summary should contain bias alert: {summary}"

    print(f"✅ PASS: 15 Up decisions → bias detected")
    print(f"   Balance: Up {balance['up_pct']:.1%} | Down {balance['down_pct']:.1%}")
    print(f"   Summary: {summary}")

def test_skip_votes_not_tracked():
    """Test 4: Skip votes are not tracked (only Up/Down counted)."""
    print("\n=== Test 4: Skip Votes Not Tracked ===")

    engine = DecisionEngine(
        agents=[],
        consensus_threshold=0.40,
        min_confidence=0.40
    )

    # Record Skip votes
    for _ in range(10):
        engine.balance_tracker.record("Skip")

    balance = engine.balance_tracker.get_balance()

    assert balance['total_decisions'] == 0, f"Skip votes should not be tracked, got {balance['total_decisions']}"

    # Now add Up/Down votes
    for _ in range(5):
        engine.balance_tracker.record("Up")
    for _ in range(5):
        engine.balance_tracker.record("Down")

    balance = engine.balance_tracker.get_balance()

    assert balance['total_decisions'] == 10, f"Should have 10 Up/Down decisions, got {balance['total_decisions']}"
    assert balance['up_pct'] == 0.5, f"Up should be 50%, got {balance['up_pct']:.1%}"

    print(f"✅ PASS: Skip votes not tracked (only Up/Down)")
    print(f"   Balance after 10 Skip + 10 Up/Down: {balance['total_decisions']} decisions")

def test_mixed_decisions():
    """Test 5: Mixed decisions with some consensus failures."""
    print("\n=== Test 5: Mixed Decisions ===")

    # Create agents with varying directions
    up_agents = [MockAgent(f"UpAgent{i}", "Up", 0.8) for i in range(2)]
    down_agents = [MockAgent(f"DownAgent{i}", "Down", 0.8) for i in range(2)]

    engine = DecisionEngine(
        agents=up_agents + down_agents,
        consensus_threshold=0.40,
        min_confidence=0.40
    )

    # This should result in Up consensus (2 Up agents)
    data = {
        'prices': {'btc': {'binance': 50000}},
        'orderbook': {},
        'positions': [],
        'balance': 100.0,
        'regime': 'neutral'
    }

    # Make several decisions (some may not reach consensus)
    for i in range(10):
        decision = engine.decide('btc', 1000 + i, data)

    balance = engine.balance_tracker.get_balance()

    # Should have tracked some decisions
    assert balance['total_decisions'] > 0, "Should have recorded at least some decisions"

    print(f"✅ PASS: Mixed decisions tracked")
    print(f"   Balance: Up {balance['up_pct']:.1%} | Down {balance['down_pct']:.1%}")
    print(f"   Total decisions: {balance['total_decisions']}")

if __name__ == "__main__":
    print("Testing DirectionalBalanceTracker Integration (US-BF-009)")
    print("=" * 70)

    try:
        test_tracker_instantiation()
        test_balanced_decisions_no_warning()
        test_biased_decisions_warning()
        test_skip_votes_not_tracked()
        test_mixed_decisions()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
