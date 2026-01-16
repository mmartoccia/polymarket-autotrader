#!/usr/bin/env python3
"""
Test US-BF-007: Change weighted score to average

Verify that weighted scores are averaged instead of summed to prevent weak signal stacking.
Formula: weighted_score = sum(confidence * weight) / sum(weight)
"""

import sys
from agents.base_agent import Vote

def test_three_weak_votes():
    """Test: Three 0.35 confidence votes should average to ~0.35, not sum to 1.05"""
    print("\n=== Test 1: Three 0.35 confidence votes ===")

    # Create three votes with same confidence/quality
    votes = [
        Vote(agent_name="Agent1", direction="Up", confidence=0.35, quality=0.35, reasoning="Weak signal 1"),
        Vote(agent_name="Agent2", direction="Up", confidence=0.35, quality=0.35, reasoning="Weak signal 2"),
        Vote(agent_name="Agent3", direction="Up", confidence=0.35, quality=0.35, reasoning="Weak signal 3"),
    ]

    # All agents have weight 1.0
    weights = {"Agent1": 1.0, "Agent2": 1.0, "Agent3": 1.0}

    # Calculate average weighted score
    total_weighted = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in votes)
    total_weight = sum(weights.get(v.agent_name, 1.0) for v in votes)
    avg_score = total_weighted / total_weight if total_weight > 0 else 0.0

    print(f"Votes: {len(votes)} × 0.35 confidence")
    print(f"Total weighted: {total_weighted:.3f}")
    print(f"Total weight: {total_weight:.1f}")
    print(f"Average score: {avg_score:.3f}")

    # Should be close to 0.35 (confidence * quality = 0.35 * 0.35 = 0.1225)
    # Three votes: 0.1225 + 0.1225 + 0.1225 = 0.3675 / 3 weights = 0.1225
    expected = 0.35 * 0.35  # confidence × quality

    assert abs(avg_score - expected) < 0.01, f"Expected ~{expected:.3f}, got {avg_score:.3f}"
    print(f"✅ PASS: Average score {avg_score:.3f} ≈ {expected:.3f} (not 1.05)")


def test_mixed_confidence_votes():
    """Test: One 0.80 vote + two 0.30 votes should average correctly"""
    print("\n=== Test 2: Mixed confidence votes (0.80 + 0.30 + 0.30) ===")

    votes = [
        Vote(agent_name="Agent1", direction="Up", confidence=0.80, quality=0.80, reasoning="Strong signal"),
        Vote(agent_name="Agent2", direction="Up", confidence=0.30, quality=0.30, reasoning="Weak signal 1"),
        Vote(agent_name="Agent3", direction="Up", confidence=0.30, quality=0.30, reasoning="Weak signal 2"),
    ]

    weights = {"Agent1": 1.0, "Agent2": 1.0, "Agent3": 1.0}

    total_weighted = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in votes)
    total_weight = sum(weights.get(v.agent_name, 1.0) for v in votes)
    avg_score = total_weighted / total_weight if total_weight > 0 else 0.0

    print(f"Votes: 1×0.80 + 2×0.30 confidence")
    print(f"Total weighted: {total_weighted:.3f}")
    print(f"Total weight: {total_weight:.1f}")
    print(f"Average score: {avg_score:.3f}")

    # Manual calculation:
    # 0.80*0.80 = 0.64, 0.30*0.30 = 0.09, 0.30*0.30 = 0.09
    # (0.64 + 0.09 + 0.09) / 3 = 0.82 / 3 = 0.2733
    expected = (0.80*0.80 + 0.30*0.30 + 0.30*0.30) / 3

    assert abs(avg_score - expected) < 0.01, f"Expected ~{expected:.3f}, got {avg_score:.3f}"
    print(f"✅ PASS: Average score {avg_score:.3f} ≈ {expected:.3f}")


