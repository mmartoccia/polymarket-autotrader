#!/usr/bin/env python3
"""
Unified Polymarket Trading Dashboard
Combines agent decisions, positions, balance, and real-time monitoring
"""

import requests
import time
import os
import json
import sys
from datetime import datetime, timezone

# VPS Configuration
VPS_IP = "216.238.85.11"
SSH_KEY = "~/.ssh/polymarket_vultr"
WALLET = "0x52dF6Dc5DE31DD844d9E432A0821BC86924C2237"
STATE_DIR = "/opt/polymarket-autotrader/v12_state"
LOG_FILE = "/opt/polymarket-autotrader/bot.log"

REFRESH_INTERVAL = 5  # seconds

# Set TERM to prevent errors
if 'TERM' not in os.environ:
    os.environ['TERM'] = 'xterm-256color'

def clear_screen():
    """Clear terminal screen."""
    print('\033[2J\033[H', end='')

def get_usdc_balance():
    """Get current USDC balance from blockchain via VPS."""
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

def get_bot_state():
    """Read bot trading state from VPS."""
    try:
        cmd = f'ssh -i {SSH_KEY} root@{VPS_IP} "cat {STATE_DIR}/trading_state.json" 2>/dev/null'
        result = os.popen(cmd).read().strip()
        if result:
            return json.loads(result)
    except:
        pass
    return None

