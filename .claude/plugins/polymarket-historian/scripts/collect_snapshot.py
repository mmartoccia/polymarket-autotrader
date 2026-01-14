#!/usr/bin/env python3
"""
Trade Data Collector - Snapshots current trading state

Collects:
- Current positions (active, winning, losing)
- Recent trades from logs
- Agent votes and decisions
- Balance and performance metrics
- Market regime
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
VPS_IP = os.getenv('VPS_IP', '216.238.85.11')
SSH_KEY = os.getenv('SSH_KEY', '~/.ssh/polymarket_vultr')
WALLET = os.getenv('POLYMARKET_WALLET', '0x52dF6Dc5DE31DD844d9E432A0821BC86924C2237')
STATE_DIR = "/opt/polymarket-autotrader/v12_state"
LOG_FILE = "/opt/polymarket-autotrader/bot.log"

# Plugin data directory
PLUGIN_DIR = Path(__file__).parent.parent
DATA_DIR = PLUGIN_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
DAILY_DIR = DATA_DIR / "daily"

# Ensure directories exist
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
DAILY_DIR.mkdir(parents=True, exist_ok=True)


def get_usdc_balance() -> Optional[float]:
    """Get current USDC balance from blockchain."""
    try:
        cmd = f'''ssh -i {SSH_KEY} root@{VPS_IP} 'python3 << "PYEOF"
import requests
wallet = "{WALLET}"
usdc = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
rpc = "https://polygon-rpc.com"
data = f"0x70a08231000000000000000000000000{{wallet[2:]}}"
resp = requests.post(rpc, json={{
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{{"to": usdc, "data": data}}, "latest"],
    "id": 1
}}, timeout=10)
balance = int(resp.json()["result"], 16) / 1e6
print(balance)
PYEOF
' 2>/dev/null'''

        result = os.popen(cmd).read().strip()
        return float(result) if result else None
    except:
        return None


def get_positions() -> Optional[Dict]:
    """Get current positions from Polymarket API."""
    try:
        resp = requests.get(
            'https://data-api.polymarket.com/positions',
            params={'user': WALLET, 'limit': 50},
            timeout=10
        )

        if resp.status_code != 200:
            return None

        positions = resp.json()

        # Categorize
        active = []
        redeemable = []
        losing = []

        for p in positions:
            size = float(p.get('size', 0))
            if size < 0.01:
                continue

            cur_price = float(p.get('curPrice', 0))
            current_value = size * cur_price
            entry = float(p.get('avg_entry_price', 0))

            # Extract crypto
            title = p.get('title', '')
            crypto = '?'
            if 'Bitcoin' in title or 'BTC' in title:
                crypto = 'BTC'
            elif 'Ethereum' in title or 'ETH' in title:
                crypto = 'ETH'
            elif 'Solana' in title or 'SOL' in title:
                crypto = 'SOL'
            elif 'XRP' in title or 'Ripple' in title:
                crypto = 'XRP'

            pos_data = {
                'crypto': crypto,
                'outcome': p.get('outcome', '?'),
                'size': size,
                'entry_price': entry,
                'current_price': cur_price,
                'current_value': current_value,
                'pnl': current_value - (size * entry),
                'title': title,
                'market_slug': p.get('market', ''),
                'condition_id': p.get('conditionId', '')
            }

            # Categorize
            is_redeemable = (p.get('redeemable', False) or cur_price >= 0.99) and current_value >= 1.0

            if is_redeemable:
                redeemable.append(pos_data)
            elif cur_price > 0.01 and current_value >= 0.10:
                active.append(pos_data)
            else:
                losing.append(pos_data)

        return {
            'active': active,
            'redeemable': redeemable,
            'losing': losing,
            'total_positions': len(active) + len(redeemable) + len(losing)
        }

    except Exception as e:
        print(f"Error getting positions: {e}")
        return None


def get_bot_state() -> Optional[Dict]:
    """Get bot trading state from VPS."""
    try:
        cmd = f'ssh -i {SSH_KEY} root@{VPS_IP} "cat {STATE_DIR}/trading_state.json" 2>/dev/null'
        result = os.popen(cmd).read().strip()
        if result:
            return json.loads(result)
    except:
        pass
    return None


def get_recent_trades(count: int = 50) -> List[Dict]:
    """Extract recent trades from bot logs."""
    try:
        cmd = f'''ssh -i {SSH_KEY} root@{VPS_IP} "tail -500 {LOG_FILE} | grep -E 'ORDER PLACED|WIN|LOSS|APPROVED|VETO'" 2>/dev/null'''
        result = os.popen(cmd).read().strip()

        if not result:
            return []

        trades = []
        lines = result.split('\n')

        for line in lines:
            # Parse trade info from log line
            # Example: "2026-01-14 03:30:15 - ORDER PLACED: BTC Up $0.25 (10 shares)"

            if 'ORDER PLACED' in line:
                trade = {'type': 'entry'}

                # Extract timestamp
                if ' - ' in line:
                    timestamp_str = line.split(' - ')[0]
                    try:
                        trade['timestamp'] = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').isoformat()
                    except:
                        trade['timestamp'] = None

                # Extract crypto
                for crypto in ['BTC', 'ETH', 'SOL', 'XRP']:
                    if crypto in line:
                        trade['crypto'] = crypto
                        break

                # Extract direction
                if ' Up ' in line or ' UP ' in line:
                    trade['direction'] = 'Up'
                elif ' Down ' in line or ' DOWN ' in line:
                    trade['direction'] = 'Down'

                # Extract price (pattern: $0.XX)
                import re
                price_match = re.search(r'\$(\d+\.\d+)', line)
                if price_match:
                    trade['entry_price'] = float(price_match.group(1))

                # Extract shares
                shares_match = re.search(r'(\d+)\s+shares', line)
                if shares_match:
                    trade['shares'] = int(shares_match.group(1))

                trades.append(trade)

            elif 'APPROVED' in line:
                # Extract agent decision info
                decision = {'type': 'approved'}

                # Extract confidence (pattern: Confidence: XX%)
                import re
                conf_match = re.search(r'Confidence:\s*(\d+)%', line)
                if conf_match:
                    decision['confidence'] = int(conf_match.group(1))

                # Extract weighted score (pattern: Score: 0.XXX)
                score_match = re.search(r'Score:\s*(\d+\.\d+)', line)
                if score_match:
                    decision['weighted_score'] = float(score_match.group(1))

                if trades:  # Associate with most recent trade
                    trades[-1]['decision'] = decision

        return trades[-count:]

    except Exception as e:
        print(f"Error getting recent trades: {e}")
        return []


def create_snapshot() -> Dict:
    """Create comprehensive snapshot of current trading state."""

    timestamp = datetime.now(timezone.utc)

    snapshot = {
        'timestamp': timestamp.isoformat(),
        'version': '1.0',
        'balance': get_usdc_balance(),
        'positions': get_positions(),
        'bot_state': get_bot_state(),
        'recent_trades': get_recent_trades(50),
        'metadata': {
            'wallet': WALLET,
            'vps_ip': VPS_IP,
            'collection_method': 'ssh+api'
        }
    }

    return snapshot


def save_snapshot(snapshot: Dict):
    """Save snapshot to timestamped file."""

    timestamp = datetime.fromisoformat(snapshot['timestamp'].replace('Z', '+00:00'))
    filename = timestamp.strftime('%Y-%m-%d_%H-%M-%S.json')
    filepath = SNAPSHOTS_DIR / filename

    with open(filepath, 'w') as f:
        json.dump(snapshot, f, indent=2)

    print(f"✅ Snapshot saved: {filepath}")

    # Also update daily aggregate
    update_daily_aggregate(snapshot)


def update_daily_aggregate(snapshot: Dict):
    """Update daily aggregate file with new snapshot."""

    timestamp = datetime.fromisoformat(snapshot['timestamp'].replace('Z', '+00:00'))
    date_str = timestamp.strftime('%Y-%m-%d')
    daily_file = DAILY_DIR / f"{date_str}.json"

    # Load existing or create new
    if daily_file.exists():
        with open(daily_file, 'r') as f:
            daily_data = json.load(f)
    else:
        daily_data = {
            'date': date_str,
            'snapshots': [],
            'summary': {}
        }

    # Add snapshot
    daily_data['snapshots'].append(snapshot)

    # Update summary
    all_trades = []
    for snap in daily_data['snapshots']:
        all_trades.extend(snap.get('recent_trades', []))

    daily_data['summary'] = {
        'total_snapshots': len(daily_data['snapshots']),
        'total_trades': len(all_trades),
        'final_balance': snapshot.get('balance'),
        'final_positions': snapshot.get('positions', {}).get('total_positions', 0)
    }

    # Save
    with open(daily_file, 'w') as f:
        json.dump(daily_data, f, indent=2)

    print(f"✅ Daily aggregate updated: {daily_file}")


def main():
    """Main collection routine."""

    print("=" * 70)
    print("POLYMARKET HISTORIAN - DATA COLLECTION")
    print("=" * 70)
    print()

    print("Collecting snapshot...")
    snapshot = create_snapshot()

    # Print summary
    print()
    print("SNAPSHOT SUMMARY:")
    print(f"  Timestamp: {snapshot['timestamp']}")
    print(f"  Balance: ${snapshot['balance']:.2f}" if snapshot['balance'] else "  Balance: N/A")

    if snapshot['positions']:
        pos = snapshot['positions']
        print(f"  Active Positions: {len(pos.get('active', []))}")
        print(f"  Redeemable: {len(pos.get('redeemable', []))} (${sum(p['current_value'] for p in pos.get('redeemable', [])):.2f})")
        print(f"  Losing: {len(pos.get('losing', []))}")

    print(f"  Recent Trades: {len(snapshot['recent_trades'])}")

    if snapshot['bot_state']:
        state = snapshot['bot_state']
        print(f"  Mode: {state.get('mode', 'unknown').upper()}")
        print(f"  Daily P&L: ${state.get('daily_pnl', 0):.2f}")

    print()

    # Save
    save_snapshot(snapshot)

    print()
    print("=" * 70)
    print("Collection complete! Use /historian-patterns to analyze.")
    print("=" * 70)


if __name__ == "__main__":
    main()
