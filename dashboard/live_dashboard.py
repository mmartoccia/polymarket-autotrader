#!/usr/bin/env python3
"""
Live Polymarket Trading Dashboard - Real-time monitoring with auto-refresh
"""

import requests
import time
import os
import json
import sys
from datetime import datetime, timezone

WALLET = "0x52dF6Dc5DE31DD844d9E432A0821BC86924C2237"
REFRESH_INTERVAL = 10  # seconds

# Set TERM immediately to prevent errors
if 'TERM' not in os.environ:
    os.environ['TERM'] = 'xterm-256color'

def clear_screen():
    """Clear terminal screen."""
    try:
        os.system('clear' if os.name == 'posix' else 'cls')
    except:
        print('\n' * 50)

def get_usdc_balance():
    """Get current USDC balance from blockchain."""
    try:
        rpc_url = 'https://polygon-rpc.com'
        usdc_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        data = '0x70a08231000000000000000000000000' + WALLET[2:].lower()

        response = requests.post(rpc_url, json={
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{'to': usdc_address, 'data': data}, 'latest'],
            'id': 1
        }, timeout=10)

        balance_hex = response.json().get('result', '0x0')
        return int(balance_hex, 16) / 1e6
    except:
        return None

def get_current_epoch_time():
    """Get time into current 15-minute epoch."""
    current_time = int(time.time())
    epoch_start = (current_time // 900) * 900
    time_in_epoch = current_time - epoch_start
    time_remaining = 900 - time_in_epoch
    return time_in_epoch, time_remaining

def get_bot_state():
    """Read bot trading state."""
    try:
        with open('/opt/polymarket-autotrader/v12_state/trading_state.json', 'r') as f:
            return json.load(f)
    except:
        return None

def get_ralph_state():
    """Read Ralph regime state."""
    try:
        with open('/opt/polymarket-autotrader/.ralph_regime_state.json', 'r') as f:
            return json.load(f)
    except:
        return None

def get_market_details(market_id):
    """Fetch market details from Gamma API."""
    try:
        resp = requests.get(
            f'https://gamma-api.polymarket.com/markets/{market_id}',
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def get_price_to_beat(slug, outcome):
    """
    Get the price to beat (epoch start price) for a position.

    For Up: Need crypto to end ABOVE start price
    For Down: Need crypto to end BELOW start price

    Returns: (price_to_beat, current_crypto_price, direction_needed)
    """
    try:
        # Fetch market by slug
        resp = requests.get(
            f'https://gamma-api.polymarket.com/markets?slug={slug}',
            timeout=5
        )
        if resp.status_code != 200:
            return None, None, None

        markets = resp.json()
        if not markets:
            return None, None, None

        market = markets[0] if isinstance(markets, list) else markets

        # Extract crypto and direction from outcome (e.g., "BTC Up" or "SOL Down")
        parts = outcome.split()
        if len(parts) < 2:
            return None, None, None

        crypto = parts[0]  # BTC, ETH, SOL, XRP
        direction = parts[1]  # Up or Down

        # Get epoch start price from market metadata
        # The market should have start_price or we can infer from question
        question = market.get('question', '')

        # Try to extract start price from question
        # Example: "Will BTC be higher than $43,521.50 at 9:15 PM?"
        import re
        price_match = re.search(r'\$([0-9,]+\.?\d*)', question)
        if price_match:
            start_price = float(price_match.group(1).replace(',', ''))

            # Get current crypto price
            current_price = get_current_crypto_price(crypto)

            return start_price, current_price, direction

    except Exception as e:
        pass

    return None, None, None

def get_current_crypto_price(crypto):
    """Get current price for a crypto from Binance."""
    try:
        symbol_map = {
            'BTC': 'BTCUSDT',
            'Bitcoin': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'Ethereum': 'ETHUSDT',
            'SOL': 'SOLUSDT',
            'Solana': 'SOLUSDT',
            'XRP': 'XRPUSDT'
        }

        symbol = symbol_map.get(crypto)
        if not symbol:
            return None

        resp = requests.get(
            f'https://api.binance.com/api/v3/ticker/price',
            params={'symbol': symbol},
            timeout=3
        )

        if resp.status_code == 200:
            return float(resp.json()['price'])
    except:
        pass

    return None

def get_positions():
    """Get all positions categorized by status."""
    try:
        resp = requests.get(
            'https://data-api.polymarket.com/positions',
            params={'user': WALLET, 'limit': 50},
            timeout=10
        )

        if resp.status_code != 200:
            return None

        positions = resp.json()
        
        open_positions = []
        resolved_winners = []
        resolved_losers = []
        awaiting_resolution = []
        
        for pos in positions:
            size = float(pos.get('size', 0))
            if size < 0.01:
                continue

            outcome = pos.get('outcome', 'Unknown')
            cur_price = float(pos.get('curPrice', 0))

            # Get title directly from position (more reliable than market object)
            question = pos.get('title', 'Unknown Market')

            # Get redeemable status
            redeemable = pos.get('redeemable', False)

            # Check market resolution status (if market object exists)
            market = pos.get('market', {})
            resolved = market.get('resolved', False) if market else False
            closed = market.get('closed', False) if market else False

            current_value = size * cur_price
            max_payout = size * 1.0
            win_prob = cur_price

            position_data = {
                'outcome': outcome,
                'question': question[:70],
                'size': size,
                'cur_price': cur_price,
                'current_value': current_value,
                'max_payout': max_payout,
                'win_prob': win_prob,
                'resolved': resolved,
                'closed': closed,
                'redeemable': redeemable,
                'slug': pos.get('slug')
            }

            if resolved:
                winning_outcome = market.get('winning_outcome', '')
                if outcome == winning_outcome:
                    resolved_winners.append(position_data)
                else:
                    resolved_losers.append(position_data)
            elif closed:
                awaiting_resolution.append(position_data)
            else:
                # Filter out worthless positions (0% win prob or < $0.10 value)
                if win_prob <= 0.01 or current_value < 0.10:
                    continue  # Skip displaying worthless positions

                # Check redeemable status AND has value (only show winners worth $1+)
                if (redeemable or win_prob >= 0.99) and current_value >= 1.0:
                    position_data['status'] = 'READY_REDEEM'
                    open_positions.append(position_data)
                elif win_prob <= 0.01 or current_value < 1.0:
                    position_data['status'] = 'LIKELY_LOSS'
                    open_positions.append(position_data)
                else:
                    position_data['status'] = 'ACTIVE'
                    open_positions.append(position_data)
        
        return {
            'open': open_positions,
            'resolved_winners': resolved_winners,
            'resolved_losers': resolved_losers,
            'awaiting': awaiting_resolution
        }
    except Exception as e:
        return None

def render_dashboard():
    """Render the complete dashboard."""
    clear_screen()
    
    # Header
    print("=" * 80)
    print(" " * 20 + "🤖 POLYMARKET LIVE TRADING DASHBOARD")
    print("=" * 80)
    print(f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | 🔄 Refreshing every {REFRESH_INTERVAL}s")
    print()
    
    # System Status
    print("🖥️  SYSTEM STATUS")
    print("-" * 80)
    
    # Bot State
    bot_state = get_bot_state()
    if bot_state:
        mode = bot_state.get('mode', 'unknown')
        mode_emoji = "🟢" if mode == 'normal' else "🔴" if mode == 'halted' else "🟡"
        
        current_balance = bot_state.get('current_balance', 0)
        day_start = bot_state.get('day_start_balance', 0)
        daily_pnl = current_balance - day_start
        pnl_pct = (daily_pnl / day_start * 100) if day_start > 0 else 0
        
        print(f"{mode_emoji} Bot Mode: {mode.upper()}")
        print(f"💰 Balance: ${current_balance:.2f}")
        print(f"📊 Daily P&L: ${daily_pnl:+.2f} ({pnl_pct:+.1f}%)")
        
        if bot_state.get('halt_reason'):
            print(f"⚠️  Halt Reason: {bot_state['halt_reason']}")
    else:
        print("⚠️  Could not read bot state")
    
    # Ralph State
    ralph_state = get_ralph_state()
    if ralph_state:
        regime = ralph_state.get('regime', 'Unknown')
        regime_emoji = "🐂" if regime == 'BULL' else "🐻" if regime == 'BEAR' else "⚡" if regime == 'VOLATILE' else "➡️"
        
        params = ralph_state.get('params', {})
        strategy = params.get('strategy_focus', 'unknown')
        
        print(f"{regime_emoji} Market Regime: {regime}")
        print(f"🎯 Strategy: {strategy}")
        print(f"📏 Signal Strength: {params.get('MIN_SIGNAL_STRENGTH', 'N/A')}")
        contrarian_max = params.get('CONTRARIAN_MAX_ENTRY', 'N/A')
        if isinstance(contrarian_max, float):
            print(f"💵 Contrarian Max: ${contrarian_max:.2f}")
        else:
            print(f"💵 Contrarian Max: {contrarian_max}")
    
    # Blockchain Balance
    blockchain_balance = get_usdc_balance()
    if blockchain_balance is not None:
        print(f"🔗 Blockchain Balance: ${blockchain_balance:.2f}")
    
    # Epoch Timer
    time_in, time_remaining = get_current_epoch_time()
    mins_remaining = time_remaining // 60
    secs_remaining = time_remaining % 60
    progress = int((time_in / 900) * 40)
    bar = "█" * progress + "░" * (40 - progress)
    print(f"⏱️  Epoch Timer: [{bar}] {mins_remaining}m {secs_remaining}s remaining")
    
    print()
    
    # Positions
    positions = get_positions()
    if not positions:
        print("⚠️  Could not fetch positions")
        return
    
    open_pos = positions['open']
    resolved_wins = positions['resolved_winners']
    resolved_losses = positions['resolved_losers']
    awaiting = positions['awaiting']
    
    # Separate ready-to-redeem positions
    ready_redeem = [p for p in open_pos if p.get('status') == 'READY_REDEEM']
    active_pos = [p for p in open_pos if p.get('status') != 'READY_REDEEM']
    
    # Ready to Redeem (100% winners)
    if ready_redeem:
        total_redeem = sum(p['current_value'] for p in ready_redeem)
        print("💰 READY TO REDEEM (AUTO-REDEEMER RUNS EVERY 5 MIN)")
        print("-" * 80)
        for i, pos in enumerate(ready_redeem, 1):
            redeem_status = "✓ Redeemable" if pos.get('redeemable') else "⏳ Pending"
            print(f"🟢 [{i}] {pos['outcome']}: {pos['size']:.0f} shares @ {pos['cur_price']*100:.1f}%")
            print(f"    {pos['question']}")
            print(f"    💵 Will Redeem: ${pos['current_value']:.2f} | {redeem_status}")
        print(f"\n✅ Total Pending Redemption: ${total_redeem:.2f}")
        print()
    
    # Active Open Positions
    if active_pos:
        print("📈 ACTIVE POSITIONS")
        print("-" * 80)

        # Calculate totals
        total_current_value = sum(p['current_value'] for p in active_pos)
        total_max_payout = sum(p['max_payout'] for p in active_pos)

        # Estimate amount invested (shares bought at their initial price)
        # We approximate by assuming entry price ≈ max(0.50, current_price)
        # This is an estimate since we don't track actual entry prices
        total_invested = sum(p['size'] * max(0.50, p['cur_price']) for p in active_pos)

        # Calculate unrealized P&L (current value vs estimated investment)
        unrealized_pnl = total_current_value - total_invested
        pnl_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0

        for i, pos in enumerate(active_pos, 1):
            status_emoji = "🔴" if pos.get('status') == 'LIKELY_LOSS' else "🟡"

            prob_pct = pos['win_prob'] * 100
            bar_length = int(prob_pct / 2.5)
            bar = "█" * bar_length + "░" * (40 - bar_length)

            # Estimate entry price for this position
            est_entry = max(0.50, pos['cur_price'])
            est_invested = pos['size'] * est_entry

            print(f"\n{status_emoji} [{i}] {pos['outcome']}: {pos['size']:.0f} shares @ {pos['cur_price']*100:.1f}%")
            print(f"    {pos['question']}")
            print(f"    Win Prob: [{bar}] {prob_pct:.1f}%")

            # Show current crypto price and position status
            # Extract crypto from slug (format: "btc-updown-15m-...", "sol-updown-15m-...", etc)
            slug = pos.get('slug', '')
            direction = pos['outcome']  # "Up" or "Down"

            if slug and direction:
                # Get crypto ticker from slug (first part before hyphen)
                crypto_ticker = slug.split('-')[0].upper() if slug else None

                if crypto_ticker:
                    current_price = get_current_crypto_price(crypto_ticker)
                    if current_price:
                        # Show current price with position direction
                        arrow = "↑" if direction == "Up" else "↓" if direction == "Down" else ""
                        print(f"    📊 {crypto_ticker} Current Price: ${current_price:,.2f} {arrow} | Market Prob: {pos['cur_price']*100:.1f}%")

            print(f"    Current Value: ${pos['current_value']:.2f} | If Win: ${pos['max_payout']:.2f} | Est. Invested: ${est_invested:.2f}")

        print(f"\n💰 SUMMARY:")
        print(f"   Current Value: ${total_current_value:.2f} (what your shares are worth now)")
        print(f"   If All Win: ${total_max_payout:.2f} (max payout if everything wins)")
        print(f"   Est. Invested: ${total_invested:.2f} (approx capital tied up)")
        print(f"   Unrealized P&L: ${unrealized_pnl:+.2f} ({pnl_pct:+.1f}%)")
        print()
    
    if not ready_redeem and not active_pos:
        print("📈 OPEN POSITIONS: None")
        print()
    
    # Awaiting Resolution
    if awaiting:
        print(f"⏳ AWAITING RESOLUTION ({len(awaiting)})")
        print("-" * 80)
        for pos in awaiting:
            print(f"  • {pos['outcome']}: {pos['size']:.0f} shares - {pos['question']}")
        print()
    
    # Resolved Winners
    if resolved_wins:
        total_won = sum(p['max_payout'] for p in resolved_wins)
        print(f"✅ RESOLVED WINNERS ({len(resolved_wins)}) - Total: ${total_won:.2f}")
        print("-" * 80)
        for pos in resolved_wins[:5]:
            print(f"  ✅ {pos['outcome']}: {pos['size']:.0f} shares = ${pos['max_payout']:.2f}")
        if len(resolved_wins) > 5:
            print(f"  ... and {len(resolved_wins) - 5} more")
        print()
    
    # Resolved Losers
    if resolved_losses:
        total_lost = sum(p['current_value'] for p in resolved_losses)
        print(f"❌ RESOLVED LOSSES ({len(resolved_losses)}) - Lost: ${total_lost:.2f}")
        print("-" * 80)
        for pos in resolved_losses[:3]:
            print(f"  ❌ {pos['outcome']}: {pos['size']:.0f} shares - ${pos['current_value']:.2f} lost")
        if len(resolved_losses) > 3:
            print(f"  ... and {len(resolved_losses) - 3} more")
        print()
    
    print("=" * 80)
    print("💡 Press Ctrl+C to exit | Dashboard updates every 10 seconds")
    print("=" * 80)
    
    sys.stdout.flush()

def main():
    """Main loop."""
    print("Starting live dashboard...")
    time.sleep(1)
    
    try:
        while True:
            render_dashboard()
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        clear_screen()
        print("\n👋 Dashboard stopped. Goodbye!")
        print()

if __name__ == "__main__":
    main()
