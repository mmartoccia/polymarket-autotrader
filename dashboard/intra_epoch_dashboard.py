#!/usr/bin/env python3
"""
Intra-Epoch Momentum Dashboard (with Granular Signals)

Real-time visualization of 1-minute candle patterns within each 15-minute epoch.
Shows momentum buildup and predicted outcome probability for BTC, ETH, SOL, XRP.
Includes live Polymarket prices for Up/Down markets.

ENHANCED FEATURES (Jan 17, 2026):
- Shadow mode indicator (when running alongside live bot)
- Multi-exchange confluence display (Binance, Kraken, Coinbase)
- Magnitude tracking visualization
- Granular signal comparison logging
- Recent shadow trade display
"""

import os
import sys
import time
import re
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GOLD = "\033[38;5;220m"  # Gold/amber color for active trades
MAGENTA = "\033[95m"
BG_BLUE = "\033[44m"

# Exchange symbols for multi-exchange confluence
EXCHANGE_SYMBOLS = {
    'BTC': {'binance': 'BTCUSDT', 'kraken': 'XBTUSD', 'coinbase': 'BTC-USD'},
    'ETH': {'binance': 'ETHUSDT', 'kraken': 'ETHUSD', 'coinbase': 'ETH-USD'},
    'SOL': {'binance': 'SOLUSDT', 'kraken': 'SOLUSD', 'coinbase': 'SOL-USD'},
    'XRP': {'binance': 'XRPUSDT', 'kraken': 'XRPUSD', 'coinbase': 'XRP-USD'},
}

# File paths
BASE_PATH = Path(__file__).parent.parent
INTRA_LOG = BASE_PATH / "intra_epoch_bot.log"
GRANULAR_LOG = BASE_PATH / "granular_signals.log"

# Decision thresholds (must match bot config)
MIN_CUMULATIVE_MAGNITUDE = 0.0003  # 0.03% total move required
MIN_EXCHANGES_AGREE = 2           # Require 2 of 3 exchanges to agree
MIN_PATTERN_ACCURACY = 0.735      # 73.5% minimum pattern accuracy
EDGE_BUFFER = 0.05                # Entry price must be accuracy - 5%

