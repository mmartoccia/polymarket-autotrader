#!/usr/bin/env python3
"""
Intra-Epoch Momentum Bot

A simple, focused trading bot that uses only intra-epoch momentum patterns.

VALIDATED PATTERNS (2,688 epochs, 7 days):
- 4+ of first 5 minutes same direction: 74-80% accuracy
- All first 3 minutes same direction: 74-78% accuracy

RULES:
1. Only trade strong patterns (74%+ accuracy)
2. Only trade good value entries (≤$0.35)
3. Only trade during window (minutes 3-10)
4. Skip weak/mixed signals
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import POLYGON

# Load environment
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Trading parameters
MAX_ENTRY_PRICE = 0.35          # Only enter if price ≤ this
MIN_PATTERN_ACCURACY = 0.74     # Only trade 74%+ patterns
TRADING_WINDOW_START = 180      # Start trading at minute 3 (180 seconds)
TRADING_WINDOW_END = 600        # Stop trading at minute 10 (600 seconds)

# Position sizing
BASE_POSITION_USD = 5.0         # Base position size
MAX_POSITION_USD = 15.0         # Maximum position size
MIN_BET_USD = 1.10              # Polymarket minimum

# Risk management
MAX_POSITIONS = 4               # Max concurrent positions (1 per crypto)
MAX_DAILY_LOSS_USD = 30.0       # Stop trading if daily loss exceeds this
MAX_DRAWDOWN_PCT = 0.30         # Stop if drawdown exceeds 30%

# Scanning
SCAN_INTERVAL = 10              # Check every 10 seconds
CRYPTOS = ['BTC', 'ETH', 'SOL', 'XRP']

# State file
STATE_FILE = Path(__file__).parent.parent / "state" / "intra_epoch_state.json"

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# Also log to file
file_handler = logging.FileHandler(
    Path(__file__).parent.parent / "intra_epoch_bot.log"
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)s | %(message)s'
))
log.addHandler(file_handler)

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class BotState:
    """Persistent bot state."""

    def __init__(self):
        self.starting_balance = 0.0
        self.current_balance = 0.0
        self.peak_balance = 0.0
        self.daily_start_balance = 0.0
        self.total_trades = 0
        self.total_wins = 0
        self.total_losses = 0
        self.daily_pnl = 0.0
        self.positions = {}  # {crypto: {direction, entry_price, size, epoch}}
        self.last_epoch_traded = {}  # {crypto: epoch} - prevent double trading
        self.halted = False
        self.halt_reason = ""

    def load(self):
        """Load state from file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.starting_balance = data.get('starting_balance', 0.0)
                    self.current_balance = data.get('current_balance', 0.0)
                    self.peak_balance = data.get('peak_balance', 0.0)
                    self.daily_start_balance = data.get('daily_start_balance', 0.0)
                    self.total_trades = data.get('total_trades', 0)
                    self.total_wins = data.get('total_wins', 0)
                    self.total_losses = data.get('total_losses', 0)
                    self.daily_pnl = data.get('daily_pnl', 0.0)
                    self.positions = data.get('positions', {})
                    self.last_epoch_traded = data.get('last_epoch_traded', {})
                    self.halted = data.get('halted', False)
                    self.halt_reason = data.get('halt_reason', "")
                log.info(f"Loaded state: balance=${self.current_balance:.2f}, trades={self.total_trades}")
            except Exception as e:
                log.error(f"Failed to load state: {e}")

    def save(self):
        """Save state to file."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    'starting_balance': self.starting_balance,
                    'current_balance': self.current_balance,
                    'peak_balance': self.peak_balance,
                    'daily_start_balance': self.daily_start_balance,
                    'total_trades': self.total_trades,
                    'total_wins': self.total_wins,
                    'total_losses': self.total_losses,
                    'daily_pnl': self.daily_pnl,
                    'positions': self.positions,
                    'last_epoch_traded': self.last_epoch_traded,
                    'halted': self.halted,
                    'halt_reason': self.halt_reason,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save state: {e}")

    def win_rate(self) -> float:
        """Calculate current win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.total_wins / self.total_trades

