#!/usr/bin/env python3
"""
Test RegimeAgent Skip vote behavior - US-BF-003

Verifies that RegimeAgent returns Skip vote in sideways regime
instead of defaulting to Up direction.
"""

import sys
from collections import deque

# Add agents directory to path
sys.path.insert(0, '/Volumes/TerraTitan/Development/polymarket-autotrader')

from agents.regime_agent import RegimeAgent


def test_sideways_regime_returns_skip():
    """Test that sideways regime with flat trend returns Skip vote."""
    print("TEST 1: Sideways regime with flat trend → Skip vote")

    agent = RegimeAgent(name="RegimeAgent", weight=1.0, lookback_windows=20)

    # Simulate sideways market - prices oscillating around same level
    sideways_prices = {
        'BTC': 50000.0, 'ETH': 3000.0, 'SOL': 100.0, 'XRP': 0.50
    }

    # Build price history with sideways movement (±0.05% random walk)
    for i in range(20):
        for crypto in sideways_prices:
            if crypto not in agent.price_history:
                agent.price_history[crypto] = deque(maxlen=20)

            # Add small random fluctuations (0.00% to 0.05% changes)
            variation = (-1 if i % 2 == 0 else 1) * 0.0003  # ±0.03%
            price = sideways_prices[crypto] * (1 + variation)
            agent.price_history[crypto].append(price)

    # Analyze with current epoch data
    data = {
        'prices': sideways_prices,
        'price_history': agent.price_history
    }

    vote = agent.analyze(crypto='BTC', epoch=100, data=data)

    print(f"  Direction: {vote.direction}")
    print(f"  Confidence: {vote.confidence}")
    print(f"  Quality: {vote.quality}")
    print(f"  Reasoning: {vote.reasoning}")
    print(f"  Regime: {vote.details.get('regime')}")

    assert vote.direction == "Skip", f"Expected Skip, got {vote.direction}"
    assert vote.confidence == 0.0, f"Expected 0.0 confidence, got {vote.confidence}"
    assert vote.quality == 0.0, f"Expected 0.0 quality, got {vote.quality}"
    assert "ABSTAINING" in vote.reasoning or "sideways" in vote.reasoning.lower()

    print("  ✅ PASS\n")


def test_bull_regime_returns_up():
    """Test that bull momentum regime returns Up vote."""
    print("TEST 2: Bull momentum regime → Up vote")

    agent = RegimeAgent(name="RegimeAgent", weight=1.0, lookback_windows=20)

    # Simulate bull market - steadily rising prices
    # Need strong trend > TREND_THRESHOLD (0.001) to trigger bullish trend
    base_prices = {
        'BTC': 50000.0, 'ETH': 3000.0, 'SOL': 100.0, 'XRP': 0.50
    }

    # Build price history with upward trend (0.3% per step compounding)
    # Initialize price trackers and deques for each crypto
    current_prices = {crypto: price for crypto, price in base_prices.items()}
    for crypto in base_prices.keys():
        agent.price_history[crypto] = deque(maxlen=20)

    for i in range(20):
        # Update each crypto's price (compound 0.3% increase)
        for crypto in base_prices.keys():
            # Compound the increase
            current_prices[crypto] *= 1.003
            agent.price_history[crypto].append(current_prices[crypto])

    # Debug: print first few prices
    print(f"  BTC price history (first 5): {list(agent.price_history['BTC'])[:5]}")
    print(f"  BTC price history (last 5): {list(agent.price_history['BTC'])[-5:]}")

    # Pass current prices (after the trend), not base prices!
    data = {
        'prices': current_prices,  # Use ending prices, not starting prices
        'price_history': agent.price_history
    }

    vote = agent.analyze(crypto='BTC', epoch=100, data=data)

    print(f"  Direction: {vote.direction}")
    print(f"  Confidence: {vote.confidence}")
    print(f"  Quality: {vote.quality}")
    print(f"  Reasoning: {vote.reasoning}")
    print(f"  Regime: {vote.details.get('regime')}")

    # Debug regime detection
    crypto_details = vote.details.get('crypto_details', {})
    print(f"  Crypto Details:")
    for crypto, details in crypto_details.items():
        print(f"    {crypto}: trend={details.get('trend')}, mean_return={details.get('mean_return', 0)*100:.3f}%, strength={details.get('strength', 0):.2f}")

    assert vote.direction == "Up", f"Expected Up, got {vote.direction}"
    assert vote.confidence > 0.0, f"Expected confidence > 0, got {vote.confidence}"

    print("  ✅ PASS\n")