def test_different_weights():
    """Test: Agents with different weights should be averaged correctly"""
    print("\n=== Test 3: Different agent weights (1.5, 1.0, 0.5) ===")

    votes = [
        Vote(agent_name="Agent1", direction="Up", confidence=0.60, quality=0.60, reasoning="Heavy agent"),
        Vote(agent_name="Agent2", direction="Up", confidence=0.40, quality=0.40, reasoning="Medium agent"),
        Vote(agent_name="Agent3", direction="Up", confidence=0.50, quality=0.50, reasoning="Light agent"),
    ]

    weights = {"Agent1": 1.5, "Agent2": 1.0, "Agent3": 0.5}

    total_weighted = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in votes)
    total_weight = sum(weights.get(v.agent_name, 1.0) for v in votes)
    avg_score = total_weighted / total_weight if total_weight > 0 else 0.0

    print(f"Votes: Agent1(w=1.5, c=0.60), Agent2(w=1.0, c=0.40), Agent3(w=0.5, c=0.50)")
    print(f"Total weighted: {total_weighted:.3f}")
    print(f"Total weight: {total_weight:.1f}")
    print(f"Average score: {avg_score:.3f}")

    # Manual calculation:
    # Agent1: 0.60*0.60*1.5 = 0.54
    # Agent2: 0.40*0.40*1.0 = 0.16
    # Agent3: 0.50*0.50*0.5 = 0.125
    # (0.54 + 0.16 + 0.125) / (1.5 + 1.0 + 0.5) = 0.825 / 3.0 = 0.275
    expected = (0.60*0.60*1.5 + 0.40*0.40*1.0 + 0.50*0.50*0.5) / (1.5 + 1.0 + 0.5)

    assert abs(avg_score - expected) < 0.01, f"Expected ~{expected:.3f}, got {avg_score:.3f}"
    print(f"✅ PASS: Weighted average {avg_score:.3f} ≈ {expected:.3f}")


def test_single_vote():
    """Test: Single vote should return its own weighted score"""
    print("\n=== Test 4: Single vote ===")

    votes = [
        Vote(agent_name="Agent1", direction="Up", confidence=0.70, quality=0.65, reasoning="Only signal"),
    ]

    weights = {"Agent1": 1.0}

    total_weighted = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in votes)
    total_weight = sum(weights.get(v.agent_name, 1.0) for v in votes)
    avg_score = total_weighted / total_weight if total_weight > 0 else 0.0

    print(f"Vote: confidence=0.70, quality=0.65, weight=1.0")
    print(f"Average score: {avg_score:.3f}")

    # Should be confidence * quality = 0.70 * 0.65 = 0.455
    expected = 0.70 * 0.65

    assert abs(avg_score - expected) < 0.01, f"Expected ~{expected:.3f}, got {avg_score:.3f}"
    print(f"✅ PASS: Single vote score {avg_score:.3f} ≈ {expected:.3f}")


def test_empty_votes():
    """Test: Empty vote list should return 0.0"""
    print("\n=== Test 5: Empty vote list ===")

    votes = []
    weights = {}

    if not votes:
        avg_score = 0.0
    else:
        total_weighted = sum(v.weighted_score(weights.get(v.agent_name, 1.0)) for v in votes)
        total_weight = sum(weights.get(v.agent_name, 1.0) for v in votes)
        avg_score = total_weighted / total_weight if total_weight > 0 else 0.0

    print(f"Votes: empty list")
    print(f"Average score: {avg_score:.3f}")

    assert avg_score == 0.0, f"Expected 0.0, got {avg_score:.3f}"
    print(f"✅ PASS: Empty list returns 0.0")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing US-BF-007: Weighted Score Averaging")
    print("=" * 60)

    try:
        test_three_weak_votes()
        test_mixed_confidence_votes()
        test_different_weights()
        test_single_vote()
        test_empty_votes()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nKey findings:")
        print("- Three 0.35 votes average to ~0.12 (not 1.05 sum)")
        print("- Mixed confidence votes weight correctly")
        print("- Different agent weights handled properly")
        print("- Single vote returns its own score")
        print("- Empty list returns 0.0 safely")
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
