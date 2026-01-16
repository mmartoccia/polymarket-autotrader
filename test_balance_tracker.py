#!/usr/bin/env python3
"""
Test DirectionalBalanceTracker class.

Tests:
1. 15 Up / 5 Down → returns 75% Up bias with alert
2. 10 Up / 10 Down → returns 50% balanced, no alert
3. Empty tracker → no bias
4. Less than window_size decisions → no bias alert
5. Edge case: All Up → 100% bias
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from coordinator.decision_engine import DirectionalBalanceTracker


def test_bias_detected():
    """Test: 15 Up / 5 Down → 75% Up bias with alert"""
    tracker = DirectionalBalanceTracker(window_size=20, bias_threshold=0.70)

    # Record 15 Up decisions
    for _ in range(15):
        tracker.record("Up")

    # Record 5 Down decisions
    for _ in range(5):
        tracker.record("Down")

    balance = tracker.get_balance()
    assert balance['up_pct'] == 0.75, f"Expected 75% Up, got {balance['up_pct']:.2%}"
    assert balance['down_pct'] == 0.25, f"Expected 25% Down, got {balance['down_pct']:.2%}"
    assert balance['total_decisions'] == 20

    assert tracker.has_bias() is True, "Expected bias to be detected"

    summary = tracker.get_balance_summary()
    assert "BIAS DETECTED" in summary, f"Expected bias alert in summary: {summary}"
    assert "Up 75" in summary, f"Expected Up 75% in summary: {summary}"

    print("✅ Test 1 passed: 15 Up / 5 Down → 75% Up bias detected")


def test_balanced_no_alert():
    """Test: 10 Up / 10 Down → 50% balanced, no alert"""
    tracker = DirectionalBalanceTracker(window_size=20, bias_threshold=0.70)

    # Record 10 Up decisions
    for _ in range(10):
        tracker.record("Up")

    # Record 10 Down decisions
    for _ in range(10):
        tracker.record("Down")

    balance = tracker.get_balance()
    assert balance['up_pct'] == 0.50, f"Expected 50% Up, got {balance['up_pct']:.2%}"
    assert balance['down_pct'] == 0.50, f"Expected 50% Down, got {balance['down_pct']:.2%}"
    assert balance['total_decisions'] == 20

    assert tracker.has_bias() is False, "Expected no bias to be detected"

    summary = tracker.get_balance_summary()
    assert "BIAS DETECTED" not in summary, f"Expected no bias alert: {summary}"

    print("✅ Test 2 passed: 10 Up / 10 Down → balanced, no alert")


def test_empty_tracker():
    """Test: Empty tracker → no bias"""
    tracker = DirectionalBalanceTracker(window_size=20, bias_threshold=0.70)

    balance = tracker.get_balance()
    assert balance['up_pct'] == 0.0
    assert balance['down_pct'] == 0.0
    assert balance['total_decisions'] == 0

    assert tracker.has_bias() is False

    summary = tracker.get_balance_summary()
    assert "No decisions tracked yet" in summary

    print("✅ Test 3 passed: Empty tracker → no bias")


def test_insufficient_decisions():
    """Test: Less than window_size decisions → no bias alert"""
    tracker = DirectionalBalanceTracker(window_size=20, bias_threshold=0.70)

    # Record only 10 decisions (all Up)
    for _ in range(10):
        tracker.record("Up")

    balance = tracker.get_balance()
    assert balance['up_pct'] == 1.0  # 100% Up
    assert balance['total_decisions'] == 10

    # Should NOT alert because total < window_size
    assert tracker.has_bias() is False, "Expected no bias alert with insufficient decisions"

    summary = tracker.get_balance_summary()
    assert "BIAS DETECTED" not in summary

    print("✅ Test 4 passed: Less than window_size → no bias alert")


def test_extreme_bias():
    """Test: All Up → 100% bias"""
    tracker = DirectionalBalanceTracker(window_size=20, bias_threshold=0.70)

    # Record 20 Up decisions
    for _ in range(20):
        tracker.record("Up")

    balance = tracker.get_balance()
    assert balance['up_pct'] == 1.0
    assert balance['down_pct'] == 0.0
    assert balance['total_decisions'] == 20

    assert tracker.has_bias() is True

    summary = tracker.get_balance_summary()
    assert "BIAS DETECTED" in summary
    assert "Up 100" in summary

    print("✅ Test 5 passed: All Up → 100% bias detected")


def test_skip_votes_ignored():
    """Test: Skip votes are not tracked"""
    tracker = DirectionalBalanceTracker(window_size=20, bias_threshold=0.70)

    # Record mix of Up, Down, Skip
    tracker.record("Up")
    tracker.record("Skip")
    tracker.record("Down")
    tracker.record("Neutral")
    tracker.record("Up")

    balance = tracker.get_balance()
    # Should only count Up and Down (not Skip or Neutral)
    assert balance['total_decisions'] == 3, f"Expected 3 decisions, got {balance['total_decisions']}"
    assert balance['up_pct'] == 2/3, f"Expected 66.7% Up, got {balance['up_pct']:.2%}"

    print("✅ Test 6 passed: Skip/Neutral votes ignored")


def test_rolling_window():
    """Test: Rolling window only keeps last N decisions"""
    tracker = DirectionalBalanceTracker(window_size=5, bias_threshold=0.70)

    # Record 10 Up decisions (should keep only last 5)
    for _ in range(10):
        tracker.record("Up")

    balance = tracker.get_balance()
    assert balance['total_decisions'] == 5, "Window should keep only last 5 decisions"
    assert balance['up_pct'] == 1.0

    # Now record 3 Down decisions → window should be [Up, Up, Down, Down, Down]
    for _ in range(3):
        tracker.record("Down")

    balance = tracker.get_balance()
    assert balance['total_decisions'] == 5
    assert balance['up_pct'] == 0.4  # 2 Up / 5 total
    assert balance['down_pct'] == 0.6  # 3 Down / 5 total

    print("✅ Test 7 passed: Rolling window works correctly")


if __name__ == "__main__":
    print("Testing DirectionalBalanceTracker...\n")

    test_bias_detected()
    test_balanced_no_alert()
    test_empty_tracker()
    test_insufficient_decisions()
    test_extreme_bias()
    test_skip_votes_ignored()
    test_rolling_window()

    print("\n✅ All DirectionalBalanceTracker tests passed!")