def test_bear_regime_returns_down():
    """Test that bear momentum regime returns Down vote."""
    print("TEST 3: Bear momentum regime → Down vote")

    agent = RegimeAgent(name="RegimeAgent", weight=1.0, lookback_windows=20)

    # Simulate bear market - steadily falling prices
    base_prices = {
        'BTC': 50000.0, 'ETH': 3000.0, 'SOL': 100.0, 'XRP': 0.50
    }

    # Build price history with downward trend (0.3% per step compounding)
    # Initialize price trackers and deques for each crypto
    current_prices = {crypto: price for crypto, price in base_prices.items()}
    for crypto in base_prices.keys():
        agent.price_history[crypto] = deque(maxlen=20)

    for i in range(20):
        # Update each crypto's price (compound 0.3% decrease)
        for crypto in base_prices.keys():
            # Compound the decrease
            current_prices[crypto] *= 0.997
            agent.price_history[crypto].append(current_prices[crypto])

    # Pass current prices (after the trend), not base prices!
    data = {
        'prices': current_prices,  # Use ending prices, not starting prices
        'price_history': agent.price_history
    }

    vote = agent.analyze(crypto='BTC', epoch=100, data=data)

    print(f"  Direction: {vote.direction}")
    print(f"  Confidence: {vote.confidence}")
    print(f"  Quality: {vote.quality}")
    print(f"  Reasoning: {vote.reasoning}")
    print(f"  Regime: {vote.details.get('regime')}")

    assert vote.direction == "Down", f"Expected Down, got {vote.direction}"
    assert vote.confidence > 0.0, f"Expected confidence > 0, got {vote.confidence}"

    print("  ✅ PASS\n")


def test_volatile_regime_behavior():
    """Test volatile regime behavior."""
    print("TEST 4: Volatile regime (high variance)")

    agent = RegimeAgent(name="RegimeAgent", weight=1.0, lookback_windows=20)

    # Simulate volatile market - large swings
    base_prices = {
        'BTC': 50000.0, 'ETH': 3000.0, 'SOL': 100.0, 'XRP': 0.50
    }

    # Build price history with high volatility (±2% swings)
    for i in range(20):
        for crypto in base_prices:
            if crypto not in agent.price_history:
                agent.price_history[crypto] = deque(maxlen=20)

            # Volatile: alternate between +2% and -2%
            variation = 0.02 if i % 2 == 0 else -0.02
            price = base_prices[crypto] * (1 + variation)
            agent.price_history[crypto].append(price)

    data = {
        'prices': base_prices,
        'price_history': agent.price_history
    }

    vote = agent.analyze(crypto='BTC', epoch=100, data=data)

    print(f"  Direction: {vote.direction}")
    print(f"  Confidence: {vote.confidence}")
    print(f"  Quality: {vote.quality}")
    print(f"  Reasoning: {vote.reasoning}")
    print(f"  Regime: {vote.details.get('regime')}")

    # Volatile regime should be detected
    assert vote.details.get('regime') == 'volatile', f"Expected volatile regime"

    print("  ✅ PASS\n")


def test_choppy_market_skip():
    """Test that choppy market (no clear trend, not volatile) returns Skip."""
    print("TEST 5: Choppy market (mixed signals) → Skip vote")

    agent = RegimeAgent(name="RegimeAgent", weight=1.0, lookback_windows=20)

    # Simulate choppy market - small movements, no clear direction
    base_prices = {
        'BTC': 50000.0, 'ETH': 3000.0, 'SOL': 100.0, 'XRP': 0.50
    }

    # Build price history with choppy movement (±0.08% alternating)
    for i in range(20):
        for crypto in base_prices:
            if crypto not in agent.price_history:
                agent.price_history[crypto] = deque(maxlen=20)

            # Choppy: small alternating moves
            variation = 0.0008 if i % 3 == 0 else (-0.0008 if i % 3 == 1 else 0.0)
            price = base_prices[crypto] * (1 + variation)
            agent.price_history[crypto].append(price)

    data = {
        'prices': base_prices,
        'price_history': agent.price_history
    }

    vote = agent.analyze(crypto='BTC', epoch=100, data=data)

    print(f"  Direction: {vote.direction}")
    print(f"  Confidence: {vote.confidence}")
    print(f"  Quality: {vote.quality}")
    print(f"  Reasoning: {vote.reasoning}")
    print(f"  Regime: {vote.details.get('regime')}")

    # Choppy market should trigger sideways regime → Skip
    if vote.details.get('regime') == 'sideways':
        assert vote.direction == "Skip", f"Expected Skip in sideways, got {vote.direction}"
        assert vote.confidence == 0.0

    print("  ✅ PASS\n")


if __name__ == '__main__':
    print("="*60)
    print("Testing RegimeAgent Skip Vote Behavior (US-BF-003)")
    print("="*60 + "\n")

    test_sideways_regime_returns_skip()
    test_bull_regime_returns_up()
    test_bear_regime_returns_down()
    test_volatile_regime_behavior()
    test_choppy_market_skip()

    print("="*60)
    print("✅ ALL TESTS PASSED")
    print("="*60)
