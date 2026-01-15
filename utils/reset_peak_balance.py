#!/usr/bin/env python3
"""
Reset Peak Balance Utility

Resets peak_balance to match current_balance in trading_state.json.
Use this to exit HALTED mode when drawdown is incorrectly calculated
due to peak balance being inflated by unrealized position values.

Usage:
    python3 utils/reset_peak_balance.py
"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

STATE_FILE = Path(__file__).parent.parent / "state" / "trading_state.json"

def reset_peak_balance():
    """Reset peak_balance to current_balance"""
    if not STATE_FILE.exists():
        print(f"ERROR: State file not found at {STATE_FILE}")
        return False

    # Load current state
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)

    current_balance = state.get('current_balance', 0)
    old_peak = state.get('peak_balance', 0)

    print(f"Current state:")
    print(f"  Current balance: ${current_balance:.2f}")
    print(f"  Peak balance: ${old_peak:.2f}")

    if old_peak > current_balance:
        drawdown_pct = ((old_peak - current_balance) / old_peak) * 100
        print(f"  Drawdown: {drawdown_pct:.1f}%")

    # Update peak to match current
    state['peak_balance'] = current_balance

    # Write back
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\n✅ Peak balance reset to ${current_balance:.2f}")
    print(f"   Bot should exit HALTED mode on next scan cycle")
    return True

if __name__ == "__main__":
    success = reset_peak_balance()
    sys.exit(0 if success else 1)