# =============================================================================
# MARKET DATA
# =============================================================================

def get_current_epoch() -> Tuple[int, int]:
    """Get current epoch start and time elapsed."""
    now = int(time.time())
    epoch_start = now // 900 * 900
    time_in_epoch = now - epoch_start
    return epoch_start, time_in_epoch


def fetch_minute_candles(crypto: str, epoch_start: int) -> Optional[List[str]]:
    """Fetch 1-minute candles for the current epoch. Returns list of 'Up'/'Down'."""
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

        # Convert to Up/Down (skip last incomplete candle)
        minutes = []
        for k in klines[:-1]:
            open_p = float(k[1])
            close_p = float(k[4])
            minutes.append('Up' if close_p > open_p else 'Down')

        return minutes

    except Exception as e:
        log.warning(f"Failed to fetch candles for {crypto}: {e}")
        return None


def fetch_polymarket_prices(crypto: str, epoch_start: int) -> Optional[Dict]:
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

        # Get CLOB data
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

                # Best ask (what you pay to buy)
                best_ask = float(asks[-1]["price"]) if asks else 0.99

                prices[outcome] = {
                    'ask': best_ask,
                    'token_id': token_id
                }
            except Exception:
                continue

        return prices if 'Up' in prices and 'Down' in prices else None

    except Exception as e:
        log.warning(f"Failed to fetch Polymarket prices for {crypto}: {e}")
        return None

# =============================================================================
# PATTERN DETECTION
# =============================================================================

def analyze_pattern(minutes: List[str]) -> Tuple[Optional[str], float, str]:
    """
    Analyze minute patterns and return (direction, accuracy, reason).

    Only returns signals for strong patterns (74%+ accuracy).
    """
    if not minutes or len(minutes) < 3:
        return (None, 0.0, "Not enough data")

    # Pattern 1: 4+ of first 5 minutes same direction (strongest)
    if len(minutes) >= 5:
        first_5 = minutes[:5]
        ups = sum(1 for m in first_5 if m == 'Up')
        downs = 5 - ups

        if ups >= 4:
            return ('Up', 0.797, f"{ups}/5 first minutes UP = 79.7% accuracy")
        elif downs >= 4:
            return ('Down', 0.740, f"{downs}/5 first minutes DOWN = 74.0% accuracy")

    # Pattern 2: All first 3 minutes same direction
    first_3 = minutes[:3]
    if all(m == 'Up' for m in first_3):
        return ('Up', 0.780, "All 3 first minutes UP = 78.0% accuracy")
    elif all(m == 'Down' for m in first_3):
        return ('Down', 0.739, "All 3 first minutes DOWN = 73.9% accuracy")

    # No strong pattern
    return (None, 0.0, "No strong pattern detected")

# =============================================================================
# TRADING
# =============================================================================

def get_clob_client() -> Optional[ClobClient]:
    """Initialize CLOB client for trading."""
    try:
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        if not private_key:
            log.error("POLYMARKET_PRIVATE_KEY not set")
            return None

        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=POLYGON,
            key=private_key,
            signature_type=2,  # POLY_GNOSIS_SAFE
            funder=os.getenv("POLYMARKET_WALLET")
        )

        # Derive API credentials
        client.set_api_creds(client.create_or_derive_api_creds())

        return client

    except Exception as e:
        log.error(f"Failed to initialize CLOB client: {e}")
        return None