def get_current_epoch_time():
    """Get time into current 15-minute epoch."""
    current_time = int(time.time())
    epoch_start = (current_time // 900) * 900
    time_in_epoch = current_time - epoch_start
    time_remaining = 900 - time_in_epoch

    epoch_start_dt = datetime.fromtimestamp(epoch_start, tz=timezone.utc)
    epoch_end_dt = datetime.fromtimestamp(epoch_start + 900, tz=timezone.utc)

    return time_in_epoch, time_remaining, epoch_start_dt, epoch_end_dt

def get_positions():
    """Get current positions from Polymarket."""
    try:
        resp = requests.get(
            'https://data-api.polymarket.com/positions',
            params={'user': WALLET, 'limit': 30},
            timeout=5
        )

        if resp.status_code != 200:
            return None

        all_positions = resp.json()

        # Categorize positions
        active = []  # size > 0, value > 0
        losing = []  # size > 0, value = 0

        for p in all_positions:
            size = float(p.get('size', 0))
            value = float(p.get('value', 0))

            if size > 0:
                # Extract crypto from market name
                market = p.get('market', '')
                crypto = '?'
                if 'Bitcoin' in market or 'BTC' in market:
                    crypto = 'BTC'
                elif 'Ethereum' in market or 'ETH' in market:
                    crypto = 'ETH'
                elif 'Solana' in market or 'SOL' in market:
                    crypto = 'SOL'
                elif 'XRP' in market or 'Ripple' in market:
                    crypto = 'XRP'

                p['crypto'] = crypto

                if value > 0:
                    active.append(p)
                else:
                    losing.append(p)

        return {
            'active': active,
            'losing': losing
        }
    except Exception as e:
        return None

def get_recent_agent_decisions():
    """Get recent agent decisions from bot logs."""
    try:
        cmd = f'''ssh -i {SSH_KEY} root@{VPS_IP} "tail -200 {LOG_FILE} | grep -E '✅ APPROVED|❌ VETO|AGENTS SKIP|ORDER PLACED|Contrarian filter' | tail -10" 2>/dev/null'''
        result = os.popen(cmd).read().strip()
        return result.split('\n') if result else []
    except:
        return []

def get_recent_trades_with_confidence():
    """Get recent trades with confidence scores from bot logs."""
    try:
        cmd = f'''ssh -i {SSH_KEY} root@{VPS_IP} "tail -500 {LOG_FILE} | grep -B1 'ORDER PLACED' | grep -E 'Confidence:|ORDER PLACED' | tail -20" 2>/dev/null'''
        result = os.popen(cmd).read().strip()

        trades = []
        lines = result.split('\n') if result else []

        i = 0
        while i < len(lines):
            line = lines[i]
            # Look for pattern: "Confidence: XX% | Strategy: agent_consensus"
            if 'Confidence:' in line and 'Strategy:' in line:
                # Extract crypto, direction, confidence from context
                parts = line.split('|')
                confidence = 0
                for part in parts:
                    if 'Confidence:' in part:
                        try:
                            confidence = int(part.split(':')[1].strip().rstrip('%'))
                        except:
                            pass

                # Check if next line is ORDER PLACED
                if i + 1 < len(lines) and 'ORDER PLACED' in lines[i + 1]:
                    trades.append({'confidence': confidence, 'line': line})
            i += 1

        return trades[-5:]  # Last 5 trades
    except:
        return []

def format_pnl(value):
    """Format P&L with color."""
    if value > 0:
        return f"\033[92m+${value:.2f}\033[0m"  # Green
    elif value < 0:
        return f"\033[91m${value:.2f}\033[0m"  # Red
    else:
        return f"${value:.2f}"

def format_percentage(value):
    """Format percentage with color."""
    if value > 0:
        return f"\033[92m+{value:.1f}%\033[0m"  # Green
    elif value < 0:
        return f"\033[91m{value:.1f}%\033[0m"  # Red
    else:
        return f"{value:.1f}%"

def run_dashboard():
    """Main dashboard loop."""
    while True:
        try:
            clear_screen()

            # Header
            now = datetime.now(timezone.utc)
            print("═" * 100)
            print(f"{'🤖 POLYMARKET AGENT TRADING DASHBOARD':^100}")
            print(f"{now.strftime('%Y-%m-%d %H:%M:%S UTC'):^100}")
            print("═" * 100)
            print()

            # Balance & State Section
            print("┌─ 💰 BALANCE & STATUS " + "─" * 76 + "┐")

            state = get_bot_state()
            balance = get_usdc_balance()

            if state and balance is not None:
                mode = state.get('mode', 'unknown').upper()
                day_start = state.get('day_start_balance', 0)
                peak = state.get('peak_balance', 0)
                daily_pnl = balance - day_start if day_start > 0 else 0
                pnl_pct = (daily_pnl / day_start * 100) if day_start > 0 else 0
                drawdown = ((peak - balance) / peak * 100) if peak > 0 else 0

                print(f"│ Balance: ${balance:.2f}  |  Mode: {mode}  |  Peak: ${peak:.2f}  |  Drawdown: {drawdown:.1f}%")
                print(f"│ Today P&L: {format_pnl(daily_pnl)} ({format_percentage(pnl_pct)})  |  Day Start: ${day_start:.2f}")
            else:
                print("│ Unable to fetch balance/state")

            print("└" + "─" * 99 + "┘")
            print()

            # Epoch Timing Section
            time_in_epoch, time_remaining, epoch_start, epoch_end = get_current_epoch_time()
            progress = int((time_in_epoch / 900) * 50)
            progress_bar = "█" * progress + "░" * (50 - progress)

            print("┌─ ⏰ CURRENT EPOCH " + "─" * 79 + "┐")
            print(f"│ {epoch_start.strftime('%H:%M')} → {epoch_end.strftime('%H:%M UTC')}  |  {time_in_epoch}s / 900s  |  {time_remaining}s remaining")
            print(f"│ [{progress_bar}] {(time_in_epoch/900*100):.1f}%")
            print("└" + "─" * 99 + "┘")
            print()

            # Open Positions Section
            print("┌─ 📊 OPEN POSITIONS " + "─" * 78 + "┐")

            positions = get_positions()
            if positions:
                active = positions.get('active', [])
                losing = positions.get('losing', [])

                if active:
                    print(f"│ \033[92mACTIVE ({len(active)} positions with value):\033[0m")
                    for p in active[:8]:
                        crypto = p['crypto']
                        outcome = p.get('outcome', '?')
                        size = float(p.get('size', 0))
                        value = float(p.get('value', 0))
                        entry = float(p.get('avg_entry_price', 0))
                        cost = size * entry
                        pnl = value - cost
                        market = p.get('market', 'Unknown')

                        # Extract time from market name if present
                        market_short = market
                        if ' - ' in market:
                            parts = market.split(' - ')
                            if len(parts) >= 2:
                                market_short = parts[-1][:45]  # Last part (time range)
                        else:
                            market_short = market[:45]

                        status_icon = "📈" if pnl > 0 else "📉"
                        print(f"│   {status_icon} {crypto:>3} {outcome:>4}: {market_short}")
                        print(f"│        {size:>3.0f} shares @ ${entry:.3f} → ${value:.2f} ({format_pnl(pnl)})")
                else:
                    print("│ \033[93mNo active positions with value\033[0m")

                if losing:
                    print(f"│")
                    print(f"│ \033[91mLOSING ({len(losing)} positions at 0% value):\033[0m")
                    # Group by crypto
                    crypto_counts = {}
                    for p in losing:
                        crypto = p['crypto']
                        outcome = p.get('outcome', '?')
                        key = f"{crypto} {outcome}"
                        crypto_counts[key] = crypto_counts.get(key, 0) + 1

                    for key, count in sorted(crypto_counts.items())[:5]:
                        print(f"│   ❌ {key}: {count} position(s)")
            else:
                print("│ Unable to fetch positions")

            print("└" + "─" * 99 + "┘")
            print()

            # Recent Agent Decisions Section
            print("┌─ 🧠 RECENT AGENT DECISIONS " + "─" * 70 + "┐")

            decisions = get_recent_agent_decisions()
            if decisions:
                for decision in decisions[-8:]:  # Last 8 decisions
                    # Clean up log timestamp
                    if ' - ' in decision:
                        decision = decision.split(' - ', 1)[1]

                    # Color code decisions
                    if '✅ APPROVED' in decision:
                        decision = f"\033[92m{decision}\033[0m"
                    elif '❌ VETO' in decision or 'BLOCKED' in decision or 'Contrarian filter' in decision:
                        decision = f"\033[91m{decision}\033[0m"
                    elif 'SKIP' in decision:
                        decision = f"\033[93m{decision}\033[0m"

                    # Truncate long lines
                    if len(decision) > 95:
                        decision = decision[:92] + "..."

                    print(f"│ {decision}")
            else:
                print("│ No recent decisions found")

            print("└" + "─" * 99 + "┘")
            print()

            # Recent Trades with Confidence Section
            print("┌─ 📈 RECENT TRADES & CONFIDENCE " + "─" * 64 + "┐")

            recent_trades = get_recent_trades_with_confidence()
            if recent_trades:
                for trade in recent_trades:
                    conf = trade['confidence']
                    line = trade['line']

                    # Extract crypto and direction from line
                    crypto = "?"
                    direction = "?"
                    if '[BTC]' in line or 'BTC' in line:
                        crypto = 'BTC'
                    elif '[ETH]' in line or 'ETH' in line:
                        crypto = 'ETH'
                    elif '[SOL]' in line or 'SOL' in line:
                        crypto = 'SOL'
                    elif '[XRP]' in line or 'XRP' in line:
                        crypto = 'XRP'

                    if 'Up' in line:
                        direction = 'Up'
                    elif 'Down' in line:
                        direction = 'Down'

                    # Color code confidence
                    if conf >= 60:
                        conf_str = f"\033[92m{conf}%\033[0m"  # Green
                        conf_bar = "█" * 6
                    elif conf >= 40:
                        conf_str = f"\033[93m{conf}%\033[0m"  # Yellow
                        conf_bar = "█" * 4 + "░" * 2
                    elif conf >= 20:
                        conf_str = f"\033[91m{conf}%\033[0m"  # Red
                        conf_bar = "█" * 2 + "░" * 4
                    else:
                        conf_str = f"\033[91m{conf}%\033[0m"  # Red
                        conf_bar = "█" * 1 + "░" * 5

                    arrow = "↗" if direction == "Up" else "↘"
                    print(f"│ {crypto:>3} {arrow} {direction:>4}  [{conf_bar}] {conf_str}")
            else:
                print("│ No recent trades found")

            print("└" + "─" * 99 + "┘")
            print()

            # Footer
            print("─" * 100)
            print(f"{'🔄 Refreshing every 5 seconds  |  Press Ctrl+C to exit':^100}")
            print("─" * 100)

            # Wait before refresh
            time.sleep(REFRESH_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n👋 Dashboard stopped\n")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    run_dashboard()
