#!/usr/bin/env python3
"""
Intra-Epoch Momentum Dashboard

Real-time visualization of 1-minute candle patterns within each 15-minute epoch.
Shows momentum buildup and predicted outcome probability for BTC, ETH, SOL, XRP.
"""

import os
import sys
import time
import re
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"


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


def get_current_epoch() -> Tuple[int, int]:
    """Get current epoch start and time elapsed."""
    now = int(time.time())
    epoch_start = now // 900 * 900
    time_in_epoch = now - epoch_start
    return epoch_start, time_in_epoch


def fetch_epoch_minutes(crypto: str, epoch_start: int) -> Optional[List[dict]]:
    """Fetch 1-minute candles for the current epoch."""
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
        minutes = []

        for k in klines[:-1]:  # Skip last (incomplete)
            open_p = float(k[1])
            close_p = float(k[4])
            minutes.append({
                'direction': 'Up' if close_p > open_p else 'Down',
                'incomplete': False
            })

        # Add current incomplete candle
        if klines:
            k = klines[-1]
            open_p = float(k[1])
            close_p = float(k[4])
            minutes.append({
                'direction': 'Up' if close_p > open_p else 'Down',
                'incomplete': True
            })

        return minutes
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


def render_crypto_panel(crypto: str, minutes: List[dict], time_in_epoch: int) -> List[str]:
    """Render a single crypto panel."""
    W = 38  # Panel inner width (excluding borders)
    lines = []

    direction, probability, description = analyze_pattern(minutes)
    completed = [m for m in minutes if not m.get('incomplete', False)]
    current = [m for m in minutes if m.get('incomplete', False)]

    # Header
    if direction == 'Up':
        header = f"{GREEN}{BOLD}{crypto}{RESET}"
    elif direction == 'Down':
        header = f"{RED}{BOLD}{crypto}{RESET}"
    else:
        header = f"{CYAN}{BOLD}{crypto}{RESET}"

    lines.append(f"┌{'─' * W}┐")
    # Center the header
    header_pad = (W - len(crypto)) // 2
    lines.append(f"│{' ' * header_pad}{header}{' ' * (W - header_pad - len(crypto))}│")
    lines.append(f"├{'─' * W}┤")

    # Build minute row
    def make_row(start: int, end: int, label: str) -> str:
        symbols = []
        for i in range(start, end):
            if i < len(completed):
                if completed[i]['direction'] == 'Up':
                    symbols.append(f"{GREEN}▲{RESET}")
                else:
                    symbols.append(f"{RED}▼{RESET}")
            elif i == len(completed) and current:
                if current[0]['direction'] == 'Up':
                    symbols.append(f"{DIM}[{GREEN}▲{RESET}{DIM}]{RESET}")
                else:
                    symbols.append(f"{DIM}[{RED}▼{RESET}{DIM}]{RESET}")
            else:
                symbols.append(f"{DIM}·{RESET}")

        row_content = f"{label}  " + "  ".join(symbols)
        return row_content

    row1 = make_row(0, 5, "Min 1-5: ")
    row2 = make_row(5, 10, "Min 6-10:")
    row3 = make_row(10, 15, "Min 11-15:")

    lines.append(f"│ {pad_right(row1, W-2)} │")
    lines.append(f"│ {pad_right(row2, W-2)} │")
    lines.append(f"│ {pad_right(row3, W-2)} │")
    lines.append(f"├{'─' * W}┤")

    # Count
    ups = sum(1 for m in completed if m['direction'] == 'Up')
    downs = len(completed) - ups
    count_line = f"Count: {GREEN}{ups}▲{RESET} {RED}{downs}▼{RESET}"
    lines.append(f"│ {pad_right(count_line, W-2)} │")

    # Prediction
    if direction == 'Up':
        pred_line = f"Predict: {GREEN}{probability:.0%} UP{RESET}"
    elif direction == 'Down':
        pred_line = f"Predict: {RED}{probability:.0%} DOWN{RESET}"
    else:
        pred_line = f"Predict: {YELLOW}50% ???{RESET}"
    lines.append(f"│ {pad_right(pred_line, W-2)} │")

    # Description
    desc = description[:W-2]
    lines.append(f"│ {desc:<{W-2}} │")

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


def render_dashboard(data: Dict[str, List[dict]], epoch_start: int, time_in_epoch: int):
    """Render the full dashboard."""
    clear_screen()

    epoch_time = datetime.fromtimestamp(epoch_start, tz=timezone.utc)
    epoch_end = datetime.fromtimestamp(epoch_start + 900, tz=timezone.utc)
    minutes_elapsed = time_in_epoch // 60
    seconds_elapsed = time_in_epoch % 60

    # Header box - 80 chars wide
    W = 80
    print()
    print(f"{CYAN}╔{'═' * (W-2)}╗{RESET}")
    title = "INTRA-EPOCH MOMENTUM DASHBOARD"
    title_pad = (W - 2 - len(title)) // 2
    print(f"{CYAN}║{RESET}{' ' * title_pad}{BOLD}{title}{RESET}{' ' * (W - 2 - title_pad - len(title))}{CYAN}║{RESET}")
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

    # Render panels
    cryptos = ['BTC', 'ETH', 'SOL', 'XRP']
    panels = [render_crypto_panel(c, data.get(c, []), time_in_epoch) for c in cryptos]

    # Print top row (BTC, ETH)
    for i in range(len(panels[0])):
        print(f"  {panels[0][i]}  {panels[1][i]}")
    print()

    # Print bottom row (SOL, XRP)
    for i in range(len(panels[2])):
        print(f"  {panels[2][i]}  {panels[3][i]}")

    # Legend
    print()
    print(f"  {DIM}Legend: {GREEN}▲{RESET}{DIM}=Up  {RED}▼{RESET}{DIM}=Down  ·=Pending  [▲]=Current{RESET}")
    print(f"  {DIM}Patterns: 4+/5 same = 74-80%  |  All 3 same = 74-78%  |  3/5 same = ~65%{RESET}")
    print()
    print(f"  {DIM}Refreshing every 5s. Press Ctrl+C to exit.{RESET}")


def main():
    """Main dashboard loop."""
    print(f"\n{CYAN}Starting Intra-Epoch Momentum Dashboard...{RESET}")
    print(f"{DIM}Fetching initial data...{RESET}\n")

    cryptos = ['BTC', 'ETH', 'SOL', 'XRP']

    try:
        while True:
            epoch_start, time_in_epoch = get_current_epoch()

            data = {}
            for crypto in cryptos:
                minutes = fetch_epoch_minutes(crypto, epoch_start)
                if minutes:
                    data[crypto] = minutes

            render_dashboard(data, epoch_start, time_in_epoch)
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n\n{CYAN}Dashboard stopped.{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