def get_wallet_balance() -> float:
    """Get current USDC balance from Polygon."""
    try:
        wallet = os.getenv("POLYMARKET_WALLET")
        if not wallet:
            return 0.0

        rpc = "https://polygon-rpc.com"
        usdc = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

        # balanceOf call
        data = f"0x70a08231000000000000000000000000{wallet[2:]}"
        resp = requests.post(rpc, json={
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{'to': usdc, 'data': data}, 'latest'],
            'id': 1
        }, timeout=5)

        result = resp.json().get('result', '0x0')
        return int(result, 16) / 1e6

    except Exception as e:
        log.warning(f"Failed to get balance: {e}")
        return 0.0


def calculate_position_size(balance: float, accuracy: float) -> float:
    """Calculate position size based on balance and signal accuracy."""
    # Base size scales with balance
    if balance < 50:
        base = min(BASE_POSITION_USD, balance * 0.15)
    elif balance < 100:
        base = min(BASE_POSITION_USD, balance * 0.10)
    elif balance < 200:
        base = min(BASE_POSITION_USD * 1.5, balance * 0.08)
    else:
        base = min(MAX_POSITION_USD, balance * 0.05)

    # Scale by accuracy (79.7% gets full size, 74% gets 90%)
    accuracy_multiplier = 0.9 + (accuracy - 0.74) * 2.0  # 0.9 to 1.12

    size = base * accuracy_multiplier

    # Enforce limits
    size = max(MIN_BET_USD, min(MAX_POSITION_USD, size))

    return round(size, 2)


def place_trade(client: ClobClient, crypto: str, direction: str,
                token_id: str, price: float, size_usd: float) -> bool:
    """Place a trade on Polymarket."""
    try:
        # Calculate shares
        shares = size_usd / price

        log.info(f"Placing order: {crypto} {direction} @ ${price:.2f}, ${size_usd:.2f} ({shares:.1f} shares)")

        order_args = OrderArgs(
            price=price,
            size=shares,
            side="BUY",
            token_id=token_id
        )

        signed_order = client.create_order(order_args)
        response = client.post_order(signed_order, OrderType.GTC)

        if response and response.get("success"):
            log.info(f"ORDER PLACED: {crypto} {direction} - ${size_usd:.2f} @ ${price:.2f}")
            return True
        else:
            log.error(f"Order failed: {response}")
            return False

    except Exception as e:
        log.error(f"Failed to place trade: {e}")
        return False

# =============================================================================
# MAIN BOT LOOP
# =============================================================================

def resolve_completed_positions(state: BotState) -> None:
    """Check and resolve any positions from completed epochs."""
    if not state.positions:
        return

    current_epoch, _ = get_current_epoch()

    positions_to_remove = []

    for crypto, pos in state.positions.items():
        pos_epoch = pos['epoch']

        # Position is from a past epoch - it's resolved
        if pos_epoch < current_epoch:
            direction = pos['direction']
            entry_price = pos['entry_price']
            size = pos['size']

            # Fetch the final outcome from that epoch
            # We check if the price moved in our direction
            outcome = check_epoch_outcome(crypto, pos_epoch)

            if outcome is None:
                log.warning(f"{crypto}: Could not determine outcome for epoch {pos_epoch}")
                positions_to_remove.append(crypto)
                continue

            if outcome == direction:
                # WIN - we get $1.00 per share
                shares = size / entry_price
                payout = shares * 1.0
                profit = payout - size

                state.total_wins += 1
                state.daily_pnl += profit
                state.current_balance += profit

                log.info(f"")
                log.info(f"{'='*50}")
                log.info(f"WIN: {crypto} {direction}")
                log.info(f"  Entry: ${entry_price:.2f}, Size: ${size:.2f}")
                log.info(f"  Payout: ${payout:.2f}, Profit: ${profit:.2f}")
                log.info(f"  Balance: ${state.current_balance:.2f}")
                log.info(f"{'='*50}")

            else:
                # LOSS - position is worthless
                state.total_losses += 1
                state.daily_pnl -= size
                state.current_balance -= size

                log.info(f"")
                log.info(f"{'='*50}")
                log.info(f"LOSS: {crypto} {direction} (actual: {outcome})")
                log.info(f"  Entry: ${entry_price:.2f}, Size: ${size:.2f}")
                log.info(f"  Loss: -${size:.2f}")
                log.info(f"  Balance: ${state.current_balance:.2f}")
                log.info(f"{'='*50}")

            positions_to_remove.append(crypto)

    # Remove resolved positions
    for crypto in positions_to_remove:
        del state.positions[crypto]

    if positions_to_remove:
        # Update peak balance
        if state.current_balance > state.peak_balance:
            state.peak_balance = state.current_balance
        state.save()

        # Log stats
        win_rate = state.total_wins / state.total_trades * 100 if state.total_trades > 0 else 0
        log.info(f"Stats: {state.total_wins}W/{state.total_losses}L ({win_rate:.1f}%) | Daily P&L: ${state.daily_pnl:.2f}")


