#!/usr/bin/env python3
"""
Test SentimentAgent Skip vote behavior.

Verifies:
1. No orderbook → Skip vote
2. No contrarian opportunity → Skip vote
3. Contrarian opportunity → directional vote (unchanged)
4. Skip votes have confidence=0.0 and quality=0.0
"""

import sys
sys.path.insert(0, '/Volumes/TerraTitan/Development/polymarket-autotrader')

from agents.sentiment_agent import SentimentAgent


def test_no_orderbook():
    """Test: Missing orderbook returns Skip vote"""
    agent = SentimentAgent()

    # No orderbook data
    data = {
        'time_in_epoch': 100,
        'rsi': 50.0
    }

    vote = agent.analyze('btc', 1234567890, data)

    assert vote.direction == "Skip", f"Expected Skip, got {vote.direction}"
    assert vote.confidence == 0.0, f"Expected confidence 0.0, got {vote.confidence}"
    assert vote.quality == 0.0, f"Expected quality 0.0, got {vote.quality}"
    assert "ABSTAINING" in vote.reasoning, f"Expected ABSTAINING in reasoning, got: {vote.reasoning}"
    print("✅ No orderbook → Skip vote")


def test_no_contrarian_opportunity():
    """Test: No contrarian signal returns Skip vote"""
    agent = SentimentAgent()

    # Orderbook with balanced prices, outside contrarian time window
    data = {
        'orderbook': {
            'Up': {'price': 0.52},
            'Down': {'price': 0.48}
        },
        'time_in_epoch': 900,  # Outside 30-700 second window
        'rsi': 50.0
    }

    vote = agent.analyze('eth', 1234567890, data)

    assert vote.direction == "Skip", f"Expected Skip, got {vote.direction}"
    assert vote.confidence == 0.0, f"Expected confidence 0.0, got {vote.confidence}"
    assert vote.quality == 0.0, f"Expected quality 0.0, got {vote.quality}"
    assert "ABSTAINING" in vote.reasoning, f"Expected ABSTAINING in reasoning, got: {vote.reasoning}"
    print("✅ No contrarian opportunity → Skip vote")


def test_no_contrarian_opportunity_early():
    """Test: No contrarian signal in contrarian time window but no extreme prices"""
    agent = SentimentAgent()

    # Orderbook with non-extreme prices, inside time window
    data = {
        'orderbook': {
            'Up': {'price': 0.60},
            'Down': {'price': 0.40}
        },
        'time_in_epoch': 300,  # Inside 30-700 second window
        'rsi': 50.0
    }

    vote = agent.analyze('sol', 1234567890, data)

    assert vote.direction == "Skip", f"Expected Skip, got {vote.direction}"
    assert vote.confidence == 0.0, f"Expected confidence 0.0, got {vote.confidence}"
    assert vote.quality == 0.0, f"Expected quality 0.0, got {vote.quality}"
    assert "ABSTAINING" in vote.reasoning, f"Expected ABSTAINING in reasoning, got: {vote.reasoning}"
    print("✅ No extreme prices in time window → Skip vote")


def test_contrarian_opportunity():
    """Test: Valid contrarian signal returns directional vote (unchanged behavior)"""
    agent = SentimentAgent()

    # Up overpriced, Down cheap - contrarian Down opportunity
    data = {
        'orderbook': {
            'Up': {'price': 0.85},   # Overpriced
            'Down': {'price': 0.15}  # Cheap
        },
        'time_in_epoch': 300,  # Inside 30-700 second window
        'rsi': 65.0  # Slightly high (confirms overbought)
    }

    vote = agent.analyze('xrp', 1234567890, data)

    # Should vote Down (fade the overpriced Up side)
    assert vote.direction == "Down", f"Expected Down, got {vote.direction}"
    assert vote.confidence > 0.0, f"Expected confidence > 0, got {vote.confidence}"
    assert vote.quality > 0.0, f"Expected quality > 0, got {vote.quality}"
    assert "Contrarian" in vote.reasoning, f"Expected 'Contrarian' in reasoning, got: {vote.reasoning}"
    print(f"✅ Contrarian opportunity → {vote.direction} vote (confidence: {vote.confidence:.2f})")


def test_contrarian_opportunity_reverse():
    """Test: Down overpriced, Up cheap - contrarian Up opportunity"""
    agent = SentimentAgent()

    # Down overpriced, Up cheap - contrarian Up opportunity
    data = {
        'orderbook': {
            'Up': {'price': 0.18},   # Cheap
            'Down': {'price': 0.82}  # Overpriced
        },
        'time_in_epoch': 400,  # Inside 30-700 second window
        'rsi': 35.0  # Low (confirms oversold)
    }

    vote = agent.analyze('btc', 1234567890, data)

    # Should vote Up (fade the overpriced Down side)
    assert vote.direction == "Up", f"Expected Up, got {vote.direction}"
    assert vote.confidence > 0.0, f"Expected confidence > 0, got {vote.confidence}"
    assert vote.quality > 0.0, f"Expected quality > 0, got {vote.quality}"
    assert "Contrarian" in vote.reasoning, f"Expected 'Contrarian' in reasoning, got: {vote.reasoning}"
    print(f"✅ Contrarian opportunity (reverse) → {vote.direction} vote (confidence: {vote.confidence:.2f})")


if __name__ == "__main__":
    print("Testing SentimentAgent Skip vote behavior...")
    print()

    test_no_orderbook()
    test_no_contrarian_opportunity()
    test_no_contrarian_opportunity_early()
    test_contrarian_opportunity()
    test_contrarian_opportunity_reverse()

    print()
    print("✅ All tests passed!")
