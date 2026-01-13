#!/usr/bin/env python3
"""
Quick Status - Single snapshot of bot status (no auto-refresh)
"""
import requests
import json
import os
from datetime import datetime, timezone

WALLET = os.getenv("POLYMARKET_WALLET", "0x52dF6Dc5DE31DD844d9E432A0821BC86924C2237")

def get_usdc_balance():
    """Get USDC balance from blockchain."""
    try:
        rpc_url = 'https://polygon-rpc.com'
        usdc_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'

        response = requests.post(rpc_url, json={
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{
                'to': usdc_address,
                'data': f'0x70a08231000000000000000000000000{WALLET[2:]}'
            }, 'latest'],
            'id': 1
        }, timeout=5)

        balance_hex = response.json().get('result', '0x0')
        return int(balance_hex, 16) / 1e6
    except:
        return 0

def get_positions():
    """Get positions from Polymarket API."""
    try:
        resp = requests.get(
            f"https://data-api.polymarket.com/positions?user={WALLET}&limit=20",
            timeout=10
        )
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def main():
    print("=" * 80)
    print("POLYMARKET BOT - QUICK STATUS")
    print("=" * 80)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # Balance
    balance = get_usdc_balance()
    print(f"💰 Balance: ${balance:.2f}")

    # State
    try:
        with open('state/trading_state.json', 'r') as f:
            state = json.load(f)

        print(f"📊 Mode: {state.get('mode', 'unknown').upper()}")
        print(f"📈 Daily P&L: ${state.get('daily_pnl', 0):.2f}")
        print(f"🎯 Peak Balance: ${state.get('peak_balance', 0):.2f}")
        print(f"✅ Total Wins: {state.get('total_wins', 0)}")
        print(f"📊 Total Trades: {state.get('total_trades', 0)}")
    except:
        print("⚠️  Could not read state file")

    print()

    # Positions
    positions = get_positions()
    open_positions = [p for p in positions if float(p.get('size', 0)) > 0.01]

    print(f"📈 Open Positions: {len(open_positions)}")

    if open_positions:
        print()
        for i, pos in enumerate(open_positions[:5], 1):
            outcome = pos.get('outcome', 'Unknown')
            size = float(pos.get('size', 0))
            cur_price = float(pos.get('curPrice', 0))
            value = size * cur_price
            max_payout = size * 1.0

            title = pos.get('title', 'Unknown')[:60]

            print(f"  [{i}] {outcome}: {size:.0f} shares @ {cur_price*100:.1f}%")
            print(f"      {title}")
            print(f"      Value: ${value:.2f} | Max: ${max_payout:.2f}")
            print()

    print("=" * 80)

if __name__ == "__main__":
    main()