# Track epoch start prices for confluence calculation
_epoch_start_prices: Dict[str, Dict[str, float]] = {}
_last_epoch_start: int = 0


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from string."""
    return re.sub(r'\033\[[0-9;]*m', '', text)


def visible_len(text: str) -> int:
    """Get visible length of string (excluding ANSI codes)."""
    return len(strip_ansi(text))


def pad_right(text: str, width: int) -> str:
    """Pad text to width, accounting for ANSI codes."""
    visible = visible_len(text)
    padding = width - visible
    return text + ' ' * max(0, padding)


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def load_active_positions() -> Dict[str, dict]:
    """Load active positions from state file."""
    state_file = Path(__file__).parent.parent / "state" / "intra_epoch_state.json"
    try:
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                return state.get('positions', {})
    except Exception:
        pass
    return {}


def get_current_epoch() -> Tuple[int, int]:
    """Get current epoch start and time elapsed."""
    now = int(time.time())
    epoch_start = now // 900 * 900
    time_in_epoch = now - epoch_start
    return epoch_start, time_in_epoch


def is_shadow_mode_active() -> bool:
    """Check if intra-epoch bot is running in shadow mode."""
    try:
        if INTRA_LOG.exists():
            with open(INTRA_LOG, 'r') as f:
                lines = f.readlines()[-100:]
                for line in reversed(lines):
                    if 'SHADOW MODE' in line:
                        return True
                    if 'INTRA-EPOCH MOMENTUM BOT STARTING' in line and 'SHADOW' not in line:
                        return False
    except Exception:
        pass
    return False


def fetch_exchange_price(exchange: str, symbol: str) -> Optional[float]:
    """Fetch price from a specific exchange."""
    try:
        if exchange == 'binance':
            resp = requests.get(
                'https://api.binance.com/api/v3/ticker/price',
                params={'symbol': symbol},
                timeout=2
            )
            if resp.status_code == 200:
                return float(resp.json()['price'])
        elif exchange == 'kraken':
            kraken_map = {'XBTUSD': 'XXBTZUSD', 'ETHUSD': 'XETHZUSD', 'SOLUSD': 'SOLUSD', 'XRPUSD': 'XXRPZUSD'}
            pair = kraken_map.get(symbol, symbol)
            resp = requests.get('https://api.kraken.com/0/public/Ticker', params={'pair': pair}, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('result'):
                    key = list(data['result'].keys())[0]
                    return float(data['result'][key]['c'][0])
        elif exchange == 'coinbase':
            resp = requests.get(f'https://api.coinbase.com/v2/prices/{symbol}/spot', timeout=2)
            if resp.status_code == 200:
                return float(resp.json()['data']['amount'])
    except Exception:
        pass
    return None


def get_multi_exchange_prices(crypto: str) -> Dict[str, Optional[float]]:
    """Fetch prices from all exchanges for a crypto in parallel."""
    symbols = EXCHANGE_SYMBOLS.get(crypto, {})
    prices = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            'binance': executor.submit(fetch_exchange_price, 'binance', symbols.get('binance', '')),
            'kraken': executor.submit(fetch_exchange_price, 'kraken', symbols.get('kraken', '')),
            'coinbase': executor.submit(fetch_exchange_price, 'coinbase', symbols.get('coinbase', '')),
        }
        for name, future in futures.items():
            try:
                prices[name] = future.result(timeout=3)
            except Exception:
                prices[name] = None

    return prices


def get_exchange_confluence(crypto: str, epoch_start_prices: Dict[str, float]) -> Dict:
    """
    Check if multiple exchanges agree on direction from epoch start.
    Returns confluence data including direction agreement.
    """
    current_prices = get_multi_exchange_prices(crypto)

    directions = {}
    for exchange, current in current_prices.items():
        start = epoch_start_prices.get(exchange)
        if current and start:
            if current > start:
                directions[exchange] = 'Up'
            elif current < start:
                directions[exchange] = 'Down'
            else:
                directions[exchange] = 'Flat'

    # Count agreement
    up_count = sum(1 for d in directions.values() if d == 'Up')
    down_count = sum(1 for d in directions.values() if d == 'Down')

    if up_count >= 2:
        consensus = 'Up'
        agreement = up_count
    elif down_count >= 2:
        consensus = 'Down'
        agreement = down_count
    else:
        consensus = None
        agreement = max(up_count, down_count)

    return {
        'prices': current_prices,
        'directions': directions,
        'consensus': consensus,
        'agreement': agreement,
        'total': len([d for d in directions.values() if d])
    }


def get_decision_factors(crypto: str, data: Optional[dict], prices: Optional[Dict],
                         confluence: Optional[Dict], pattern_dir: Optional[str],
                         pattern_acc: float) -> Dict:
    """
    Analyze all decision factors and return a summary of why trade would/wouldn't happen.

    Returns dict with:
    - pattern: {passes: bool, reason: str}
    - magnitude: {passes: bool, value: float, reason: str}
    - confluence: {passes: bool, agreement: int, direction: str, reason: str}
    - entry_price: {passes: bool, price: float, max_price: float, reason: str}
    - overall: {would_trade: bool, block_reason: str or None}
    """
    factors = {
        'pattern': {'passes': False, 'reason': 'No pattern'},
        'magnitude': {'passes': False, 'value': 0.0, 'reason': 'No data'},
        'confluence': {'passes': False, 'agreement': 0, 'direction': None, 'reason': 'No data'},
        'entry_price': {'passes': False, 'price': 0.0, 'max_price': 0.0, 'reason': 'No prices'},
        'overall': {'would_trade': False, 'block_reason': 'Waiting for data'}
    }

    # 1. Pattern check
    if pattern_dir and pattern_acc >= MIN_PATTERN_ACCURACY:
        factors['pattern'] = {
            'passes': True,
            'reason': f'{pattern_dir} @ {pattern_acc:.0%}'
        }
    elif pattern_dir:
        factors['pattern'] = {
            'passes': False,
            'reason': f'{pattern_dir} @ {pattern_acc:.0%} < {MIN_PATTERN_ACCURACY:.0%}'
        }
    else:
        factors['pattern'] = {
            'passes': False,
            'reason': 'No clear pattern'
        }

    # 2. Magnitude check
    if data:
        net_mag = data.get('net_magnitude', 0) / 100.0  # Convert from pct to decimal
        mag_dir = data.get('magnitude_direction', 'Flat')
        passes_mag = net_mag >= MIN_CUMULATIVE_MAGNITUDE

        factors['magnitude'] = {
            'passes': passes_mag,
            'value': net_mag * 100,  # Back to pct for display
            'reason': f'{net_mag*100:.3f}% {"≥" if passes_mag else "<"} {MIN_CUMULATIVE_MAGNITUDE*100:.2f}%'
        }

    # 3. Confluence check
    if confluence:
        conf_dir = confluence.get('consensus')
        agreement = confluence.get('agreement', 0)
        total = confluence.get('total', 0)

        if conf_dir is None:
            # No consensus = would block
            factors['confluence'] = {
                'passes': False,
                'agreement': agreement,
                'direction': None,
                'reason': f'No consensus ({agreement}/{total} agree) - CHOPPY'
            }
        elif pattern_dir and conf_dir != pattern_dir:
            # Mismatch = would block
            factors['confluence'] = {
                'passes': False,
                'agreement': agreement,
                'direction': conf_dir,
                'reason': f'Mismatch: pattern={pattern_dir}, exchanges={conf_dir}'
            }
        else:
            # Agreement
            factors['confluence'] = {
                'passes': True,
                'agreement': agreement,
                'direction': conf_dir,
                'reason': f'{agreement}/{total} agree {conf_dir}'
            }

    # 4. Entry price check
    if prices and pattern_dir:
        entry_price = prices.get(pattern_dir, {}).get('ask', 0.99)
        max_entry = pattern_acc - EDGE_BUFFER
        passes_price = entry_price <= max_entry

        factors['entry_price'] = {
            'passes': passes_price,
            'price': entry_price,
            'max_price': max_entry,
            'reason': f'${entry_price:.2f} {"≤" if passes_price else ">"} ${max_entry:.2f} max'
        }

    # 5. Overall decision
    all_pass = (factors['pattern']['passes'] and
                factors['magnitude']['passes'] and
                factors['confluence']['passes'] and
                factors['entry_price']['passes'])

    if all_pass:
        factors['overall'] = {
            'would_trade': True,
            'block_reason': None
        }
    else:
        # Find first blocking reason
        if not factors['pattern']['passes']:
            block = f"Pattern: {factors['pattern']['reason']}"
        elif not factors['magnitude']['passes']:
            block = f"Magnitude: {factors['magnitude']['reason']}"
        elif not factors['confluence']['passes']:
            block = f"Confluence: {factors['confluence']['reason']}"
        elif not factors['entry_price']['passes']:
            block = f"Entry: {factors['entry_price']['reason']}"
        else:
            block = "Unknown"

        factors['overall'] = {
            'would_trade': False,
            'block_reason': block
        }

    return factors


def get_recent_shadow_trades(limit: int = 5) -> List[str]:
    """Get recent shadow trade entries from log."""
    trades = []
    try:
        if INTRA_LOG.exists():
            with open(INTRA_LOG, 'r') as f:
                lines = f.readlines()[-500:]
                for line in reversed(lines):
                    if '🔮 SHADOW ORDER' in line:
                        # Extract just the relevant part
                        parts = line.split('|')
                        if len(parts) >= 3:
                            trades.append(parts[-1].strip())
                        else:
                            trades.append(line.strip()[-60:])
                        if len(trades) >= limit:
                            break
    except Exception:
        pass
    return list(reversed(trades))


def get_recent_granular_signals(limit: int = 3) -> List[str]:
    """Get recent granular signal comparison entries."""
    signals = []
    try:
        if GRANULAR_LOG.exists():
            with open(GRANULAR_LOG, 'r') as f:
                lines = f.readlines()[-50:]
                for line in reversed(lines):
                    if '[GRANULAR]' in line:
                        # Extract just the comparison part
                        parts = line.split('[GRANULAR]')
                        if len(parts) > 1:
                            signals.append(parts[1].strip()[:70])
                        if len(signals) >= limit:
                            break
    except Exception:
        pass
    return list(reversed(signals))


def calculate_magnitude(minutes_data: List[dict]) -> Tuple[float, str]:
    """
    Calculate cumulative magnitude of price moves.
    Returns (total_magnitude_pct, direction).
    """
    if not minutes_data:
        return 0.0, 'Flat'

    up_mag = 0.0
    down_mag = 0.0

    for m in minutes_data:
        if not m.get('incomplete', False):
            change_pct = abs(m.get('change_pct', 0))
            if m.get('direction') == 'Up':
                up_mag += change_pct
            else:
                down_mag += change_pct

    net = up_mag - down_mag
    direction = 'Up' if net > 0 else 'Down' if net < 0 else 'Flat'
    return abs(net), direction


def fetch_epoch_minutes(crypto: str, epoch_start: int) -> Optional[dict]:
    """Fetch 1-minute candles for the current epoch with price data."""
    try:
        symbol = f"{crypto}USDT"
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '1m',
            'startTime': epoch_start * 1000,
            'limit': 15
        }

        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return None

        klines = resp.json()
        if not klines:
            return None

        minutes = []
        epoch_start_price = float(klines[0][1])  # Open price of first candle
        current_price = float(klines[-1][4])      # Close price of last candle

        total_up_mag = 0.0
        total_down_mag = 0.0

        for k in klines[:-1]:  # Skip last (incomplete)
            open_p = float(k[1])
            close_p = float(k[4])
            change_pct = ((close_p - open_p) / open_p) * 100 if open_p > 0 else 0
            direction = 'Up' if close_p > open_p else 'Down'

            if direction == 'Up':
                total_up_mag += abs(change_pct)
            else:
                total_down_mag += abs(change_pct)

            minutes.append({
                'direction': direction,
                'change_pct': change_pct,
                'incomplete': False
            })

        # Add current incomplete candle
        if klines:
            k = klines[-1]
            open_p = float(k[1])
            close_p = float(k[4])
            change_pct = ((close_p - open_p) / open_p) * 100 if open_p > 0 else 0
            minutes.append({
                'direction': 'Up' if close_p > open_p else 'Down',
                'change_pct': change_pct,
                'incomplete': True
            })

        # Calculate net magnitude
        net_magnitude = total_up_mag - total_down_mag
        magnitude_direction = 'Up' if net_magnitude > 0 else 'Down' if net_magnitude < 0 else 'Flat'

        return {
            'minutes': minutes,
            'epoch_start_price': epoch_start_price,
            'current_price': current_price,
            'price_change': current_price - epoch_start_price,
            'price_change_pct': ((current_price - epoch_start_price) / epoch_start_price) * 100,
            'total_up_magnitude': total_up_mag,
            'total_down_magnitude': total_down_mag,
            'net_magnitude': abs(net_magnitude),
            'magnitude_direction': magnitude_direction
        }
    except Exception:
        return None


def fetch_polymarket_prices(crypto: str, epoch_start: int) -> Optional[Dict[str, float]]:
    """Fetch current Polymarket prices for Up/Down markets."""
    try:
        slug = f"{crypto.lower()}-updown-15m-{epoch_start}"

        # Get market from Gamma API
        resp = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=3)
        if resp.status_code != 200 or not resp.json():
            return None

        event = resp.json()[0]
        markets = event.get("markets", [])
        if not markets:
            return None

        # Get CLOB data for prices
        cid = markets[0].get("conditionId")
        clob = requests.get(f"https://clob.polymarket.com/markets/{cid}", timeout=3)
        if clob.status_code != 200:
            return None

        tokens = clob.json().get("tokens", [])
        prices = {}

        for t in tokens:
            outcome = t.get("outcome", "")
            token_id = t.get("token_id", "")
            if not token_id:
                continue

            try:
                book_resp = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=2)
                book = book_resp.json()
                asks = book.get("asks", [])
                bids = book.get("bids", [])

                # Best ask (what you pay to buy)
                best_ask = float(asks[-1]["price"]) if asks else 0.99
                # Best bid (what you get to sell)
                best_bid = float(bids[0]["price"]) if bids else 0.01

                prices[outcome] = {
                    'ask': best_ask,
                    'bid': best_bid,
                    'mid': (best_ask + best_bid) / 2
                }
            except Exception:
                continue

        return prices if prices else None

    except Exception:
        return None


def analyze_pattern(minutes: List[dict]) -> Tuple[Optional[str], float, str]:
    """Analyze minute patterns and return (direction, probability, description)."""
    if not minutes:
        return (None, 0.5, 'Waiting for data...')

    completed = [m for m in minutes if not m.get('incomplete', False)]

    if len(completed) < 3:
        return (None, 0.5, f'Need {3 - len(completed)} more minutes...')

    # Pattern 1: 4+ of first 5 minutes
    if len(completed) >= 5:
        first_5 = completed[:5]
        ups_5 = sum(1 for m in first_5 if m['direction'] == 'Up')
        downs_5 = 5 - ups_5

        if ups_5 >= 4:
            return ('Up', 0.797, f'{ups_5}/5 first mins UP = 79.7% UP')
        elif downs_5 >= 4:
            return ('Down', 0.740, f'{downs_5}/5 first mins DOWN = 74.0% DOWN')

    # Pattern 2: All first 3 minutes same direction
    first_3 = completed[:3]
    if all(m['direction'] == 'Up' for m in first_3):
        return ('Up', 0.780, 'All 3 first mins UP = 78.0% UP')
    elif all(m['direction'] == 'Down' for m in first_3):
        return ('Down', 0.739, 'All 3 first mins DOWN = 73.9% DOWN')

    # Pattern 3: Weaker - 3 of first 5 same direction
    if len(completed) >= 5:
        first_5 = completed[:5]
        ups_5 = sum(1 for m in first_5 if m['direction'] == 'Up')

        if ups_5 >= 3:
            return ('Up', 0.65, f'{ups_5}/5 first mins UP = ~65% UP')
        elif ups_5 <= 2:
            downs_5 = 5 - ups_5
            return ('Down', 0.65, f'{downs_5}/5 first mins DOWN = ~65% DOWN')

    # No clear pattern
    ups = sum(1 for m in completed if m['direction'] == 'Up')
    downs = len(completed) - ups
    return (None, 0.5, f'Mixed: {ups} up, {downs} down (no signal)')


def render_crypto_panel(crypto: str, data: Optional[dict], time_in_epoch: int,
                        prices: Optional[Dict] = None,
                        active_position: Optional[dict] = None) -> List[str]:
    """Render a single crypto panel with prices and price-based winning/losing."""
    W = 38  # Panel inner width (excluding borders)
    lines = []

    # Extract data
    if data:
        minutes = data.get('minutes', [])
        epoch_start_price = data.get('epoch_start_price', 0)
        current_price = data.get('current_price', 0)
        price_change = data.get('price_change', 0)
        price_change_pct = data.get('price_change_pct', 0)
        net_magnitude = data.get('net_magnitude', 0)
        magnitude_direction = data.get('magnitude_direction', 'Flat')
        up_mag = data.get('total_up_magnitude', 0)
        down_mag = data.get('total_down_magnitude', 0)
    else:
        minutes = []
        epoch_start_price = 0
        current_price = 0
        price_change = 0
        price_change_pct = 0
        net_magnitude = 0
        magnitude_direction = 'Flat'
        up_mag = 0
        down_mag = 0

    direction, probability, description = analyze_pattern(minutes)
    completed = [m for m in minutes if not m.get('incomplete', False)]
    current = [m for m in minutes if m.get('incomplete', False)]

    # Header with gold star if active position
    has_position = active_position is not None
    if has_position:
        star_prefix = f"{GOLD}{BOLD}★{RESET} "
        visible_name_len = len(crypto) + 2  # star + space + crypto
    else:
        star_prefix = ""
        visible_name_len = len(crypto)

    if direction == 'Up':
        crypto_colored = f"{GREEN}{BOLD}{crypto}{RESET}"
    elif direction == 'Down':
        crypto_colored = f"{RED}{BOLD}{crypto}{RESET}"
    else:
        crypto_colored = f"{CYAN}{BOLD}{crypto}{RESET}"

    header = f"{star_prefix}{crypto_colored}"

    lines.append(f"┌{'─' * W}┐")
    # Center the header
    header_pad = (W - visible_name_len) // 2
    lines.append(f"│{' ' * header_pad}{header}{' ' * (W - header_pad - visible_name_len)}│")
    lines.append(f"├{'─' * W}┤")

    # Build minute row with fixed-width columns
    def make_row(start: int, end: int, label: str) -> str:
        # Each arrow slot is 3 chars wide for alignment
        symbols = []
        for i in range(start, end):
            if i < len(completed):
                if completed[i]['direction'] == 'Up':
                    symbols.append(f" {GREEN}▲{RESET} ")
                else:
                    symbols.append(f" {RED}▼{RESET} ")
            elif i == len(completed) and current:
                if current[0]['direction'] == 'Up':
                    symbols.append(f"{DIM}[{GREEN}▲{RESET}{DIM}]{RESET}")
                else:
                    symbols.append(f"{DIM}[{RED}▼{RESET}{DIM}]{RESET}")
            else:
                symbols.append(f" {DIM}·{RESET} ")

        row_content = f"{label}" + "".join(symbols)
        return row_content

    row1 = make_row(0, 5, "Min 1-5:  ")
    row2 = make_row(5, 10, "Min 6-10: ")
    row3 = make_row(10, 15, "Min 11-15:")

    lines.append(f"│ {pad_right(row1, W-2)} │")
    lines.append(f"│ {pad_right(row2, W-2)} │")
    lines.append(f"│ {pad_right(row3, W-2)} │")
    lines.append(f"├{'─' * W}┤")

    # Polymarket prices
    if prices and 'Up' in prices and 'Down' in prices:
        up_ask = prices['Up'].get('ask', 0.50)
        down_ask = prices['Down'].get('ask', 0.50)
        price_line = f"Market: {GREEN}UP ${up_ask:.2f}{RESET}  {RED}DN ${down_ask:.2f}{RESET}"
        lines.append(f"│ {pad_right(price_line, W-2)} │")
    else:
        price_line = f"{DIM}Market: No prices available{RESET}"
        lines.append(f"│ {pad_right(price_line, W-2)} │")

    # Count
    ups = sum(1 for m in completed if m['direction'] == 'Up')
    downs = len(completed) - ups
    count_line = f"Count: {GREEN}{ups}▲{RESET} {RED}{downs}▼{RESET}"
    lines.append(f"│ {pad_right(count_line, W-2)} │")

    # Magnitude (granular signal enhancement)
    if net_magnitude > 0:
        mag_color = GREEN if magnitude_direction == 'Up' else RED if magnitude_direction == 'Down' else YELLOW
        mag_arrow = '↑' if magnitude_direction == 'Up' else '↓' if magnitude_direction == 'Down' else '→'
        # Show if magnitude is strong enough for boost (>0.8%)
        if net_magnitude >= 0.8:
            boost_indicator = f" {MAGENTA}+boost{RESET}"
        else:
            boost_indicator = ""
        mag_line = f"Magnitude: {mag_color}{mag_arrow}{net_magnitude:.2f}%{RESET}{boost_indicator}"
        lines.append(f"│ {pad_right(mag_line, W-2)} │")

    # Prediction
    if direction == 'Up':
        pred_line = f"Predict: {GREEN}{probability:.0%} UP{RESET}"
    elif direction == 'Down':
        pred_line = f"Predict: {RED}{probability:.0%} DOWN{RESET}"
    else:
        pred_line = f"Predict: {YELLOW}50% ???{RESET}"
    lines.append(f"│ {pad_right(pred_line, W-2)} │")

    # Value indicator - show if prediction aligns with cheap entry
    if direction and prices:
        entry_price = prices.get(direction, {}).get('ask', 0.99)
        if entry_price <= 0.25:
            value_line = f"{GREEN}{BOLD}★ VALUE: ${entry_price:.2f} entry!{RESET}"
        elif entry_price <= 0.35:
            value_line = f"{GREEN}● Good: ${entry_price:.2f} entry{RESET}"
        elif entry_price <= 0.50:
            value_line = f"{YELLOW}○ Fair: ${entry_price:.2f} entry{RESET}"
        else:
            value_line = f"{RED}✗ Expensive: ${entry_price:.2f}{RESET}"
        lines.append(f"│ {pad_right(value_line, W-2)} │")
    else:
        lines.append(f"│ {pad_right(f'{DIM}○ No signal yet{RESET}', W-2)} │")

    # Price change line - show epoch start vs current
    if epoch_start_price > 0 and current_price > 0:
        arrow = "↑" if price_change > 0 else "↓" if price_change < 0 else "→"
        change_color = GREEN if price_change > 0 else RED if price_change < 0 else YELLOW
        price_line = f"Price: {change_color}{arrow} {price_change_pct:+.2f}%{RESET}"
        lines.append(f"│ {pad_right(price_line, W-2)} │")
    else:
        lines.append(f"│ {pad_right(f'{DIM}Price: Waiting...{RESET}', W-2)} │")

    # Winning/Losing status - based on ACTUAL PRICE vs prediction
    if direction and epoch_start_price > 0 and current_price > 0:
        # Determine winning based on price movement vs prediction
        if direction == 'Up':
            is_winning = current_price > epoch_start_price
        else:  # direction == 'Down'
            is_winning = current_price < epoch_start_price

        if is_winning:
            status_line = f"{GREEN}{BOLD}📈 WINNING{RESET} (pred {direction})"
        elif current_price == epoch_start_price:
            status_line = f"{YELLOW}⚖️  TIED{RESET} (pred {direction})"
        else:
            status_line = f"{RED}{BOLD}📉 LOSING{RESET} (pred {direction})"
        lines.append(f"│ {pad_right(status_line, W-2)} │")
    else:
        lines.append(f"│ {pad_right(f'{DIM}○ Waiting for signal...{RESET}', W-2)} │")

    # Window status
    if 180 <= time_in_epoch <= 600:
        win_line = f"{GREEN}● ACTIVE WINDOW{RESET}"
    elif time_in_epoch < 180:
        win_line = f"{YELLOW}○ Window in {180 - time_in_epoch}s{RESET}"
    else:
        win_line = f"{DIM}○ Window closed{RESET}"
    lines.append(f"│ {pad_right(win_line, W-2)} │")

    lines.append(f"└{'─' * W}┘")

    return lines


def render_dashboard(data: Dict[str, List[dict]], prices_data: Dict[str, Dict],
                     epoch_start: int, time_in_epoch: int, shadow_mode: bool = False):
    """Render the full dashboard with prices."""
    clear_screen()

    # Load active positions
    active_positions = load_active_positions()

    epoch_time = datetime.fromtimestamp(epoch_start, tz=timezone.utc)
    epoch_end = datetime.fromtimestamp(epoch_start + 900, tz=timezone.utc)
    minutes_elapsed = time_in_epoch // 60
    seconds_elapsed = time_in_epoch % 60

    # Header box - 80 chars wide
    W = 80
    print()
    print(f"{CYAN}╔{'═' * (W-2)}╗{RESET}")

    # Title with shadow mode indicator
    if shadow_mode:
        title = "🔮 INTRA-EPOCH DASHBOARD - SHADOW MODE 🔮"
        title_color = MAGENTA
    else:
        title = "INTRA-EPOCH MOMENTUM DASHBOARD"
        title_color = ""
    title_pad = (W - 2 - len(title.replace('🔮', '  '))) // 2  # Account for emoji width
    print(f"{CYAN}║{RESET}{' ' * title_pad}{title_color}{BOLD}{title}{RESET}{' ' * max(0, W - 2 - title_pad - len(title.replace('🔮', '  ')))}{CYAN}║{RESET}")
    print(f"{CYAN}╠{'═' * (W-2)}╣{RESET}")

    # Epoch line
    epoch_str = f"Epoch: {epoch_time.strftime('%H:%M')} - {epoch_end.strftime('%H:%M')} UTC"
    print(f"{CYAN}║{RESET} {epoch_str:<{W-4}} {CYAN}║{RESET}")

    # Progress bar
    progress = time_in_epoch / 900
    bar_width = 50
    filled = int(progress * bar_width)
    bar_visual = '█' * filled + '░' * (bar_width - filled)
    time_str = f"{minutes_elapsed:02d}:{seconds_elapsed:02d}"
    prog_line = f"Progress: [{GREEN}{bar_visual[:filled]}{RESET}{DIM}{bar_visual[filled:]}{RESET}] {time_str} / 15:00"
    print(f"{CYAN}║{RESET} {pad_right(prog_line, W-4)} {CYAN}║{RESET}")

    # Window status
    if 180 <= time_in_epoch <= 600:
        win_str = f"{GREEN}● TRADING WINDOW ACTIVE (minutes 3-10){RESET}"
    elif time_in_epoch < 180:
        win_str = f"{YELLOW}○ Waiting for minute 3 ({180 - time_in_epoch}s remaining){RESET}"
    else:
        win_str = f"{DIM}○ Trading window closed{RESET}"
    print(f"{CYAN}║{RESET} {pad_right(win_str, W-4)} {CYAN}║{RESET}")

    print(f"{CYAN}╚{'═' * (W-2)}╝{RESET}")
    print()

    # Render panels with prices and active positions
    cryptos = ['BTC', 'ETH', 'SOL', 'XRP']
    panels = [render_crypto_panel(c, data.get(c), time_in_epoch, prices_data.get(c),
                                  active_positions.get(c))
              for c in cryptos]

    # Normalize panel heights - find max length and pad shorter panels
    max_len = max(len(p) for p in panels)
    panel_width = 40  # Width of each panel including borders
    empty_line = f"│{' ' * 38}│"  # Empty line with borders for padding

    for p in panels:
        while len(p) < max_len:
            # Insert empty line before the closing border
            p.insert(-1, empty_line)

    # Print top row (BTC, ETH)
    for i in range(len(panels[0])):
        print(f"  {panels[0][i]}  {panels[1][i]}")
    print()

    # Print bottom row (SOL, XRP)
    for i in range(len(panels[2])):
        print(f"  {panels[2][i]}  {panels[3][i]}")

    # Shadow trades section (if shadow mode active)
    if shadow_mode:
        shadow_trades = get_recent_shadow_trades(5)
        if shadow_trades:
            print()
            print(f"  {MAGENTA}┌{'─' * 76}┐{RESET}")
            print(f"  {MAGENTA}│{RESET} {BOLD}Recent Shadow Trades{RESET}{' ' * 55}{MAGENTA}│{RESET}")
            print(f"  {MAGENTA}├{'─' * 76}┤{RESET}")
            for trade in shadow_trades:
                # Truncate if needed
                display_trade = trade[:74] if len(trade) > 74 else trade
                print(f"  {MAGENTA}│{RESET} {display_trade:<74} {MAGENTA}│{RESET}")
            print(f"  {MAGENTA}└{'─' * 76}┘{RESET}")

        # Granular signal comparison
        granular_signals = get_recent_granular_signals(3)
        if granular_signals:
            print()
            print(f"  {CYAN}┌{'─' * 76}┐{RESET}")
            print(f"  {CYAN}│{RESET} {BOLD}Granular Signal Comparison (Old vs New){RESET}{' ' * 35}{CYAN}│{RESET}")
            print(f"  {CYAN}├{'─' * 76}┤{RESET}")
            for sig in granular_signals:
                display_sig = sig[:74] if len(sig) > 74 else sig
                print(f"  {CYAN}│{RESET} {display_sig:<74} {CYAN}│{RESET}")
            print(f"  {CYAN}└{'─' * 76}┘{RESET}")

    # Legend
    print()
    print(f"  {DIM}Legend: {GREEN}▲{RESET}{DIM}=Up  {RED}▼{RESET}{DIM}=Down  ·=Pending  [▲]=Current  {GOLD}★{RESET}{DIM}=Active Trade{RESET}")
    print(f"  {DIM}Patterns: 4+/5 same = 74-80%  |  All 3 same = 74-78%  |  3/5 same = ~65%{RESET}")
    print(f"  {DIM}Value: ★ ≤$0.25 | ● ≤$0.35 | ○ ≤$0.50 | ✗ >$0.50  |  {MAGENTA}+boost{RESET}{DIM} = magnitude ≥0.8%{RESET}")
    print()
    print(f"  {DIM}Refreshing every 5s. Press Ctrl+C to exit.{RESET}")


def render_decision_summary(decision_factors: Dict[str, Dict], time_in_epoch: int):
    """Render a decision summary panel showing why each crypto would/wouldn't trade."""
    W = 80

    print()
    print(f"  {YELLOW}┌{'─' * (W-4)}┐{RESET}")
    print(f"  {YELLOW}│{RESET} {BOLD}DECISION FACTORS{RESET} (why the bot would/wouldn't trade){' ' * 24}{YELLOW}│{RESET}")
    print(f"  {YELLOW}├{'─' * (W-4)}┤{RESET}")

    # Header row
    header = f"  {'Crypto':<6} {'Pattern':<12} {'Magnitude':<14} {'Confluence':<18} {'Entry':<12} {'Decision':<10}"
    print(f"  {YELLOW}│{RESET}{DIM}{header[2:]:<{W-6}}{RESET}{YELLOW}│{RESET}")
    print(f"  {YELLOW}├{'─' * (W-4)}┤{RESET}")

    for crypto, factors in decision_factors.items():
        # Pattern indicator
        if factors['pattern']['passes']:
            pattern_str = f"{GREEN}✓{RESET} {factors['pattern']['reason'][:9]}"
        else:
            pattern_str = f"{RED}✗{RESET} {factors['pattern']['reason'][:9]}"

        # Magnitude indicator
        if factors['magnitude']['passes']:
            mag_str = f"{GREEN}✓{RESET} {factors['magnitude']['value']:.3f}%"
        else:
            mag_str = f"{RED}✗{RESET} {factors['magnitude']['value']:.3f}%"

        # Confluence indicator
        conf = factors['confluence']
        if conf['passes']:
            conf_str = f"{GREEN}✓{RESET} {conf['agreement']}/3 {conf['direction'] or '?'}"
        elif conf['direction'] is None and conf['agreement'] > 0:
            conf_str = f"{RED}✗{RESET} {conf['agreement']}/3 CHOPPY"
        elif conf['direction']:
            conf_str = f"{RED}✗{RESET} {conf['agreement']}/3 {conf['direction']}"
        else:
            conf_str = f"{DIM}· waiting{RESET}"

        # Entry price indicator
        if factors['entry_price']['passes']:
            entry_str = f"{GREEN}✓{RESET} ${factors['entry_price']['price']:.2f}"
        elif factors['entry_price']['price'] > 0:
            entry_str = f"{RED}✗{RESET} ${factors['entry_price']['price']:.2f}"
        else:
            entry_str = f"{DIM}· n/a{RESET}"

        # Overall decision
        if factors['overall']['would_trade']:
            decision_str = f"{GREEN}{BOLD}TRADE{RESET}"
        else:
            decision_str = f"{RED}BLOCK{RESET}"

        # Build row - need to handle ANSI codes for padding
        row = f"  {crypto:<6}"
        print(f"  {YELLOW}│{RESET} {crypto:<6} {pad_right(pattern_str, 12)} {pad_right(mag_str, 14)} {pad_right(conf_str, 18)} {pad_right(entry_str, 12)} {pad_right(decision_str, 10)}{YELLOW}│{RESET}")

    print(f"  {YELLOW}├{'─' * (W-4)}┤{RESET}")

    # Show blocking reasons for blocked trades
    blocked = [(c, f['overall']['block_reason']) for c, f in decision_factors.items()
               if not f['overall']['would_trade'] and f['overall']['block_reason'] != 'Waiting for data']

    if blocked:
        print(f"  {YELLOW}│{RESET} {RED}Blocked:{RESET}{' ' * (W-14)}{YELLOW}│{RESET}")
        for crypto, reason in blocked[:3]:  # Show up to 3
            block_line = f"  {crypto}: {reason}"
            print(f"  {YELLOW}│{RESET} {block_line:<{W-6}}{YELLOW}│{RESET}")
    else:
        note = "All checks shown above. Green ✓ = pass, Red ✗ = fail/block"
        print(f"  {YELLOW}│{RESET} {DIM}{note:<{W-6}}{RESET}{YELLOW}│{RESET}")

    print(f"  {YELLOW}└{'─' * (W-4)}┘{RESET}")


