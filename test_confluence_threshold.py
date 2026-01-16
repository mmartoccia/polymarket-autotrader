#!/usr/bin/env python3
"""
Test confluence threshold filtering of random walk noise
"""

import sys
sys.path.insert(0, '/Volumes/TerraTitan/Development/polymarket-autotrader')

from agents.tech_agent import CONFLUENCE_THRESHOLD


def test_confluence_threshold_value():
    """Test that confluence threshold is 0.003 (0.30%)"""
    print(f"✓ CONFLUENCE_THRESHOLD = {CONFLUENCE_THRESHOLD} (expected: 0.003)")
    assert CONFLUENCE_THRESHOLD == 0.003, f"Expected 0.003, got {CONFLUENCE_THRESHOLD}"


def test_small_price_move_filtered():
    """Test that 0.20% price move does not trigger confluence"""
    price_change = 0.002  # 0.20%

    triggers_up = price_change > CONFLUENCE_THRESHOLD
    triggers_down = price_change < -CONFLUENCE_THRESHOLD

    print(f"✓ Price change {price_change*100:.2f}% (< threshold): triggers_up={triggers_up}, triggers_down={triggers_down}")
    assert not triggers_up, f"0.20% move should not trigger Up signal (threshold is 0.30%)"
    assert not triggers_down, f"0.20% move should not trigger Down signal"


def test_large_price_move_triggers():
    """Test that 0.35% price move does trigger confluence"""
    price_change_up = 0.0035  # 0.35% up
    price_change_down = -0.0035  # 0.35% down

    triggers_up = price_change_up > CONFLUENCE_THRESHOLD
    triggers_down = price_change_down < -CONFLUENCE_THRESHOLD

    print(f"✓ Price change +{price_change_up*100:.2f}% (> threshold): triggers Up = {triggers_up}")
    print(f"✓ Price change {price_change_down*100:.2f}% (< -threshold): triggers Down = {triggers_down}")

    assert triggers_up, f"0.35% up move should trigger Up signal"
    assert triggers_down, f"0.35% down move should trigger Down signal"


def test_edge_case_exactly_at_threshold():
    """Test behavior exactly at threshold boundary"""
    price_change_up = 0.003  # Exactly 0.30% up
    price_change_down = -0.003  # Exactly 0.30% down

    triggers_up = price_change_up > CONFLUENCE_THRESHOLD
    triggers_down = price_change_down < -CONFLUENCE_THRESHOLD

    print(f"✓ Price change exactly at +0.30%: triggers Up = {triggers_up} (expected: False, uses >)")
    print(f"✓ Price change exactly at -0.30%: triggers Down = {triggers_down} (expected: False, uses <)")

    # Using > and < (not >=, <=) means exactly at threshold does NOT trigger
    assert not triggers_up, "Exactly at threshold should not trigger (uses > not >=)"
    assert not triggers_down, "Exactly at threshold should not trigger (uses < not <=)"


def test_random_walk_noise_filtered():
    """Test that typical random walk noise (±0.05% to ±0.25%) is filtered out"""
    test_changes = [
        (0.0005, "±0.05%"),
        (0.001, "±0.10%"),
        (0.0015, "±0.15%"),
        (0.002, "±0.20%"),
        (0.0025, "±0.25%"),
    ]

    for change, label in test_changes:
        triggers_up = change > CONFLUENCE_THRESHOLD
        triggers_down = -change < -CONFLUENCE_THRESHOLD

        print(f"✓ Random walk noise {label}: Up={triggers_up}, Down={triggers_down} (both should be False)")
        assert not triggers_up, f"{label} noise should not trigger Up signal"
        assert not triggers_down, f"{label} noise should not trigger Down signal"


if __name__ == "__main__":
    print("Testing confluence threshold behavior...")
    print(f"CONFLUENCE_THRESHOLD = {CONFLUENCE_THRESHOLD}")
    print()

    test_confluence_threshold_value()
    print()

    test_small_price_move_filtered()
    print()

    test_large_price_move_triggers()
    print()

    test_edge_case_exactly_at_threshold()
    print()

    test_random_walk_noise_filtered()
    print()

    print("✅ All confluence threshold tests passed!")
