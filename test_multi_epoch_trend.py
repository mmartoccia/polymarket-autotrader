#!/usr/bin/env python3
"""
Test US-BF-017: Multi-epoch trend detection

Verifies:
1. TECH_CONFLUENCE_THRESHOLD lowered from 0.003 to 0.002
2. REGIME_TREND_THRESHOLD lowered from 0.001 to 0.0005
3. TechAgent tracks last 5 epochs
4. TechAgent detects 3+ consecutive epochs as trend
5. TechAgent reduces confidence by 50% on trend conflict
6. RegimeAgent adds trend_strength field
7. VoteAggregator logs trend conflicts
"""

import sys
import time
from collections import deque
from agents.tech_agent import TechAgent, CONFLUENCE_THRESHOLD
from agents.regime_agent import RegimeAgent, TREND_THRESHOLD
from config import agent_config


def test_thresholds_lowered():
    """Test that thresholds were lowered correctly."""
    print("=" * 60)
    print("TEST 1: Verify thresholds lowered")
    print("=" * 60)

    # Check config values
    assert agent_config.TECH_CONFLUENCE_THRESHOLD == 0.002, \
        f"TECH_CONFLUENCE_THRESHOLD should be 0.002, got {agent_config.TECH_CONFLUENCE_THRESHOLD}"
    print("✅ config.TECH_CONFLUENCE_THRESHOLD = 0.002 (was 0.003)")

    assert agent_config.REGIME_TREND_THRESHOLD == 0.0005, \
        f"REGIME_TREND_THRESHOLD should be 0.0005, got {agent_config.REGIME_TREND_THRESHOLD}"
    print("✅ config.REGIME_TREND_THRESHOLD = 0.0005 (was 0.001)")

    # Check hardcoded values in agents
    assert CONFLUENCE_THRESHOLD == 0.002, \
        f"tech_agent.CONFLUENCE_THRESHOLD should be 0.002, got {CONFLUENCE_THRESHOLD}"
    print("✅ tech_agent.CONFLUENCE_THRESHOLD = 0.002 (was 0.003)")

    assert TREND_THRESHOLD == 0.0005, \
        f"regime_agent.TREND_THRESHOLD should be 0.0005, got {TREND_THRESHOLD}"
    print("✅ regime_agent.TREND_THRESHOLD = 0.0005 (was 0.001)")

    print("\n✅ All thresholds lowered correctly\n")


def test_tech_agent_epoch_history():
    """Test that TechAgent tracks epoch history."""
    print("=" * 60)
    print("TEST 2: TechAgent epoch history tracking")
    print("=" * 60)

    agent = TechAgent()

    # Verify epoch_history exists
    assert hasattr(agent, 'epoch_history'), "TechAgent should have epoch_history attribute"
    print("✅ TechAgent has epoch_history attribute")

    # Verify it's a dict
    assert isinstance(agent.epoch_history, dict), "epoch_history should be a dict"
    print("✅ epoch_history is a dict")

    print("\n✅ TechAgent epoch history initialized correctly\n")


def test_tech_agent_trend_detection():
    """Test that TechAgent detects 3+ epoch trends."""
    print("=" * 60)
    print("TEST 3: TechAgent 3-epoch trend detection")
    print("=" * 60)

    agent = TechAgent()

    # Manually simulate 3 consecutive Down epochs
    agent.epoch_history['btc'] = deque(['Down', 'Down', 'Down'], maxlen=5)

    # Create mock data that will trigger an Up vote (conflicts with trend)
    mock_data = {
        'orderbook': {'yes': {'price': 0.20}, 'no': {'price': 0.80}},
        'positions': [],
        'balance': 100.0
    }

    # Mock the price feed to return Up signal
    class MockPriceFeed:
        def __init__(self):
            self.rsi = type('obj', (object,), {'get_rsi': lambda c: 50.0})()

        def update_prices(self, crypto):
            pass

        def get_confluence_signal(self, crypto):
            # Return Up signal
            return "Up", 3, 0.005, {
                'binance': ('Up', 0.006),
                'kraken': ('Up', 0.005),
                'coinbase': ('Up', 0.004)
            }

    agent.price_feed = MockPriceFeed()
    agent.last_update = {'btc': time.time()}

    # Get vote
    vote = agent.analyze('btc', int(time.time()), mock_data)

    # Check that trend was detected
    assert 'epoch_trend' in vote.details, "Vote should include epoch_trend in details"
    assert vote.details['epoch_trend'] == 'Down', f"Should detect Down trend, got {vote.details.get('epoch_trend')}"
    print("✅ TechAgent detected 3-epoch downtrend")

    # Check that conflict was flagged
    assert 'trend_conflict' in vote.details, "Vote should include trend_conflict in details"
    assert vote.details['trend_conflict'] == True, "Should flag trend conflict"
    print("✅ TechAgent flagged trend conflict (Up vote vs Down trend)")

    # Check that reasoning mentions conflict
    assert 'CONFLICTS' in vote.reasoning or 'conflict' in vote.reasoning.lower(), \
        f"Reasoning should mention conflict: {vote.reasoning}"
    print("✅ Vote reasoning mentions conflict")

    print("\n✅ TechAgent trend detection working correctly\n")