def check_epoch_outcome(crypto: str, epoch_start: int) -> Optional[str]:
    """Check the actual outcome of a completed epoch."""
    try:
        symbol = f"{crypto}USDT"
        url = "https://api.binance.com/api/v3/klines"

        # Fetch the 15-minute candle for that epoch
        params = {
            'symbol': symbol,
            'interval': '15m',
            'startTime': epoch_start * 1000,
            'limit': 1
        }

        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return None

        klines = resp.json()
        if not klines:
            return None

        # Compare open to close
        open_price = float(klines[0][1])
        close_price = float(klines[0][4])

        if close_price > open_price:
            return 'Up'
        else:
            return 'Down'

    except Exception as e:
        log.warning(f"Failed to check outcome for {crypto}: {e}")
        return None


def check_risk_limits(state: BotState) -> bool:
    """Check if we should continue trading."""
    # Check drawdown
    if state.peak_balance > 0:
        drawdown = (state.peak_balance - state.current_balance) / state.peak_balance
        if drawdown >= MAX_DRAWDOWN_PCT:
            state.halted = True
            state.halt_reason = f"Drawdown {drawdown:.1%} exceeds {MAX_DRAWDOWN_PCT:.0%}"
            log.error(f"HALTED: {state.halt_reason}")
            return False

    # Check daily loss
    if state.daily_pnl <= -MAX_DAILY_LOSS_USD:
        state.halted = True
        state.halt_reason = f"Daily loss ${abs(state.daily_pnl):.2f} exceeds ${MAX_DAILY_LOSS_USD}"
        log.error(f"HALTED: {state.halt_reason}")
        return False

    return True


