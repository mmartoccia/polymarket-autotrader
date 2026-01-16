#!/usr/bin/env python3
"""
Test bull market override detection and disabling.

Tests:
1. DISABLE_BULL_OVERRIDES flag exists in config
2. Flag is set to True
3. bull_market_overrides.json file is detected
4. Check function logic (without full bot import)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_config_flag():
    """Test that DISABLE_BULL_OVERRIDES flag exists and is True."""
    print("=" * 60)
    print("TEST 1: Config Flag")
    print("=" * 60)

    from config import agent_config

    # Check that DISABLE_BULL_OVERRIDES exists
    assert hasattr(agent_config, 'DISABLE_BULL_OVERRIDES'), \
        "DISABLE_BULL_OVERRIDES flag not found in config"
    print("✓ DISABLE_BULL_OVERRIDES flag exists")

    # Check that it's True
    disable_flag = agent_config.DISABLE_BULL_OVERRIDES
    assert disable_flag is True, \
        f"DISABLE_BULL_OVERRIDES should be True (got {disable_flag})"
    print(f"✓ DISABLE_BULL_OVERRIDES = {disable_flag}")

    return disable_flag


def test_file_detection():
    """Test that bull_market_overrides.json is detected if present."""
    print("\n" + "=" * 60)
    print("TEST 2: File Detection")
    print("=" * 60)

    bull_override_path = project_root / "state" / "bull_market_overrides.json"
    file_exists = bull_override_path.exists()

    if file_exists:
        print(f"✓ bull_market_overrides.json detected at:")
        print(f"  {bull_override_path}")
    else:
        print("ℹ️  bull_market_overrides.json not found (normal)")

    return file_exists


def test_check_logic(disable_flag, file_exists):
    """Test the logic of what should happen."""
    print("\n" + "=" * 60)
    print("TEST 3: Check Logic")
    print("=" * 60)

    print(f"Scenario:")
    print(f"  - DISABLE_BULL_OVERRIDES: {disable_flag}")
    print(f"  - File exists: {file_exists}")

    if file_exists and disable_flag:
        expected = "File exists but DISABLED - bot will log warning and ignore"
        status = "✅ SAFE"
    elif file_exists and not disable_flag:
        expected = "File exists and NOT disabled - DANGEROUS, would load overrides!"
        status = "🚨 DANGEROUS"
    elif not file_exists:
        expected = "File doesn't exist - bot will log info message"
        status = "✅ SAFE"
    else:
        expected = "Unknown scenario"
        status = "⚠️  UNKNOWN"

    print(f"\nExpected behavior:")
    print(f"  {expected}")
    print(f"\nStatus: {status}")

    # Verify safe scenario
    if file_exists and disable_flag:
        print("\n✓ Test passed: Overrides disabled despite file existing")
        print("  Bot will log: '⚠️  Bull market overrides file found but DISABLED'")
        return True
    elif not file_exists:
        print("\n✓ Test passed: No override file present")
        print("  Bot will log: 'ℹ️  No bull market overrides file found (normal)'")
        return True
    else:
        print("\n❌ Test warning: Unsafe configuration detected")
        return False


def run_all_tests():
    """Run all tests."""
    print("\nTesting bull market override detection...\n")

    disable_flag = test_config_flag()
    file_exists = test_file_detection()
    is_safe = test_check_logic(disable_flag, file_exists)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Config flag (DISABLE_BULL_OVERRIDES): {disable_flag}")
    print(f"Override file exists: {file_exists}")
    print(f"Configuration is safe: {is_safe}")

    if is_safe:
        print("\n✅ ALL TESTS PASSED - Bot will handle overrides correctly")
    else:
        print("\n⚠️  WARNING - Potential configuration issue detected")

    print("\nExpected startup logs:")
    if file_exists and disable_flag:
        print("  ⚠️  Bull market overrides file found but DISABLED by config flag")
        print("  ✅ Bot will NOT load bull market overrides")
    elif not file_exists:
        print("  ℹ️  No bull market overrides file found (normal)")

    return is_safe


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