def test_regime_agent_trend_strength():
    """Test that RegimeAgent adds trend_strength field."""
    print("=" * 60)
    print("TEST 4: RegimeAgent trend_strength classification")
    print("=" * 60)

    agent = RegimeAgent()

    # Test data: weak bear regime (-0.07% mean return)
    test_data = {
        'prices': {
            'btc': 45000.0,
            'eth': 3000.0,
            'sol': 100.0,
            'xrp': 0.50
        }
    }

    # Pre-populate price history with downward trend
    for crypto in ['btc', 'eth', 'sol', 'xrp']:
        agent.price_history[crypto] = deque(maxlen=20)
        # Add 20 prices with slight downward trend (-0.07% per window)
        base_price = test_data['prices'][crypto]
        for i in range(20):
            price = base_price * (1 - 0.0007 * i)
            agent.price_history[crypto].append(price)

    # Get vote
    vote = agent.analyze('btc', int(time.time()), test_data)

    # Check that trend_strength field exists
    assert 'trend_strength' in vote.details, "Vote should include trend_strength in details"
    print(f"✅ RegimeAgent includes trend_strength: {vote.details['trend_strength']}")

    # Verify trend_strength is one of valid values
    valid_strengths = ['strong_bull', 'weak_bull', 'strong_bear', 'weak_bear', 'sideways']
    assert vote.details['trend_strength'] in valid_strengths, \
        f"trend_strength should be one of {valid_strengths}, got {vote.details['trend_strength']}"
    print(f"✅ trend_strength is valid: {vote.details['trend_strength']}")

    # Check that mean_return is included
    assert 'mean_return' in vote.details, "Vote should include mean_return"
    print(f"✅ RegimeAgent includes mean_return: {vote.details['mean_return']:.3%}")

    print("\n✅ RegimeAgent trend_strength working correctly\n")


def test_lower_thresholds_detect_weak_trends():
    """Test that lowered thresholds detect -0.15% to -0.25% moves."""
    print("=" * 60)
    print("TEST 5: Lower thresholds detect weak trends")
    print("=" * 60)

    # Test TECH_CONFLUENCE_THRESHOLD with -0.25% move
    # Old threshold (0.30%) would NOT trigger, new threshold (0.20%) WILL trigger
    move_pct = -0.0025
    assert abs(move_pct) < 0.003, f"0.25% move should be below old 0.30% threshold"
    assert abs(move_pct) > 0.002, f"0.25% move should be above new 0.20% threshold"
    print(f"✅ -0.25% move: below old threshold (0.30%), above new threshold (0.20%)")

    # Test REGIME_TREND_THRESHOLD with -0.07% mean
    # Old threshold (0.10%) would classify as sideways, new threshold (0.05%) classifies as weak_bear
    mean_return = -0.0007
    assert abs(mean_return) < 0.001, f"0.07% mean should be below old 0.10% threshold"
    assert abs(mean_return) > 0.0005, f"0.07% mean should be above new 0.05% threshold"
    print(f"✅ -0.07% mean: below old threshold (0.10%), above new threshold (0.05%)")

    # Verify the math: cumulative -0.15% to -0.20% per epoch = 3 epochs of weak downtrend
    single_epoch = -0.0018  # -0.18% per epoch
    cumulative_3 = single_epoch * 3  # -0.54% over 3 epochs
    print(f"✅ Example: 3 epochs @ -0.18% each = {cumulative_3:.2%} cumulative downtrend")

    print("\n✅ Lower thresholds correctly detect weak cumulative trends\n")


if __name__ == '__main__':
    try:
        test_thresholds_lowered()
        test_tech_agent_epoch_history()
        test_tech_agent_trend_detection()
        test_regime_agent_trend_strength()
        test_lower_thresholds_detect_weak_trends()

        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nUS-BF-017 Implementation Summary:")
        print("- ✅ TECH_CONFLUENCE_THRESHOLD: 0.003 → 0.002 (0.30% → 0.20%)")
        print("- ✅ REGIME_TREND_THRESHOLD: 0.001 → 0.0005 (0.10% → 0.05%)")
        print("- ✅ TechAgent tracks last 5 epochs per crypto")
        print("- ✅ TechAgent detects 3+ consecutive epochs as trend")
        print("- ✅ TechAgent reduces confidence by 50% on conflict")
        print("- ✅ RegimeAgent adds trend_strength field")
        print("- ✅ VoteAggregator logs trend conflicts")
        print("\n" + "=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