def run_bot():
    """Main bot loop."""
    log.info("=" * 60)
    log.info("INTRA-EPOCH MOMENTUM BOT STARTING")
    log.info("=" * 60)
    log.info(f"Max Entry Price: ${MAX_ENTRY_PRICE}")
    log.info(f"Min Pattern Accuracy: {MIN_PATTERN_ACCURACY:.0%}")
    log.info(f"Trading Window: minutes 3-10")
    log.info(f"Position Size: ${BASE_POSITION_USD}-${MAX_POSITION_USD}")
    log.info("=" * 60)

    # Initialize state
    state = BotState()
    state.load()

    # Get initial balance
    balance = get_wallet_balance()
    if balance > 0:
        state.current_balance = balance
        if state.starting_balance == 0:
            state.starting_balance = balance
            state.daily_start_balance = balance
        if balance > state.peak_balance:
            state.peak_balance = balance
        state.save()

    log.info(f"Current Balance: ${state.current_balance:.2f}")
    log.info(f"Peak Balance: ${state.peak_balance:.2f}")
    log.info(f"Total Trades: {state.total_trades} ({state.total_wins}W/{state.total_losses}L)")

    # Initialize CLOB client
    client = get_clob_client()
    if not client:
        log.error("Failed to initialize trading client. Exiting.")
        return

    log.info("CLOB client initialized. Starting main loop...")

    last_epoch = 0

    try:
        while True:
            # Check if halted
            if state.halted:
                log.warning(f"Bot is HALTED: {state.halt_reason}")
                time.sleep(60)
                continue

            # Get current epoch
            epoch_start, time_in_epoch = get_current_epoch()

            # New epoch - resolve positions and reset tracking
            if epoch_start != last_epoch:
                last_epoch = epoch_start
                epoch_time = datetime.fromtimestamp(epoch_start, timezone.utc)
                log.info(f"--- New Epoch: {epoch_time.strftime('%H:%M')} UTC ---")

                # Resolve any completed positions from last epoch
                resolve_completed_positions(state)

                # Update balance at epoch start
                balance = get_wallet_balance()
                if balance > 0:
                    state.current_balance = balance
                    if balance > state.peak_balance:
                        state.peak_balance = balance
                    state.save()

            # Only trade during window
            if time_in_epoch < TRADING_WINDOW_START:
                mins_left = (TRADING_WINDOW_START - time_in_epoch) // 60
                secs_left = (TRADING_WINDOW_START - time_in_epoch) % 60
                log.debug(f"Waiting for trading window ({mins_left}m {secs_left}s)")
                time.sleep(SCAN_INTERVAL)
                continue

            if time_in_epoch > TRADING_WINDOW_END:
                log.debug("Trading window closed for this epoch")
                time.sleep(SCAN_INTERVAL)
                continue

            # Check risk limits
            if not check_risk_limits(state):
                state.save()
                time.sleep(60)
                continue

            # Scan each crypto
            for crypto in CRYPTOS:
                # Skip if already traded this epoch
                if state.last_epoch_traded.get(crypto) == epoch_start:
                    continue

                # Skip if already have position in this crypto
                if crypto in state.positions:
                    continue

                # Check position limit
                if len(state.positions) >= MAX_POSITIONS:
                    continue

                # Fetch minute candles
                minutes = fetch_minute_candles(crypto, epoch_start)
                if not minutes:
                    continue

                # Analyze pattern
                direction, accuracy, reason = analyze_pattern(minutes)

                # Skip weak patterns
                if not direction or accuracy < MIN_PATTERN_ACCURACY:
                    continue

                # Fetch Polymarket prices
                prices = fetch_polymarket_prices(crypto, epoch_start)
                if not prices:
                    log.warning(f"{crypto}: No market prices available")
                    continue

                # Check entry price
                entry_price = prices[direction]['ask']
                if entry_price > MAX_ENTRY_PRICE:
                    log.info(f"{crypto}: {direction} signal but entry ${entry_price:.2f} > ${MAX_ENTRY_PRICE} (skip)")
                    continue

                # Calculate position size
                size = calculate_position_size(state.current_balance, accuracy)

                if size < MIN_BET_USD:
                    log.warning(f"{crypto}: Position size ${size:.2f} below minimum")
                    continue

                # Log the signal
                log.info(f"")
                log.info(f"{'='*50}")
                log.info(f"SIGNAL: {crypto} {direction}")
                log.info(f"  Pattern: {reason}")
                log.info(f"  Entry Price: ${entry_price:.2f}")
                log.info(f"  Position Size: ${size:.2f}")
                log.info(f"{'='*50}")

                # Place trade
                token_id = prices[direction]['token_id']
                success = place_trade(client, crypto, direction, token_id, entry_price, size)

                if success:
                    # Record position
                    state.positions[crypto] = {
                        'direction': direction,
                        'entry_price': entry_price,
                        'size': size,
                        'epoch': epoch_start,
                        'accuracy': accuracy
                    }
                    state.last_epoch_traded[crypto] = epoch_start
                    state.total_trades += 1
                    state.save()

                    log.info(f"Trade recorded. Total positions: {len(state.positions)}")

            time.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:
        log.info("\nBot stopped by user")
        state.save()

    except Exception as e:
        log.error(f"Unexpected error: {e}")
        state.save()
        raise


if __name__ == "__main__":
    run_bot()
