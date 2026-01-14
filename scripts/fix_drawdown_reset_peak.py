#!/usr/bin/env python3
"""
Fix Drawdown Issue - Reset Peak Balance

This script resets the peak balance to current balance to fix false drawdown halts.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

def get_usdc_balance():
    """Get current USDC balance from blockchain."""
    w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
    usdc = w3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
    wallet = w3.to_checksum_address(os.getenv('POLYMARKET_WALLET'))

    balance_hex = w3.eth.call({
        'to': usdc,
        'data': '0x70a08231' + wallet[2:].lower().zfill(64)
    })
    balance = int(balance_hex.hex(), 16) / 1e6
    return balance

def main():
    print("="*60)
    print("Fix Drawdown Issue - Reset Peak Balance")
    print("="*60)
    print()

    # Get current balance
    print("1. Fetching current USDC balance...")
    try:
        current_balance = get_usdc_balance()
        print(f"   ✅ Current balance: ${current_balance:.2f}")
    except Exception as e:
        print(f"   ❌ Failed to get balance: {e}")
        print()
        print("Enter current balance manually:")
        current_balance = float(input("Balance: $"))

    print()

    # Update state file
    print("2. Updating trading_state.json...")
    state_file = Path('state/trading_state.json')

    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)

        print(f"   Old values:")
        print(f"     Balance: ${state.get('current_balance', 0):.2f}")
        print(f"     Peak: ${state.get('peak_balance', 0):.2f}")
        print(f"     Mode: {state.get('mode', 'unknown')}")
    else:
        print("   State file doesn't exist, creating new one...")
        state = {}

    # Update all relevant fields
    state['current_balance'] = current_balance
    state['peak_balance'] = current_balance
    state['day_start_balance'] = current_balance
    state['mode'] = 'normal'
    state['halt_reason'] = ''
    state['consecutive_losses'] = 0
    state['loss_streak_cost'] = 0.0
    state['daily_pnl'] = 0.0

    # Create state directory if it doesn't exist
    state_file.parent.mkdir(exist_ok=True)

    # Save
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

    print()
    print(f"   ✅ New values:")
    print(f"     Balance: ${current_balance:.2f}")
    print(f"     Peak: ${current_balance:.2f}")
    print(f"     Mode: normal")

    print()
    print("="*60)
    print("✅ Peak Balance Reset Complete!")
    print("="*60)
    print()
    print("Next steps:")
    print("  1. Stop the bot: pkill -f momentum_bot_v12.py")
    print("  2. Start the bot: python3 bot/momentum_bot_v12.py")
    print()
    print("OR on VPS:")
    print("  systemctl restart polymarket-bot")
    print()

if __name__ == '__main__':
    main()