def main():
    """Main dashboard loop."""
    global _epoch_start_prices, _last_epoch_start

    print(f"\n{CYAN}Starting Intra-Epoch Momentum Dashboard...{RESET}")
    print(f"{DIM}Fetching initial data...{RESET}\n")

    cryptos = ['BTC', 'ETH', 'SOL', 'XRP']

    # Check if shadow mode is active
    shadow_mode = is_shadow_mode_active()
    if shadow_mode:
        print(f"{MAGENTA}🔮 Shadow mode detected - showing shadow trade data{RESET}\n")

    try:
        while True:
            epoch_start, time_in_epoch = get_current_epoch()

            # Re-check shadow mode periodically (in case bot was started/stopped)
            shadow_mode = is_shadow_mode_active()

            # Record epoch start prices at beginning of new epoch
            if epoch_start != _last_epoch_start:
                _last_epoch_start = epoch_start
                _epoch_start_prices = {}
                for crypto in cryptos:
                    prices = get_multi_exchange_prices(crypto)
                    _epoch_start_prices[crypto] = {k: v for k, v in prices.items() if v is not None}

            data = {}
            prices_data = {}
            confluence_data = {}
            decision_factors = {}

            for crypto in cryptos:
                # Fetch minute candles (now returns dict with minutes and price data)
                candle_data = fetch_epoch_minutes(crypto, epoch_start)
                if candle_data:
                    data[crypto] = candle_data

                # Fetch Polymarket prices
                prices = fetch_polymarket_prices(crypto, epoch_start)
                if prices:
                    prices_data[crypto] = prices

                # Get confluence (compare current exchange prices to epoch start)
                if crypto in _epoch_start_prices:
                    confluence = get_exchange_confluence(crypto, _epoch_start_prices[crypto])
                    confluence_data[crypto] = confluence

                # Analyze pattern to get direction and accuracy
                if candle_data:
                    minutes = candle_data.get('minutes', [])
                    pattern_dir, pattern_acc, _ = analyze_pattern(minutes)
                else:
                    pattern_dir, pattern_acc = None, 0.5

                # Calculate decision factors
                factors = get_decision_factors(
                    crypto,
                    candle_data,
                    prices,
                    confluence_data.get(crypto),
                    pattern_dir,
                    pattern_acc
                )
                decision_factors[crypto] = factors

            render_dashboard(data, prices_data, epoch_start, time_in_epoch, shadow_mode)

            # Add decision summary panel
            render_decision_summary(decision_factors, time_in_epoch)

            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n\n{CYAN}Dashboard stopped.{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
