#!/usr/bin/env python3
"""
Local redemption script - redeems winning positions from your machine
Run this anytime you have positions at 100% that need redemption
"""

import requests
from web3 import Web3
from eth_account import Account
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configuration from environment
WALLET = os.getenv('POLYMARKET_WALLET')
PRIVATE_KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
RPC_URL = os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
CTF_ADDRESS = os.getenv('CTF_ADDRESS', '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')
USDC_ADDRESS = os.getenv('USDC_ADDRESS', '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')

# Validate required environment variables
if not WALLET or not PRIVATE_KEY:
    print("❌ Error: Missing required environment variables")
    print("Please set POLYMARKET_WALLET and POLYMARKET_PRIVATE_KEY in .env file")
    sys.exit(1)

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

def main():
    print("=" * 70)
    print("POLYMARKET REDEMPTION SCRIPT (Run Locally)")
    print("=" * 70)
    print()

    # Get positions
    print("Fetching positions...")
    positions = get_positions()

    # Find redeemable WINNING positions (current value > $1)
    redeemable = []
    for pos in positions:
        size = float(pos.get('size', 0))
        if size < 0.01:
            continue

        cur_price = float(pos.get('curPrice', 0))
        current_value = size * cur_price

        # Only redeem if redeemable AND has value (>= $1)
        if pos.get('redeemable', False) and current_value >= 1.0:
            redeemable.append(pos)

    print(f"Found {len(redeemable)} winning positions to redeem:")
    print()

    if not redeemable:
        print("✅ No winning positions to redeem!")
        print()

        # Check if there are worthless redeemable positions
        worthless = []
        for pos in positions:
            size = float(pos.get('size', 0))
            if size < 0.01:
                continue
            cur_price = float(pos.get('curPrice', 0))
            current_value = size * cur_price
            if pos.get('redeemable', False) and current_value < 1.0:
                worthless.append(pos)

        if worthless:
            print(f"(Found {len(worthless)} worthless positions marked 'redeemable' - these are losses)")

        return

    # Display redeemable positions
    total_value = 0
    for i, pos in enumerate(redeemable, 1):
        title = pos.get('title', 'Unknown')
        outcome = pos.get('outcome', '?')
        size = pos.get('size', 0)
        cur_price = pos.get('curPrice', 0)
        value = size * cur_price
        total_value += value

        print(f"{i}. {outcome}: {size:.0f} shares @ {cur_price*100:.1f}% = ${value:.2f}")
        print(f"   {title}")
        print()

    print(f"Total to redeem: ${total_value:.2f}")
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

    # Check current balance
    print(f"Wallet: {account.address}")
    print()

    # Process each redeemable position
    print("=" * 70)
    print("REDEEMING POSITIONS")
    print("=" * 70)
    print()

    for i, pos in enumerate(redeemable, 1):
        title = pos.get('title', 'Unknown')[:50]
        outcome = pos.get('outcome', '?')
        size = pos.get('size', 0)
        condition_id = pos.get('conditionId', '')
        outcome_index = pos.get('outcomeIndex', 0)
        value = size * pos.get('curPrice', 0)

        print(f"[{i}/{len(redeemable)}] Redeeming {outcome} - {title}")
        print(f"   Value: ${value:.2f}")

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

            print(f"   Building transaction (nonce: {nonce}, gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei)...")

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
            print(f"   🔗 https://polygonscan.com/tx/{tx_hash.hex()}")
            print(f"   ⏳ Waiting for confirmation...")

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"   ✅ Successfully redeemed ${value:.2f}!")
                print(f"   Gas used: {receipt['gasUsed']}")
            else:
                print(f"   ❌ Transaction failed")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

    print("=" * 70)
    print("REDEMPTION COMPLETE!")
    print("=" * 70)

if __name__ == "__main__":
    main()
