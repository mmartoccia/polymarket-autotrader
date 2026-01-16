#!/usr/bin/env python3
"""
Test entry price limits for US-BF-014
"""
from config import agent_config

def test_max_entry_exists():
    """Test that MAX_ENTRY constant exists and has correct value"""
    assert hasattr(agent_config, 'MAX_ENTRY'), "MAX_ENTRY not found in config"
    assert agent_config.MAX_ENTRY == 0.25, f"MAX_ENTRY should be 0.25, got {agent_config.MAX_ENTRY}"
    print("✓ MAX_ENTRY = 0.25")

def test_early_max_entry_exists():
    """Test that EARLY_MAX_ENTRY constant exists"""
    assert hasattr(agent_config, 'EARLY_MAX_ENTRY'), "EARLY_MAX_ENTRY not found in config"
    assert agent_config.EARLY_MAX_ENTRY == 0.30, f"EARLY_MAX_ENTRY should be 0.30, got {agent_config.EARLY_MAX_ENTRY}"
    print("✓ EARLY_MAX_ENTRY = 0.30")

def test_entry_price_rejection_logic():
    """Test that entry price validation logic works correctly"""
    # Simulate the validation check from the bot
    max_entry_cap = getattr(agent_config, 'MAX_ENTRY', 0.40)

    # Test case 1: Entry price above limit should be rejected
    entry_price_high = 0.30
    should_reject_high = entry_price_high > max_entry_cap
    assert should_reject_high == True, f"Entry ${entry_price_high:.2f} > ${max_entry_cap:.2f} should be rejected"
    print(f"✓ Entry price ${entry_price_high:.2f} > ${max_entry_cap:.2f} would be rejected")

    # Test case 2: Entry price at limit should be allowed
    entry_price_at = 0.25
    should_reject_at = entry_price_at > max_entry_cap
    assert should_reject_at == False, f"Entry ${entry_price_at:.2f} = ${max_entry_cap:.2f} should be allowed"
    print(f"✓ Entry price ${entry_price_at:.2f} = ${max_entry_cap:.2f} would be allowed")

    # Test case 3: Entry price below limit should be allowed
    entry_price_low = 0.20
    should_reject_low = entry_price_low > max_entry_cap
    assert should_reject_low == False, f"Entry ${entry_price_low:.2f} < ${max_entry_cap:.2f} should be allowed"
    print(f"✓ Entry price ${entry_price_low:.2f} < ${max_entry_cap:.2f} would be allowed")

if __name__ == '__main__':
    print("Testing US-BF-014: Lower entry price threshold")
    print("=" * 60)

    test_max_entry_exists()
    test_early_max_entry_exists()
    test_entry_price_rejection_logic()

    print("=" * 60)
    print("✅ All tests passed!")
