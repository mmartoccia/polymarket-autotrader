#!/usr/bin/env python3
"""
Cleanup script - redeems worthless positions to clear them from the UI
These are 0% losers that clutter the dashboard but can be redeemed to remove them
"""

import requests
from web3 import Web3
from eth_account import Account
import os
from dotenv import load_dotenv
import argparse

# Load environment variables
load_dotenv()

# Configuration from environment
WALLET = os.getenv('POLYMARKET_WALLET')
PRIVATE_KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
RPC_URL = "https://polygon-rpc.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# CTF ABI for redemption
CTF_ABI = [{
    "inputs": [
        {"name": "collateralToken", "type": "address"},
        {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"},
        {"name": "indexSets", "type": "uint256[]"}
    ],
    "name": "redeemPositions",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]

def get_positions():
    """Get all positions."""
    resp = requests.get(
        "https://data-api.polymarket.com/positions",
        params={"user": WALLET, "limit": 100},
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json()
    return []

def main(skip_confirmation=False):
    print("=" * 70)
    print("CLEANUP SCRIPT - Remove Worthless Positions")
    print("=" * 70)
    print()
    print("This redeems 0% losers to clear them from your dashboard.")
    print("⚠️  You won't get any money - these are expired losses.")
    print("Purpose: Clean up UI clutter")
    print()

    # Get positions
    print("Fetching positions...")
    positions = get_positions()

    # Find worthless redeemable positions (0% but marked redeemable)
    worthless = []
    for pos in positions:
        size = float(pos.get('size', 0))
        if size < 0.01:
            continue

        cur_price = float(pos.get('curPrice', 0))
        current_value = size * cur_price

        # Only cleanup if redeemable AND worthless (< $0.10)
        if pos.get('redeemable', False) and current_value < 0.10:
            worthless.append(pos)

    print(f"Found {len(worthless)} worthless positions to cleanup:")
    print()

    if not worthless:
        print("✅ No worthless positions to cleanup!")
        return

    # Display positions
    for i, pos in enumerate(worthless, 1):
        title = pos.get('title', 'Unknown')
        outcome = pos.get('outcome', '?')
        size = pos.get('size', 0)
        cur_price = pos.get('curPrice', 0)
        value = size * cur_price

        print(f"{i}. {outcome}: {size:.0f} shares @ {cur_price*100:.1f}% = ${value:.2f}")
        print(f"   {title}")
        print()

    # Confirm
    print("⚠️  These positions are worthless ($0). Redeeming will:")
    print("   • Remove them from your dashboard")
    print("   • Cost ~$0.10-0.15 in gas per position")
    print("   • NOT give you any money back")
    print()
    if not skip_confirmation:
        response = input("Continue? (yes/no): ").strip().lower()

        if response != 'yes':
            print("Cancelled.")
            return

    print()

    # Connect to blockchain
    print("Connecting to Polygon...")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Failed to connect to Polygon RPC")
        return

    print("✅ Connected to Polygon")
    account = Account.from_key(PRIVATE_KEY)
    ctf = w3.eth.contract(address=CTF_ADDRESS, abi=CTF_ABI)

    print(f"Wallet: {account.address}")
    print()

    # Process each worthless position
    print("=" * 70)
    print("CLEANING UP POSITIONS")
    print("=" * 70)
    print()

    success_count = 0
    for i, pos in enumerate(worthless, 1):
        title = pos.get('title', 'Unknown')[:50]
        outcome = pos.get('outcome', '?')
        size = pos.get('size', 0)
        condition_id = pos.get('conditionId', '')
        outcome_index = pos.get('outcomeIndex', 0)

        print(f"[{i}/{len(worthless)}] Cleaning up {outcome} - {title}")

        if not condition_id:
            print("   ❌ Missing condition ID, skipping")
            continue

        try:
            # Convert condition_id to bytes32
            condition_bytes = bytes.fromhex(condition_id[2:] if condition_id.startswith('0x') else condition_id)

            # Index set: 1 for outcome 0, 2 for outcome 1
            index_set = 1 << outcome_index

            # Build transaction
            nonce = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price

            print(f"   Building transaction (nonce: {nonce}, gas: {w3.from_wei(gas_price, 'gwei'):.2f} gwei)...")

            tx = ctf.functions.redeemPositions(
                USDC_ADDRESS,
                bytes(32),  # parentCollectionId = 0
                condition_bytes,
                [index_set]
            ).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': gas_price,
                'chainId': 137  # Polygon mainnet
            })

            # Sign and send
            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            print(f"   📤 Transaction sent: {tx_hash.hex()}")
            print(f"   ⏳ Waiting for confirmation...")

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"   ✅ Position cleaned up!")
                print(f"   Gas used: {receipt['gasUsed']}, Cost: ~${w3.from_wei(receipt['gasUsed'] * gas_price, 'ether') * 3000:.2f}")
                success_count += 1
            else:
                print(f"   ❌ Transaction failed")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

    print("=" * 70)
    print(f"CLEANUP COMPLETE! Removed {success_count}/{len(worthless)} positions")
    print("=" * 70)
    print()
    print("These positions should now be gone from your dashboard.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleanup worthless Polymarket positions')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    main(skip_confirmation=args.yes)
