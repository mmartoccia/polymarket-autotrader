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
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

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

# Shadow mode - log signals but don't place real trades (for testing alongside live bot)
SHADOW_MODE = os.getenv("INTRA_SHADOW_MODE", "false").lower() == "true" or "--shadow" in sys.argv

# Trading parameters
EDGE_BUFFER = 0.05              # Require 5% edge over break-even (for fees + safety margin)
MIN_PATTERN_ACCURACY = 0.735    # Only trade 73.5%+ patterns (includes all validated patterns)
# Max entry = pattern_accuracy - EDGE_BUFFER
# e.g., 74% pattern -> max entry $0.69, 80% pattern -> max entry $0.75
TRADING_WINDOW_START = 180      # Start trading at minute 3 (180 seconds)
TRADING_WINDOW_END = 600        # Stop trading at minute 10 (600 seconds)

# Position sizing
BASE_POSITION_USD = 5.0         # Base position size
MAX_POSITION_USD = 15.0         # Maximum position size
MIN_BET_USD = 1.10              # Polymarket minimum

# Position averaging (buying more when price improves)
ENABLE_POSITION_AVERAGING = True
PRICE_IMPROVE_THRESHOLD = 0.10  # Only add if price is 10%+ cheaper
MAX_PRICE_DROP_FOR_AVERAGING = 0.25  # STOP averaging if price dropped >25% (signal is likely wrong)
AVERAGING_SIZE_MULTIPLIER = 0.5  # Only add 50% of normal position (reduce downside risk)
MAX_ADDS_PER_POSITION = 2       # Max times we can add to a position
MAX_TOTAL_POSITION_USD = 25.0   # Max total position size after adding

# Risk management
MAX_POSITIONS = 4               # Max concurrent positions (1 per crypto)
MAX_DAILY_LOSS_USD = 30.0       # Stop trading if daily loss exceeds this
MAX_DRAWDOWN_PCT = 0.30         # Stop if drawdown exceeds 30%

# Scanning
SCAN_INTERVAL = 10              # Check every 10 seconds
CRYPTOS = ['BTC', 'ETH', 'SOL', 'XRP']

# State file
STATE_FILE = Path(__file__).parent.parent / "state" / "intra_epoch_state.json"

# Web3 / Redemption constants
RPC_URL = "https://polygon-rpc.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_ABI = [{
    "name": "redeemPositions",
    "type": "function",
    "inputs": [
        {"name": "collateralToken", "type": "address"},
        {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"},
        {"name": "indexSets", "type": "uint256[]"}
    ]
}]

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_AUTHORIZED_USER_ID", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower() == "true"

# =============================================================================
# GRANULAR SIGNAL ENHANCEMENT CONFIGURATION
# =============================================================================

# Magnitude tracking - measure HOW MUCH price moved, not just direction
ENABLE_MAGNITUDE_TRACKING = True
MIN_CUMULATIVE_MAGNITUDE = 0.0003     # 0.03% total move required for signal (was 0.8% - too strict)
MIN_PER_MINUTE_MAGNITUDE = 0.0001     # 0.01% per minute to count as "strong" move (was 0.2%)
MAGNITUDE_ACCURACY_BOOST = 0.03       # Up to 3% accuracy boost for strong moves
STRONG_MOVE_THRESHOLD = 0.0005        # 0.05% = strong move (triggers boost) (was 1.5%)

# Multi-exchange confluence - require multiple exchanges to agree on direction
ENABLE_MULTI_EXCHANGE = True
MIN_EXCHANGES_AGREE = 2               # Require 2 of 3 exchanges to agree

# Exchange symbol mappings for multi-exchange price fetching
EXCHANGE_SYMBOLS: Dict[str, Dict[str, str]] = {
    'BTC': {'binance': 'BTCUSDT', 'kraken': 'XBTUSD', 'coinbase': 'BTC-USD'},
    'ETH': {'binance': 'ETHUSDT', 'kraken': 'ETHUSD', 'coinbase': 'ETH-USD'},
    'SOL': {'binance': 'SOLUSDT', 'kraken': 'SOLUSD', 'coinbase': 'SOL-USD'},
    'XRP': {'binance': 'XRPUSDT', 'kraken': 'XRPUSD', 'coinbase': 'XRP-USD'},
}

# Shadow logging for comparing old vs new signal logic
ENABLE_GRANULAR_SHADOW_LOG = True

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
# TELEGRAM NOTIFICATIONS
# =============================================================================

def send_telegram(message: str, silent: bool = False) -> bool:
    """Send a message to Telegram."""
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_notification": silent
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")
        return False


def notify_trade(
    crypto: str,
    direction: str,
    entry_price: float,
    size: float,
    accuracy: float = 0.0,
    magnitude_boost: float = 0.0,
    confluence_count: int = 0,
    is_averaging: bool = False
):
    """Send trade notification via telegram_handler."""
    from telegram_handler import get_telegram_bot
    bot = get_telegram_bot()
    # Convert accuracy from decimal to percentage for telegram_handler
    accuracy_pct = accuracy * 100 if accuracy <= 1 else accuracy
    magnitude_pct = magnitude_boost * 100 if magnitude_boost <= 1 else magnitude_boost
    bot.notify_trade(
        crypto=crypto,
        direction=direction,
        entry_price=entry_price,
        size=size,
        accuracy=accuracy_pct,
        magnitude_pct=magnitude_pct,
        confluence_count=confluence_count,
        is_averaging=is_averaging
    )


def notify_result(crypto: str, direction: str, is_win: bool, profit: float, balance: float, win_rate: float = 0.0):
    """Send trade result notification via telegram_handler."""
    telegram = get_telegram_bot()
    if is_win:
        telegram.notify_win(crypto, direction, profit, balance, win_rate)
    else:
        telegram.notify_loss(crypto, direction, abs(profit), balance, win_rate)


def notify_alert(message: str):
    """Send alert notification (not silent)."""
    send_telegram(f"⚠️ ALERT\n{message}", silent=False)


# =============================================================================
# AUTO REDEEMER
# =============================================================================

class AutoRedeemer:
    """Automatically redeem winning positions."""

    def __init__(self):
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        if not private_key:
            self.enabled = False
            log.warning("AutoRedeemer disabled: No private key")
            return

        self.enabled = True
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.account = Account.from_key(private_key)
        self.ctf = self.w3.eth.contract(address=CTF_ADDRESS, abi=CTF_ABI)
        self.wallet = os.getenv("POLYMARKET_WALLET", self.account.address)

    def get_redeemable_positions(self) -> List[Dict]:
        """Fetch positions marked as redeemable."""
        if not self.enabled:
            return []

        try:
            resp = requests.get(
                "https://data-api.polymarket.com/positions",
                params={"user": self.wallet, "redeemable": "true", "limit": 20},
                timeout=10
            )
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            log.warning(f"Failed to fetch redeemable positions: {e}")
            return []

    def redeem_position(self, condition_id: str, nonce: int) -> bool:
        """Redeem a single position on-chain."""
        if not self.enabled:
            return False

        try:
            gas_price = int(self.w3.eth.gas_price * 1.5)

            txn = self.ctf.functions.redeemPositions(
                USDC_ADDRESS,
                bytes(32),
                bytes.fromhex(condition_id[2:] if condition_id.startswith('0x') else condition_id),
                [1, 2]
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 300000,
                'gasPrice': gas_price,
                'chainId': 137
            })

            signed = self.account.sign_transaction(txn)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                log.info(f"Redeemed position {condition_id[:10]}... tx: {tx_hash.hex()[:16]}...")
                return True
            else:
                log.warning(f"Redemption tx failed for {condition_id[:10]}...")
                return False

        except Exception as e:
            log.error(f"Redemption error: {e}")
            return False

    def check_and_redeem(self) -> Tuple[int, float]:
        """
        Check for redeemable positions and redeem them.

        Returns:
            (count_redeemed, total_value)
        """
        if not self.enabled:
            return 0, 0.0

        positions = self.get_redeemable_positions()
        if not positions:
            return 0, 0.0

        log.info(f"Found {len(positions)} redeemable positions")

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        redeemed = 0
        total_value = 0.0

        for pos in positions:
            condition_id = pos.get('conditionId') or pos.get('condition_id')
            size = float(pos.get('size', 0))

            if not condition_id:
                continue

            if self.redeem_position(condition_id, nonce):
                redeemed += 1
                total_value += size
                nonce += 1

        if redeemed > 0:
            log.info(f"Redeemed {redeemed} positions for ${total_value:.2f}")
            send_telegram(f"💰 Redeemed {redeemed} positions for ${total_value:.2f}")

        return redeemed, total_value


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


def fetch_minute_candles(crypto: str, epoch_start: int) -> Optional[List[Dict[str, Union[str, float]]]]:
    """
    Fetch 1-minute candles for the current epoch.

    Returns list of dicts with:
        - direction: "Up" or "Down"
        - change_pct: Percent change (close - open) / open * 100
        - volume: Trading volume for the candle

    Example:
        [{"direction": "Down", "change_pct": -0.25, "volume": 1234.5}, ...]
    """
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

        # Convert to candle dicts with direction, magnitude, and volume
        # Binance kline format: [open_time, open, high, low, close, volume, ...]
        # Skip last incomplete candle
        candles: List[Dict[str, Union[str, float]]] = []
        for k in klines[:-1]:
            open_p = float(k[1])
            close_p = float(k[4])
            volume = float(k[5])
            change_pct = (close_p - open_p) / open_p * 100 if open_p > 0 else 0.0

            candles.append({
                'direction': 'Up' if close_p > open_p else 'Down',
                'change_pct': change_pct,
                'volume': volume
            })

        return candles

    except Exception as e:
        log.warning(f"Failed to fetch candles for {crypto}: {e}")
        return None


def get_directions_from_candles(candles: Optional[List[Dict[str, Union[str, float]]]]) -> Optional[List[str]]:
    """
    Extract direction-only list from candle dicts for backward compatibility.

    Args:
        candles: List of candle dicts from fetch_minute_candles()

    Returns:
        List of direction strings ("Up"/"Down"), or None if input is None

    Example:
        >>> candles = [{"direction": "Down", "change_pct": -0.25, "volume": 100}]
        >>> get_directions_from_candles(candles)
        ["Down"]
    """
    if candles is None:
        return None
    return [c['direction'] for c in candles]


def check_cumulative_magnitude(candles: List[Dict[str, Union[str, float]]], direction: str) -> Tuple[bool, float]:
    """
    Check if total price movement meets minimum threshold for a given direction.

    Sums the magnitude (absolute change_pct / 100) of candles that match the specified
    direction. This helps filter out weak signals where the price moved in the right
    direction but the total magnitude was too small to be meaningful.

    Args:
        candles: List of candle dicts from fetch_minute_candles(), each containing
                 'direction' ('Up'/'Down'), 'change_pct' (float), and 'volume' (float)
        direction: The pattern direction to check ("Up" or "Down")

    Returns:
        Tuple of (passes_threshold, total_magnitude) where:
        - passes_threshold: True if magnitude >= MIN_CUMULATIVE_MAGNITUDE or feature disabled
        - total_magnitude: Sum of absolute change_pct / 100 for matching candles

    Example:
        >>> candles = [
        ...     {"direction": "Down", "change_pct": -0.25, "volume": 100},
        ...     {"direction": "Down", "change_pct": -0.35, "volume": 150},
        ...     {"direction": "Up", "change_pct": 0.10, "volume": 80},
        ...     {"direction": "Down", "change_pct": -0.30, "volume": 120},
        ... ]
        >>> check_cumulative_magnitude(candles, "Down")
        (True, 0.009)  # 0.25 + 0.35 + 0.30 = 0.90% total = 0.009

    Notes:
        - Only candles matching the direction are summed (opposite direction ignored)
        - Returns (True, magnitude) if ENABLE_MAGNITUDE_TRACKING is False
        - Threshold defined by MIN_CUMULATIVE_MAGNITUDE (default 0.008 = 0.8%)
    """
    # If feature disabled, always pass
    if not ENABLE_MAGNITUDE_TRACKING:
        return (True, 0.0)

    # Sum magnitude of candles matching the pattern direction
    total_magnitude = 0.0
    for candle in candles:
        if candle.get('direction') == direction:
            # change_pct is in percent (e.g., -0.25 for -0.25%)
            # Convert to decimal (e.g., 0.0025 for 0.25%)
            change_pct = candle.get('change_pct', 0.0)
            if isinstance(change_pct, (int, float)):
                total_magnitude += abs(change_pct) / 100.0

    passes = total_magnitude >= MIN_CUMULATIVE_MAGNITUDE
    return (passes, total_magnitude)


def check_per_minute_magnitude(candles: List[Dict[str, Union[str, float]]], direction: str) -> Tuple[int, int]:
    """
    Check if individual minute moves are meaningful (not noise) for a given direction.

    Analyzes each candle matching the specified direction and categorizes it as
    "strong" or "weak" based on whether its magnitude meets MIN_PER_MINUTE_MAGNITUDE.
    This helps distinguish between patterns with confident moves vs patterns with
    marginal moves that could easily reverse.

    Args:
        candles: List of candle dicts from fetch_minute_candles(), each containing
                 'direction' ('Up'/'Down'), 'change_pct' (float), and 'volume' (float)
        direction: The pattern direction to check ("Up" or "Down")

    Returns:
        Tuple of (strong_count, weak_count) where:
        - strong_count: Number of candles with magnitude >= MIN_PER_MINUTE_MAGNITUDE
        - weak_count: Number of candles with magnitude < MIN_PER_MINUTE_MAGNITUDE

    Example:
        >>> candles = [
        ...     {"direction": "Down", "change_pct": -0.25, "volume": 100},  # 0.25% = strong
        ...     {"direction": "Down", "change_pct": -0.08, "volume": 150},  # 0.08% = weak
        ...     {"direction": "Up", "change_pct": 0.10, "volume": 80},      # ignored (wrong dir)
        ...     {"direction": "Down", "change_pct": -0.30, "volume": 120},  # 0.30% = strong
        ... ]
        >>> check_per_minute_magnitude(candles, "Down")
        (2, 1)  # 2 strong, 1 weak

    Notes:
        - Can be used to require "4 of 5 STRONG moves" vs just "4 of 5 moves"
        - MIN_PER_MINUTE_MAGNITUDE default is 0.002 (0.2% per minute)
        - Only candles matching the direction are counted
        - If ENABLE_MAGNITUDE_TRACKING is False, all moves are counted as strong
    """
    strong_count = 0
    weak_count = 0

    for candle in candles:
        if candle.get('direction') == direction:
            # change_pct is in percent (e.g., -0.25 for -0.25%)
            # Convert to decimal (e.g., 0.0025 for 0.25%)
            change_pct = candle.get('change_pct', 0.0)
            if isinstance(change_pct, (int, float)):
                magnitude = abs(change_pct) / 100.0

                # If feature disabled, count all as strong
                if not ENABLE_MAGNITUDE_TRACKING:
                    strong_count += 1
                elif magnitude >= MIN_PER_MINUTE_MAGNITUDE:
                    strong_count += 1
                else:
                    weak_count += 1

    return (strong_count, weak_count)


def calculate_magnitude_boost(candles: List[Dict[str, Union[str, float]]], direction: str) -> float:
    """
    Calculate accuracy boost based on move strength for a given direction.

    Provides an accuracy boost (0.0 to MAGNITUDE_ACCURACY_BOOST) based on how far
    the cumulative magnitude exceeds STRONG_MOVE_THRESHOLD. This rewards patterns
    where the price moved decisively in one direction, which typically indicates
    stronger momentum and higher probability of continuation.

    Formula:
        if total_magnitude <= STRONG_MOVE_THRESHOLD:
            boost = 0.0
        else:
            excess = total_magnitude - STRONG_MOVE_THRESHOLD
            boost = min(excess / STRONG_MOVE_THRESHOLD, 1.0) * MAGNITUDE_ACCURACY_BOOST

    The boost scales linearly from 0% at STRONG_MOVE_THRESHOLD (1.5%) up to the
    maximum boost at 2x STRONG_MOVE_THRESHOLD (3.0%). This means:
        - 1.5% total move = 0% boost
        - 2.0% total move = 1.0% boost (33% of max)
        - 2.25% total move = 1.5% boost (50% of max)
        - 3.0%+ total move = 3.0% boost (100% of max, capped)

    Args:
        candles: List of candle dicts from fetch_minute_candles(), each containing
                 'direction' ('Up'/'Down'), 'change_pct' (float), and 'volume' (float)
        direction: The pattern direction to check ("Up" or "Down")

    Returns:
        Float accuracy boost between 0.0 and MAGNITUDE_ACCURACY_BOOST (default 0.03)
        Returns 0.0 if ENABLE_MAGNITUDE_TRACKING is False

    Example:
        >>> candles = [
        ...     {"direction": "Down", "change_pct": -0.50, "volume": 100},  # 0.50%
        ...     {"direction": "Down", "change_pct": -0.40, "volume": 150},  # 0.40%
        ...     {"direction": "Up", "change_pct": 0.10, "volume": 80},      # ignored
        ...     {"direction": "Down", "change_pct": -0.60, "volume": 120},  # 0.60%
        ...     {"direction": "Down", "change_pct": -0.50, "volume": 110},  # 0.50%
        ... ]
        >>> # Total magnitude = 0.50 + 0.40 + 0.60 + 0.50 = 2.0%
        >>> # Excess over 1.5% = 0.5%
        >>> # Boost = (0.5% / 1.5%) * 3% = 1.0%
        >>> calculate_magnitude_boost(candles, "Down")
        0.01  # 1% accuracy boost
    """
    # Return 0.0 if feature disabled
    if not ENABLE_MAGNITUDE_TRACKING:
        return 0.0

    # Calculate total magnitude for candles matching direction
    total_magnitude = 0.0
    for candle in candles:
        if candle.get('direction') == direction:
            # change_pct is in percent (e.g., -0.50 for -0.50%)
            # Convert to decimal (e.g., 0.005 for 0.5%)
            change_pct = candle.get('change_pct', 0.0)
            if isinstance(change_pct, (int, float)):
                total_magnitude += abs(change_pct) / 100.0

    # No boost if below strong move threshold
    if total_magnitude <= STRONG_MOVE_THRESHOLD:
        return 0.0

    # Calculate linear boost based on excess over threshold
    # Boost scales from 0 at threshold to MAGNITUDE_ACCURACY_BOOST at 2x threshold
    excess = total_magnitude - STRONG_MOVE_THRESHOLD
    boost_ratio = min(excess / STRONG_MOVE_THRESHOLD, 1.0)  # Cap at 1.0
    boost = boost_ratio * MAGNITUDE_ACCURACY_BOOST

    return boost


# =============================================================================
# MULTI-EXCHANGE PRICE FETCHING
# =============================================================================

def get_binance_price(symbol: str) -> Optional[float]:
    """
    Fetch current price from Binance.

    Args:
        symbol: Binance trading pair symbol (e.g., 'BTCUSDT', 'ETHUSDT')

    Returns:
        Current price as float, or None if fetch failed

    Example:
        >>> get_binance_price('BTCUSDT')
        104523.50
    """
    try:
        resp = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            timeout=2
        )
        if resp.status_code == 200:
            return float(resp.json()["price"])
        return None
    except Exception:
        return None


def get_kraken_price(symbol: str) -> Optional[float]:
    """
    Fetch current price from Kraken.

    Args:
        symbol: Kraken trading pair symbol (e.g., 'XBTUSD', 'ETHUSD')

    Returns:
        Current price as float, or None if fetch failed

    Note:
        Kraken returns data nested in a 'result' dict with the pair name as key.
        The price is in the 'c' field (last trade closed) as [price, lot_volume].

    Example:
        >>> get_kraken_price('XBTUSD')
        104521.00
    """
    try:
        resp = requests.get(
            f"https://api.kraken.com/0/public/Ticker?pair={symbol}",
            timeout=2
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("error"):
            return None

        # Kraken returns result nested under the pair key
        for key, val in data.get("result", {}).items():
            # 'c' is the last trade closed price: [price, lot_volume]
            return float(val["c"][0])

        return None
    except Exception:
        return None


def get_coinbase_price(symbol: str) -> Optional[float]:
    """
    Fetch current price from Coinbase.

    Args:
        symbol: Coinbase trading pair symbol (e.g., 'BTC-USD', 'ETH-USD')

    Returns:
        Current price as float, or None if fetch failed

    Example:
        >>> get_coinbase_price('BTC-USD')
        104525.00
    """
    try:
        resp = requests.get(
            f"https://api.coinbase.com/v2/prices/{symbol}/spot",
            timeout=2
        )
        if resp.status_code == 200:
            return float(resp.json()["data"]["amount"])
        return None
    except Exception:
        return None


def fetch_multi_exchange_prices(crypto: str) -> Dict[str, float]:
    """
    Fetch prices from Binance, Kraken, and Coinbase in parallel.

    Uses ThreadPoolExecutor to fetch from all exchanges concurrently with
    a 2-second timeout per exchange. Returns whatever prices were successfully
    fetched (may be partial if some exchanges failed).

    Args:
        crypto: Cryptocurrency symbol (e.g., 'BTC', 'ETH', 'SOL', 'XRP')

    Returns:
        Dict mapping exchange name to price, e.g.:
        {"binance": 104523.50, "kraken": 104521.00, "coinbase": 104525.00}

        May be partial or empty if exchanges fail:
        {"binance": 104523.50}  # If only Binance responded
        {}  # If all exchanges failed

    Example:
        >>> fetch_multi_exchange_prices('BTC')
        {'binance': 104523.50, 'kraken': 104521.00, 'coinbase': 104525.00}

        >>> fetch_multi_exchange_prices('ETH')
        {'binance': 3850.25, 'coinbase': 3849.50}  # Kraken timed out
    """
    # Get exchange symbols for this crypto
    symbols = EXCHANGE_SYMBOLS.get(crypto, {})
    if not symbols:
        return {}

    # Fetch from all exchanges in parallel using ThreadPoolExecutor
    prices: Dict[str, float] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all fetch tasks
        futures = {
            "binance": executor.submit(get_binance_price, symbols.get("binance", "")),
            "kraken": executor.submit(get_kraken_price, symbols.get("kraken", "")),
            "coinbase": executor.submit(get_coinbase_price, symbols.get("coinbase", "")),
        }

        # Collect results with timeout
        for exchange, future in futures.items():
            try:
                price = future.result(timeout=2)
                if price is not None:
                    prices[exchange] = price
            except Exception:
                # Timeout or other error - skip this exchange
                pass

    return prices


# =============================================================================
# EXCHANGE CONFLUENCE DETECTION
# =============================================================================

# Module-level storage for epoch start prices
# Structure: {crypto: {epoch: {"binance": price, "kraken": price, "coinbase": price}}}
epoch_start_prices: Dict[str, Dict[int, Dict[str, float]]] = {}


def record_epoch_start_prices(crypto: str, epoch: int, prices: Dict[str, float]) -> None:
    """
    Record exchange prices at the start of an epoch for confluence tracking.

    Call this function when a new epoch is detected to capture baseline prices
    that will be used for confluence comparison throughout the epoch.

    Args:
        crypto: Cryptocurrency symbol (e.g., 'BTC', 'ETH', 'SOL', 'XRP')
        epoch: Epoch start timestamp (Unix seconds)
        prices: Dict of exchange prices from fetch_multi_exchange_prices()

    Example:
        >>> prices = fetch_multi_exchange_prices('BTC')
        >>> record_epoch_start_prices('BTC', 1737100200, prices)
        >>> epoch_start_prices['BTC'][1737100200]
        {'binance': 104523.50, 'kraken': 104521.00, 'coinbase': 104525.00}

    Notes:
        - Only stores if at least one exchange price is available
        - Old epochs are NOT automatically cleaned up (future enhancement)
        - Safe to call multiple times for same epoch (overwrites)
    """
    if not prices:
        return

    # Initialize crypto dict if needed
    if crypto not in epoch_start_prices:
        epoch_start_prices[crypto] = {}

    # Store the prices for this epoch
    epoch_start_prices[crypto][epoch] = prices.copy()


def get_exchange_confluence(
    crypto: str,
    epoch: int
) -> Tuple[Optional[str], int, float]:
    """
    Get exchange confluence direction by comparing current prices to epoch start.

    Fetches current prices from all exchanges and compares to the recorded
    epoch start prices. Returns the consensus direction (Up/Down), how many
    exchanges agree, and the average percentage change.

    Args:
        crypto: Cryptocurrency symbol (e.g., 'BTC', 'ETH', 'SOL', 'XRP')
        epoch: Epoch start timestamp (Unix seconds)

    Returns:
        Tuple of (direction, agree_count, avg_change_pct):
        - direction: 'Up', 'Down', or None if no consensus
        - agree_count: Number of exchanges showing same direction (0-3)
        - avg_change_pct: Average percentage change across agreeing exchanges

    Examples:
        >>> get_exchange_confluence('BTC', 1737100200)
        ('Down', 3, -0.45)  # All 3 exchanges agree: Down by 0.45%

        >>> get_exchange_confluence('ETH', 1737100200)
        ('Up', 2, 0.32)  # 2 of 3 agree: Up by 0.32%

        >>> get_exchange_confluence('SOL', 1737100200)
        (None, 1, 0.15)  # No consensus: only 1 exchange says Up

    Notes:
        - Change must exceed 0.1% to count as Up/Down (otherwise Flat)
        - If no start prices recorded, returns (None, 0, 0.0)
        - Uses MIN_EXCHANGES_AGREE config for threshold
        - Fetches fresh prices on each call (not cached)
    """
    # Check if we have start prices for this epoch
    if crypto not in epoch_start_prices:
        return (None, 0, 0.0)
    if epoch not in epoch_start_prices[crypto]:
        return (None, 0, 0.0)

    start_prices = epoch_start_prices[crypto][epoch]

    # Fetch current prices from all exchanges
    current_prices = fetch_multi_exchange_prices(crypto)
    if not current_prices:
        return (None, 0, 0.0)

    # Calculate direction for each exchange
    directions: Dict[str, Tuple[str, float]] = {}  # exchange -> (direction, change_pct)
    change_threshold = 0.001  # 0.1% minimum change to count as Up/Down

    for exchange, current_price in current_prices.items():
        if exchange not in start_prices:
            continue

        start_price = start_prices[exchange]
        if start_price <= 0:
            continue

        change_pct = (current_price - start_price) / start_price

        if change_pct > change_threshold:
            directions[exchange] = ('Up', change_pct)
        elif change_pct < -change_threshold:
            directions[exchange] = ('Down', change_pct)
        else:
            directions[exchange] = ('Flat', change_pct)

    if not directions:
        return (None, 0, 0.0)

    # Count votes for each direction
    up_count = sum(1 for d, _ in directions.values() if d == 'Up')
    down_count = sum(1 for d, _ in directions.values() if d == 'Down')

    # Calculate average change for winning direction
    if up_count >= MIN_EXCHANGES_AGREE:
        up_changes = [c for d, c in directions.values() if d == 'Up']
        avg_change = sum(up_changes) / len(up_changes) if up_changes else 0.0
        return ('Up', up_count, avg_change * 100)  # Convert to percentage
    elif down_count >= MIN_EXCHANGES_AGREE:
        down_changes = [c for d, c in directions.values() if d == 'Down']
        avg_change = sum(down_changes) / len(down_changes) if down_changes else 0.0
        return ('Down', down_count, avg_change * 100)  # Convert to percentage
    else:
        # No consensus - return the most popular direction even if below threshold
        max_count = max(up_count, down_count)
        if max_count > 0:
            # Return direction with most votes even without consensus
            if up_count > down_count:
                up_changes = [c for d, c in directions.values() if d == 'Up']
                avg_change = sum(up_changes) / len(up_changes) if up_changes else 0.0
                return (None, up_count, avg_change * 100)
            else:
                down_changes = [c for d, c in directions.values() if d == 'Down']
                avg_change = sum(down_changes) / len(down_changes) if down_changes else 0.0
                return (None, down_count, avg_change * 100)
        return (None, 0, 0.0)


# =============================================================================
# GRANULAR SIGNAL COMPARISON LOGGING
# =============================================================================

# Set up a separate logger for granular signals comparison (shadow testing)
granular_log: Optional[logging.Logger] = None
if ENABLE_GRANULAR_SHADOW_LOG:
    granular_log = logging.getLogger("granular_signals")
    granular_log.setLevel(logging.INFO)
    # Don't propagate to root logger (avoid duplicate logs)
    granular_log.propagate = False
    # Add file handler for granular_signals.log
    granular_handler = logging.FileHandler(
        Path(__file__).parent.parent / "granular_signals.log"
    )
    granular_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    granular_log.addHandler(granular_handler)


def log_granular_comparison(
    crypto: str,
    epoch: int,
    pattern_direction: Optional[str],
    old_accuracy: float,
    new_accuracy: float,
    magnitude_pct: float,
    magnitude_boost: float,
    confluence_direction: Optional[str],
    confluence_count: int,
    confluence_change: float
) -> None:
    """
    Log comparison between old and new granular signal logic for analysis.

    Logs to granular_signals.log when ENABLE_GRANULAR_SHADOW_LOG is True.
    Used during shadow testing to compare signal quality before enabling
    new features in live trading.

    Args:
        crypto: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
        epoch: Current epoch timestamp
        pattern_direction: Direction from pattern analysis ('Up', 'Down', or None)
        old_accuracy: Original pattern accuracy without boosts (0.0-1.0)
        new_accuracy: New accuracy with magnitude boost applied (0.0-1.0)
        magnitude_pct: Total price magnitude for pattern direction (e.g., 1.8 for 1.8%)
        magnitude_boost: Accuracy boost from magnitude (e.g., 0.01 for 1%)
        confluence_direction: Direction from exchange confluence ('Up', 'Down', or None)
        confluence_count: Number of exchanges agreeing (0-3)
        confluence_change: Average change percent across agreeing exchanges

    Format:
        [GRANULAR] BTC: Pattern=Down(74%) Magnitude=-1.8%(+3%) Confluence=2/3 -> Final=77%

    Example:
        >>> log_granular_comparison(
        ...     crypto='BTC', epoch=1705000000,
        ...     pattern_direction='Down', old_accuracy=0.74, new_accuracy=0.77,
        ...     magnitude_pct=1.8, magnitude_boost=0.03,
        ...     confluence_direction='Down', confluence_count=2,
        ...     confluence_change=-2.5
        ... )
        # Logs: [GRANULAR] BTC: Pattern=Down(74.0%) Magnitude=1.8%(+3.0%) Confluence=2/3 Down(-2.5%) -> Final=77.0%
    """
    if not ENABLE_GRANULAR_SHADOW_LOG or granular_log is None:
        return

    # Format pattern info
    if pattern_direction:
        pattern_str = f"Pattern={pattern_direction}({old_accuracy*100:.1f}%)"
    else:
        pattern_str = "Pattern=None"

    # Format magnitude info
    if magnitude_boost > 0:
        magnitude_str = f"Magnitude={magnitude_pct:.1f}%(+{magnitude_boost*100:.1f}%)"
    else:
        magnitude_str = f"Magnitude={magnitude_pct:.1f}%(+0%)"

    # Format confluence info
    if confluence_direction:
        confluence_str = f"Confluence={confluence_count}/3 {confluence_direction}({confluence_change:+.1f}%)"
    elif confluence_count > 0:
        confluence_str = f"Confluence={confluence_count}/3 NoConsensus({confluence_change:+.1f}%)"
    else:
        confluence_str = "Confluence=0/3"

    # Format final accuracy
    final_str = f"Final={new_accuracy*100:.1f}%"

    # Log the comparison
    granular_log.info(
        f"[GRANULAR] {crypto} epoch={epoch}: {pattern_str} {magnitude_str} {confluence_str} -> {final_str}"
    )


# =============================================================================
# SIGNALS DATABASE - Structured storage for analysis
# =============================================================================

# Database connection (module-level, initialized on first use)
_signals_db: Optional[sqlite3.Connection] = None


def _init_signals_db() -> sqlite3.Connection:
    """Initialize the signals database, creating tables if needed."""
    global _signals_db
    if _signals_db is not None:
        return _signals_db

    db_path = Path(__file__).parent.parent / "state" / "intra_signals.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Create signals table - stores ALL signals for analysis
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            crypto TEXT NOT NULL,
            epoch INTEGER NOT NULL,
            direction TEXT,
            pattern_accuracy REAL,
            magnitude_pct REAL,
            magnitude_boost REAL,
            confluence_direction TEXT,
            confluence_count INTEGER,
            confluence_change REAL,
            final_accuracy REAL,
            entry_price REAL,
            decision TEXT NOT NULL,
            reason TEXT,
            UNIQUE(crypto, epoch)
        )
    """)

    # Create trades table - stores actual trades placed
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            timestamp REAL NOT NULL,
            crypto TEXT NOT NULL,
            epoch INTEGER NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            size REAL NOT NULL,
            pattern_accuracy REAL,
            magnitude_pct REAL,
            confluence_count INTEGER,
            outcome TEXT,
            pnl REAL,
            FOREIGN KEY (signal_id) REFERENCES signals(id),
            UNIQUE(crypto, epoch)
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_epoch ON signals(epoch)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_decision ON signals(decision)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_epoch ON trades(epoch)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_outcome ON trades(outcome)")

    conn.commit()
    _signals_db = conn
    log.info(f"Signals database initialized: {db_path}")
    return conn


def log_signal_to_db(
    crypto: str,
    epoch: int,
    direction: Optional[str],
    pattern_accuracy: float,
    magnitude_pct: float,
    magnitude_boost: float,
    confluence_direction: Optional[str],
    confluence_count: int,
    confluence_change: float,
    final_accuracy: float,
    entry_price: Optional[float],
    decision: str,
    reason: str
) -> int:
    """
    Log a signal to the database for later analysis.

    Args:
        crypto: Cryptocurrency symbol
        epoch: Epoch timestamp
        direction: Pattern direction ('Up', 'Down', or None)
        pattern_accuracy: Base pattern accuracy (0-1)
        magnitude_pct: Cumulative magnitude percentage
        magnitude_boost: Accuracy boost from magnitude (0-1)
        confluence_direction: Direction from confluence ('Up', 'Down', or None)
        confluence_count: Number of exchanges agreeing (0-3)
        confluence_change: Average change percent across exchanges
        final_accuracy: Final accuracy with all boosts (0-1)
        entry_price: Polymarket entry price if available
        decision: 'TRADE', 'SKIP_WEAK', 'SKIP_CONFLUENCE', 'SKIP_ENTRY', etc.
        reason: Human-readable reason for decision

    Returns:
        signal_id: ID of inserted signal, or -1 on error
    """
    try:
        conn = _init_signals_db()
        cursor = conn.execute("""
            INSERT OR REPLACE INTO signals
            (timestamp, crypto, epoch, direction, pattern_accuracy, magnitude_pct,
             magnitude_boost, confluence_direction, confluence_count, confluence_change,
             final_accuracy, entry_price, decision, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(), crypto, epoch, direction, pattern_accuracy, magnitude_pct,
            magnitude_boost, confluence_direction, confluence_count, confluence_change,
            final_accuracy, entry_price, decision, reason
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        log.error(f"Error logging signal to DB: {e}")
        return -1


def log_trade_to_db(
    crypto: str,
    epoch: int,
    direction: str,
    entry_price: float,
    size: float,
    pattern_accuracy: float,
    magnitude_pct: float,
    confluence_count: int
) -> int:
    """
    Log a trade to the database.

    Args:
        crypto: Cryptocurrency symbol
        epoch: Epoch timestamp
        direction: Trade direction ('Up' or 'Down')
        entry_price: Entry price
        size: Trade size in USD
        pattern_accuracy: Pattern accuracy at time of trade
        magnitude_pct: Magnitude percentage
        confluence_count: Number of exchanges agreeing

    Returns:
        trade_id: ID of inserted trade, or -1 on error
    """
    try:
        conn = _init_signals_db()

        # Find the corresponding signal
        signal_row = conn.execute(
            "SELECT id FROM signals WHERE crypto=? AND epoch=?",
            (crypto, epoch)
        ).fetchone()
        signal_id = signal_row[0] if signal_row else None

        cursor = conn.execute("""
            INSERT OR REPLACE INTO trades
            (signal_id, timestamp, crypto, epoch, direction, entry_price, size,
             pattern_accuracy, magnitude_pct, confluence_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_id, time.time(), crypto, epoch, direction, entry_price, size,
            pattern_accuracy, magnitude_pct, confluence_count
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        log.error(f"Error logging trade to DB: {e}")
        return -1


def update_trade_outcome(crypto: str, epoch: int, outcome: str, pnl: float):
    """
    Update a trade with its outcome after resolution.

    Args:
        crypto: Cryptocurrency symbol
        epoch: Epoch timestamp
        outcome: 'WIN' or 'LOSS'
        pnl: Profit/loss in USD
    """
    try:
        conn = _init_signals_db()
        conn.execute(
            "UPDATE trades SET outcome=?, pnl=? WHERE crypto=? AND epoch=?",
            (outcome, pnl, crypto, epoch)
        )
        conn.commit()
    except Exception as e:
        log.error(f"Error updating trade outcome: {e}")


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

def analyze_pattern(
    minutes: List[str],
    candles: Optional[List[Dict[str, Union[str, float]]]] = None
) -> Tuple[Optional[str], float, str]:
    """
    Analyze minute patterns and return (direction, accuracy, reason).

    Only returns signals for strong patterns (74%+ accuracy). When candle data
    is provided, applies magnitude checks and accuracy boosts based on move
    strength.

    Args:
        minutes: List of direction strings ("Up" or "Down") for each minute
        candles: Optional list of candle dicts with magnitude data. If provided,
                 enables magnitude checks and accuracy boosts (US-GS-008).
                 Each dict should have 'direction', 'change_pct', and 'volume'.

    Returns:
        Tuple of (direction, accuracy, reason) where:
        - direction: "Up", "Down", or None if no strong pattern
        - accuracy: Base accuracy (0.74-0.80) plus any magnitude boost
        - reason: Human-readable explanation including magnitude info

    Notes:
        - Backward compatible: if candles not provided, behaves as before
        - When ENABLE_MAGNITUDE_TRACKING is True and candles provided:
          - Rejects patterns failing MIN_CUMULATIVE_MAGNITUDE check
          - Adds accuracy boost for strong moves (up to MAGNITUDE_ACCURACY_BOOST)
          - Includes magnitude info in reason string
    """
    if not minutes or len(minutes) < 3:
        return (None, 0.0, "Not enough data")

    # Pattern 1: 4+ of first 5 minutes same direction (strongest)
    if len(minutes) >= 5:
        first_5 = minutes[:5]
        ups = sum(1 for m in first_5 if m == 'Up')
        downs = 5 - ups

        if ups >= 4:
            direction = 'Up'
            base_accuracy = 0.797
            base_reason = f"{ups}/5 UP"
        elif downs >= 4:
            direction = 'Down'
            base_accuracy = 0.740
            base_reason = f"{downs}/5 DOWN"
        else:
            # No 4/5 pattern, check 3/3 below
            direction = None
            base_accuracy = 0.0
            base_reason = ""
    else:
        direction = None
        base_accuracy = 0.0
        base_reason = ""

    # Pattern 2: All first 3 minutes same direction (only if no 4/5 pattern)
    if direction is None:
        first_3 = minutes[:3]
        if all(m == 'Up' for m in first_3):
            direction = 'Up'
            base_accuracy = 0.780
            base_reason = "3/3 UP"
        elif all(m == 'Down' for m in first_3):
            direction = 'Down'
            base_accuracy = 0.739
            base_reason = "3/3 DOWN"

    # No strong pattern found
    if direction is None:
        return (None, 0.0, "No strong pattern detected")

    # === Magnitude Enhancement (US-GS-008) ===
    # Only apply if candles provided and magnitude tracking enabled
    if candles and ENABLE_MAGNITUDE_TRACKING:
        # Check cumulative magnitude threshold
        passes_magnitude, total_magnitude = check_cumulative_magnitude(candles, direction)
        if not passes_magnitude:
            magnitude_pct = total_magnitude * 100
            return (
                None,
                0.0,
                f"Pattern {base_reason} rejected: magnitude {magnitude_pct:.2f}% < {MIN_CUMULATIVE_MAGNITUDE * 100:.1f}% threshold"
            )

        # Get strong/weak move counts
        strong_count, weak_count = check_per_minute_magnitude(candles, direction)

        # Calculate accuracy boost
        magnitude_boost = calculate_magnitude_boost(candles, direction)

        # Final accuracy with boost
        final_accuracy = base_accuracy + magnitude_boost

        # Build enhanced reason string
        magnitude_pct = total_magnitude * 100
        boost_pct = magnitude_boost * 100
        if magnitude_boost > 0:
            reason = f"{base_reason} ({magnitude_pct:+.1f}%) [{strong_count}strong/{strong_count + weak_count}total] = {final_accuracy * 100:.1f}% (+{boost_pct:.1f}% boost)"
        else:
            reason = f"{base_reason} ({magnitude_pct:+.1f}%) = {base_accuracy * 100:.1f}%"

        return (direction, final_accuracy, reason)

    # No candles or magnitude tracking disabled - return base pattern
    return (direction, base_accuracy, f"{base_reason} = {base_accuracy * 100:.1f}% accuracy")

# =============================================================================
# TRADING
# =============================================================================

def get_clob_client() -> Optional[ClobClient]:
    """Initialize CLOB client for trading."""
    try:
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        wallet = os.getenv("POLYMARKET_WALLET")

        if not private_key:
            log.error("POLYMARKET_PRIVATE_KEY not set")
            return None
        if not wallet:
            log.error("POLYMARKET_WALLET not set")
            return None

        # First create client to derive API key
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=POLYGON,
            key=private_key,
            signature_type=0,  # EOA wallet (not POLY_GNOSIS_SAFE)
            funder=wallet
        )

        # Derive API credentials
        creds = client.derive_api_key()

        # Create new client with credentials
        return ClobClient(
            host="https://clob.polymarket.com",
            chain_id=POLYGON,
            key=private_key,
            signature_type=0,
            funder=wallet,
            creds=creds
        )

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


def calculate_position_size(balance: float, accuracy: float, existing_size: float = 0.0) -> float:
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

    # If averaging, make sure we don't exceed max total position
    if existing_size > 0:
        max_add = MAX_TOTAL_POSITION_USD - existing_size
        size = min(size, max_add)

    return round(size, 2)


def check_averaging_opportunity(
    crypto: str,
    position: dict,
    current_price: float,
    pattern_direction: str
) -> Tuple[bool, str]:
    """
    Check if we should add to an existing position.

    Returns:
        (should_add, reason)
    """
    if not ENABLE_POSITION_AVERAGING:
        return (False, "Averaging disabled")

    # Must be same direction as existing position
    if pattern_direction != position['direction']:
        return (False, f"Pattern {pattern_direction} != position {position['direction']}")

    # Check if we've already maxed out adds
    adds = position.get('adds', 0)
    if adds >= MAX_ADDS_PER_POSITION:
        return (False, f"Max adds reached ({adds}/{MAX_ADDS_PER_POSITION})")

    # Check if we're already at max position size
    current_size = position['size']
    if current_size >= MAX_TOTAL_POSITION_USD:
        return (False, f"Max position size reached (${current_size:.2f})")

    # Check if price has improved enough
    entry_price = position['entry_price']
    improvement = (entry_price - current_price) / entry_price

    if improvement < PRICE_IMPROVE_THRESHOLD:
        return (False, f"Price improvement {improvement:.1%} < {PRICE_IMPROVE_THRESHOLD:.0%} threshold")

    # NEW: Stop averaging if price dropped too much - this signals the trade is likely wrong
    # In binary markets, price drop = market saying our direction is LESS likely
    if improvement > MAX_PRICE_DROP_FOR_AVERAGING:
        return (False, f"Price dropped {improvement:.1%} > {MAX_PRICE_DROP_FOR_AVERAGING:.0%} - signal may be wrong, not averaging")

    # All checks passed
    return (True, f"Price improved {improvement:.1%} (${entry_price:.2f} -> ${current_price:.2f})")


def place_trade(client: ClobClient, crypto: str, direction: str,
                token_id: str, price: float, size_usd: float) -> Tuple[bool, float]:
    """
    Place a trade on Polymarket and verify it fills.

    Returns:
        (success, filled_size_usd) - True only if order filled, with actual filled amount
    """
    try:
        # Calculate shares
        shares = size_usd / price

        # Shadow mode - log but don't execute
        if SHADOW_MODE:
            log.info(f"🔮 SHADOW ORDER: {crypto} {direction} @ ${price:.2f}, ${size_usd:.2f} ({shares:.1f} shares)")
            log.info(f"   [Shadow mode - no real trade placed]")
            return (True, size_usd)  # Simulate successful fill

        log.info(f"Placing order: {crypto} {direction} @ ${price:.2f}, ${size_usd:.2f} ({shares:.1f} shares)")

        order_args = OrderArgs(
            price=price,
            size=shares,
            side="BUY",
            token_id=token_id
        )

        signed_order = client.create_order(order_args)
        response = client.post_order(signed_order, OrderType.GTC)

        if not response or not response.get("success"):
            log.error(f"Order placement failed: {response}")
            return (False, 0.0)

        order_id = response.get("orderID")
        if not order_id:
            log.error(f"No order ID in response: {response}")
            return (False, 0.0)

        log.info(f"Order submitted: {order_id}")

        # Wait briefly for order to fill (check multiple times)
        filled_shares = 0.0
        for attempt in range(5):  # Check 5 times over ~2.5 seconds
            time.sleep(0.5)

            try:
                order_status = client.get_order(order_id)
                if order_status:
                    filled_shares = float(order_status.get("size_matched", 0))
                    original_size = float(order_status.get("original_size", shares))
                    fill_pct = (filled_shares / original_size * 100) if original_size > 0 else 0

                    if filled_shares > 0:
                        log.info(f"Order fill check {attempt+1}: {filled_shares:.1f}/{original_size:.1f} shares ({fill_pct:.0f}%)")

                    # If fully filled, we're done
                    if fill_pct >= 99:
                        break
            except Exception as e:
                log.warning(f"Error checking order status: {e}")

        # Calculate filled USD value
        filled_usd = filled_shares * price

        # Determine if order was sufficiently filled (at least 50%)
        min_fill_pct = 0.50
        if filled_shares >= shares * min_fill_pct:
            log.info(f"ORDER FILLED: {crypto} {direction} - ${filled_usd:.2f} @ ${price:.2f} ({filled_shares:.1f} shares)")

            # Cancel any remaining unfilled portion
            if filled_shares < shares * 0.99:
                try:
                    client.cancel(order_id)
                    log.info(f"Cancelled unfilled remainder of order {order_id}")
                except Exception as e:
                    log.warning(f"Could not cancel remainder: {e}")

            return (True, filled_usd)
        else:
            # Order didn't fill enough - cancel it
            log.warning(f"Order not filled (got {filled_shares:.1f}/{shares:.1f} shares). Cancelling...")
            try:
                client.cancel(order_id)
                log.info(f"Cancelled unfilled order {order_id}")
            except Exception as e:
                log.warning(f"Could not cancel order: {e}")

            # If we got partial fill, still return that amount
            if filled_shares > 0:
                log.info(f"Partial fill kept: ${filled_usd:.2f}")
                return (True, filled_usd)

            return (False, 0.0)

    except Exception as e:
        log.error(f"Failed to place trade: {e}")
        return (False, 0.0)

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

                # Telegram notification
                notify_result(crypto, direction, True, profit, state.current_balance, state.win_rate())

                # Update trade outcome in signals database
                update_trade_outcome(crypto, pos_epoch, "WIN", profit)

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

                # Telegram notification
                notify_result(crypto, direction, False, -size, state.current_balance, state.win_rate())

                # Update trade outcome in signals database
                update_trade_outcome(crypto, pos_epoch, "LOSS", -size)

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


def get_redeemable_value() -> float:
    """Get total value of redeemable positions from API."""
    try:
        wallet = os.getenv("POLYMARKET_WALLET")
        if not wallet:
            return 0.0

        resp = requests.get(
            "https://data-api.polymarket.com/positions",
            params={"user": wallet, "redeemable": "true", "limit": 50},
            timeout=10
        )

        if resp.status_code != 200:
            return 0.0

        positions = resp.json()
        total = 0.0
        for pos in positions:
            size = float(pos.get('size', 0))
            total += size  # Redeemable positions are worth $1 per share

        return total

    except Exception as e:
        log.warning(f"Failed to get redeemable value: {e}")
        return 0.0


def check_risk_limits(state: BotState) -> bool:
    """Check if we should continue trading."""
    # Get effective balance (cash + redeemable positions)
    redeemable = get_redeemable_value()
    effective_balance = state.current_balance + redeemable

    # Check drawdown using effective balance
    if state.peak_balance > 0:
        drawdown = (state.peak_balance - effective_balance) / state.peak_balance
        if drawdown >= MAX_DRAWDOWN_PCT:
            state.halted = True
            state.halt_reason = f"Drawdown {drawdown:.1%} exceeds {MAX_DRAWDOWN_PCT:.0%}"
            log.error(f"HALTED: {state.halt_reason} (cash=${state.current_balance:.2f} + redeemable=${redeemable:.2f})")
            notify_alert(f"Bot HALTED!\n{state.halt_reason}\nCash: ${state.current_balance:.2f}\nRedeemable: ${redeemable:.2f}")
            return False

    # Check daily loss
    if state.daily_pnl <= -MAX_DAILY_LOSS_USD:
        state.halted = True
        state.halt_reason = f"Daily loss ${abs(state.daily_pnl):.2f} exceeds ${MAX_DAILY_LOSS_USD}"
        log.error(f"HALTED: {state.halt_reason}")
        notify_alert(f"Bot HALTED!\n{state.halt_reason}\nBalance: ${state.current_balance:.2f}")
        return False

    return True


def run_bot():
    """Main bot loop."""
    log.info("=" * 60)
    if SHADOW_MODE:
        log.info("🔮 INTRA-EPOCH MOMENTUM BOT - SHADOW MODE 🔮")
        log.info("   (No real trades - observation only)")
    else:
        log.info("INTRA-EPOCH MOMENTUM BOT STARTING")
    log.info("=" * 60)
    log.info(f"Edge Buffer: {EDGE_BUFFER:.0%} (max entry = accuracy - {EDGE_BUFFER:.0%})")
    log.info(f"Min Pattern Accuracy: {MIN_PATTERN_ACCURACY:.0%}")
    log.info(f"Trading Window: minutes 3-10")
    log.info(f"Position Size: ${BASE_POSITION_USD}-${MAX_POSITION_USD}")
    if ENABLE_POSITION_AVERAGING:
        log.info(f"Position Averaging: ENABLED")
        log.info(f"  - Trigger: {PRICE_IMPROVE_THRESHOLD:.0%}-{MAX_PRICE_DROP_FOR_AVERAGING:.0%} price improvement")
        log.info(f"  - Add Size: {AVERAGING_SIZE_MULTIPLIER:.0%} of normal (reduced risk)")
        log.info(f"  - Max Adds: {MAX_ADDS_PER_POSITION}")
    else:
        log.info(f"Position Averaging: DISABLED")
    log.info(f"Telegram Alerts: {'ENABLED' if TELEGRAM_ENABLED else 'DISABLED'}")
    # Granular Signal Enhancement settings
    if ENABLE_MAGNITUDE_TRACKING or ENABLE_MULTI_EXCHANGE:
        log.info("-" * 40)
        log.info("Granular Signals: ENABLED")
        if ENABLE_MAGNITUDE_TRACKING:
            log.info(f"  - Magnitude: min cumulative {MIN_CUMULATIVE_MAGNITUDE*100:.1f}%, "
                     f"min per-minute {MIN_PER_MINUTE_MAGNITUDE*100:.1f}%, "
                     f"boost up to {MAGNITUDE_ACCURACY_BOOST*100:.0f}%")
        else:
            log.info(f"  - Magnitude: DISABLED")
        if ENABLE_MULTI_EXCHANGE:
            log.info(f"  - Multi-Exchange: {MIN_EXCHANGES_AGREE}/3 required (Binance, Kraken, Coinbase)")
        else:
            log.info(f"  - Multi-Exchange: DISABLED")
        log.info(f"  - Shadow Logging: {'ENABLED' if ENABLE_GRANULAR_SHADOW_LOG else 'DISABLED'}")
    else:
        log.info("-" * 40)
        log.info("Granular Signals: DISABLED")
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

    log.info("CLOB client initialized.")

    # Initialize auto-redeemer
    redeemer = AutoRedeemer()
    log.info(f"Auto-Redeemer: {'ENABLED' if redeemer.enabled else 'DISABLED'}")

    log.info("Starting main loop...")

    # Send startup notification
    if TELEGRAM_ENABLED:
        send_telegram(
            f"🤖 <b>Intra-Epoch Bot Started</b>\n"
            f"Balance: ${state.current_balance:.2f}\n"
            f"Trades: {state.total_trades} ({state.total_wins}W/{state.total_losses}L)"
        )

    last_epoch = 0
    last_redeem_check = 0

    try:
        while True:
            # Get current epoch
            epoch_start, time_in_epoch = get_current_epoch()

            # Always check for redemptions every epoch (even when halted)
            if epoch_start != last_redeem_check and redeemer.enabled:
                last_redeem_check = epoch_start
                redeemed, value = redeemer.check_and_redeem()
                if redeemed > 0:
                    time.sleep(2)  # Wait for chain to settle
                    balance = get_wallet_balance()
                    if balance > 0:
                        state.current_balance = balance
                        if balance > state.peak_balance:
                            state.peak_balance = balance
                        state.save()
                        log.info(f"Balance updated after redemption: ${balance:.2f}")

                        # Auto-unhalt if redemption fixed the drawdown
                        if state.halted and state.peak_balance > 0:
                            current_drawdown = (state.peak_balance - state.current_balance) / state.peak_balance
                            if current_drawdown < MAX_DRAWDOWN_PCT:
                                state.halted = False
                                state.halt_reason = ""
                                state.save()
                                log.info(f"AUTO-RESUMED: Drawdown now {current_drawdown:.1%} (below {MAX_DRAWDOWN_PCT:.0%})")
                                notify_alert(f"Bot AUTO-RESUMED after redemption!\nDrawdown: {current_drawdown:.1%}\nBalance: ${state.current_balance:.2f}")

            # Check if halted (but still allow redemptions above)
            if state.halted:
                log.warning(f"Bot is HALTED: {state.halt_reason}")
                time.sleep(60)
                continue

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

                # Record epoch start prices for confluence detection (multi-exchange)
                if ENABLE_MULTI_EXCHANGE:
                    for crypto in CRYPTOS:
                        prices = fetch_multi_exchange_prices(crypto)
                        if prices:
                            record_epoch_start_prices(crypto, epoch_start, prices)
                            log.debug(f"{crypto}: Recorded epoch start prices from {len(prices)} exchanges")

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
            scan_results = []  # Track what happened with each crypto

            for crypto in CRYPTOS:
                # Skip if already traded this epoch (but allow averaging same epoch)
                already_traded_this_epoch = state.last_epoch_traded.get(crypto) == epoch_start
                has_existing_position = crypto in state.positions

                # If we traded this epoch but don't have a position, something went wrong
                if already_traded_this_epoch and not has_existing_position:
                    scan_results.append(f"{crypto}:traded")
                    continue

                # Check position limit (only for new positions)
                if not has_existing_position and len(state.positions) >= MAX_POSITIONS:
                    scan_results.append(f"{crypto}:max_pos")
                    continue

                # Fetch minute candles (now returns dicts with magnitude data)
                candles = fetch_minute_candles(crypto, epoch_start)
                if not candles:
                    scan_results.append(f"{crypto}:no_data")
                    continue

                # Get direction-only list for pattern analysis (backward compatibility)
                minutes = get_directions_from_candles(candles)
                if not minutes:
                    scan_results.append(f"{crypto}:no_data")
                    continue

                # Analyze pattern (pass candles for magnitude enhancement)
                direction, accuracy, reason = analyze_pattern(minutes, candles)

                # Skip weak patterns
                if not direction or accuracy < MIN_PATTERN_ACCURACY:
                    ups = sum(1 for m in minutes if m == 'Up')
                    downs = len(minutes) - ups
                    scan_results.append(f"{crypto}:{ups}↑{downs}↓(weak)")
                    # Log granular comparison even for weak patterns (for analysis)
                    if candles and ENABLE_GRANULAR_SHADOW_LOG:
                        # Determine dominant direction for logging
                        weak_dir = "Up" if ups > downs else "Down" if downs > ups else None
                        if weak_dir:
                            magnitude_boost = calculate_magnitude_boost(candles, weak_dir)
                            magnitude_pct = sum(abs(c.get('change_pct', 0)) for c in candles if c.get('direction') == weak_dir)
                            log_granular_comparison(
                                crypto=crypto, epoch=epoch_start,
                                pattern_direction=weak_dir, old_accuracy=accuracy, new_accuracy=accuracy,
                                magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                                confluence_direction=None, confluence_count=0, confluence_change=0.0
                            )
                            # Log to database
                            log_signal_to_db(
                                crypto=crypto, epoch=epoch_start, direction=weak_dir,
                                pattern_accuracy=accuracy, magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                                confluence_direction=None, confluence_count=0, confluence_change=0.0,
                                final_accuracy=accuracy, entry_price=None,
                                decision="SKIP_WEAK", reason=f"Pattern too weak: {ups}↑{downs}↓"
                            )
                    continue

                # Fetch Polymarket prices
                prices = fetch_polymarket_prices(crypto, epoch_start)
                if not prices:
                    scan_results.append(f"{crypto}:{direction}(no_prices)")
                    continue

                entry_price = prices[direction]['ask']

                # Check if this is an averaging opportunity
                if has_existing_position:
                    existing_pos = state.positions[crypto]
                    should_add, avg_reason = check_averaging_opportunity(
                        crypto, existing_pos, entry_price, direction
                    )

                    if not should_add:
                        scan_results.append(f"{crypto}:holding")
                        log.debug(f"{crypto}: No averaging - {avg_reason}")
                        continue

                    # Averaging opportunity found!
                    scan_results.append(f"{crypto}:{direction}+ADD")

                    # Calculate additional position size (reduced to limit downside risk)
                    existing_size = existing_pos['size']
                    base_add_size = calculate_position_size(state.current_balance, accuracy, existing_size)
                    # Apply averaging multiplier - only add 50% of normal to reduce exposure on potential losing trades
                    add_size = base_add_size * AVERAGING_SIZE_MULTIPLIER
                    add_size = max(MIN_BET_USD, round(add_size, 2))  # Ensure minimum bet

                    if add_size < MIN_BET_USD:
                        log.info(f"{crypto}: Add size ${add_size:.2f} below minimum")
                        continue

                    # Log the averaging signal
                    log.info(f"")
                    log.info(f"{'='*50}")
                    log.info(f"AVERAGING: {crypto} {direction}")
                    log.info(f"  {avg_reason}")
                    log.info(f"  Original Entry: ${existing_pos['entry_price']:.2f}")
                    log.info(f"  New Entry: ${entry_price:.2f}")
                    log.info(f"  Existing Size: ${existing_size:.2f}")
                    log.info(f"  Adding: ${add_size:.2f} (50% of ${base_add_size:.2f})")
                    log.info(f"{'='*50}")

                    # Place averaging trade
                    token_id = prices[direction]['token_id']
                    success, filled_size = place_trade(client, crypto, direction, token_id, entry_price, add_size)

                    if success and filled_size > 0:
                        # Calculate new weighted average entry price
                        old_cost = existing_size  # USD spent originally
                        new_cost = filled_size    # USD spent now
                        total_cost = old_cost + new_cost

                        old_shares = existing_size / existing_pos['entry_price']
                        new_shares = filled_size / entry_price
                        total_shares = old_shares + new_shares

                        avg_entry = total_cost / total_shares

                        # Update position
                        state.positions[crypto] = {
                            'direction': direction,
                            'entry_price': avg_entry,  # Weighted average
                            'size': total_cost,        # Total USD invested
                            'epoch': existing_pos['epoch'],  # Keep original epoch
                            'accuracy': accuracy,
                            'adds': existing_pos.get('adds', 0) + 1
                        }
                        state.last_epoch_traded[crypto] = epoch_start
                        state.total_trades += 1
                        state.save()

                        log.info(f"Position AVERAGED: ${total_cost:.2f} @ ${avg_entry:.2f} (was ${existing_pos['entry_price']:.2f})")
                        notify_trade(
                            crypto, direction, entry_price, filled_size,
                            accuracy=accuracy, magnitude_boost=0.0,
                            confluence_count=0, is_averaging=True
                        )
                    else:
                        log.warning(f"{crypto}: Averaging order did not fill")

                    continue

                # New position logic (no existing position)

                # Check exchange confluence before placing trade
                confluence_dir: Optional[str] = None
                agree_count: int = 0
                avg_change: float = 0.0

                if ENABLE_MULTI_EXCHANGE:
                    confluence_dir, agree_count, avg_change = get_exchange_confluence(crypto, epoch_start)
                    if confluence_dir is not None:
                        if confluence_dir == direction:
                            log.info(f"Confluence: {agree_count}/3 exchanges agree {direction} ({avg_change:+.2f}%)")
                        else:
                            log.info(f"SKIP: Pattern={direction} but confluence={confluence_dir} ({agree_count}/3 exchanges, {avg_change:+.2f}%)")
                            scan_results.append(f"{crypto}:{direction}(conf_mismatch)")
                            # Log granular comparison even for skipped trades
                            magnitude_boost = calculate_magnitude_boost(candles, direction) if candles else 0.0
                            magnitude_pct = sum(abs(c.get('change_pct', 0)) for c in candles if c.get('direction') == direction) if candles else 0.0
                            old_accuracy = accuracy - magnitude_boost  # Original accuracy without boost
                            log_granular_comparison(
                                crypto=crypto, epoch=epoch_start,
                                pattern_direction=direction, old_accuracy=old_accuracy, new_accuracy=accuracy,
                                magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                                confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change
                            )
                            # Log to database
                            log_signal_to_db(
                                crypto=crypto, epoch=epoch_start, direction=direction,
                                pattern_accuracy=old_accuracy, magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                                confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change,
                                final_accuracy=accuracy, entry_price=entry_price,
                                decision="SKIP_CONF_MISMATCH", reason=f"Pattern={direction} but confluence={confluence_dir}"
                            )
                            continue
                    else:
                        # No consensus = choppy market, BLOCK the trade
                        log.info(f"SKIP: No confluence - only {agree_count}/3 exchanges agree ({avg_change:+.2f}%) - market too choppy")
                        scan_results.append(f"{crypto}:{direction}(no_conf)")
                        # Log granular comparison even for skipped trades
                        magnitude_boost = calculate_magnitude_boost(candles, direction) if candles else 0.0
                        magnitude_pct = sum(abs(c.get('change_pct', 0)) for c in candles if c.get('direction') == direction) if candles else 0.0
                        old_accuracy = accuracy - magnitude_boost
                        log_granular_comparison(
                            crypto=crypto, epoch=epoch_start,
                            pattern_direction=direction, old_accuracy=old_accuracy, new_accuracy=accuracy,
                            magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                            confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change
                        )
                        # Log to database
                        log_signal_to_db(
                            crypto=crypto, epoch=epoch_start, direction=direction,
                            pattern_accuracy=old_accuracy, magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                            confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change,
                            final_accuracy=accuracy, entry_price=entry_price,
                            decision="SKIP_NO_CONFLUENCE", reason=f"No confluence - only {agree_count}/3 exchanges agree"
                        )
                        continue

                scan_results.append(f"{crypto}:{direction}({accuracy*100:.0f}%)")

                # Log granular signal data for ALL patterns that pass initial checks
                magnitude_boost = calculate_magnitude_boost(candles, direction) if candles else 0.0
                magnitude_pct = sum(abs(c.get('change_pct', 0)) for c in candles if c.get('direction') == direction) if candles else 0.0
                old_accuracy = accuracy - magnitude_boost
                log_granular_comparison(
                    crypto=crypto, epoch=epoch_start,
                    pattern_direction=direction, old_accuracy=old_accuracy, new_accuracy=accuracy,
                    magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                    confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change
                )

                # Check entry price - must have edge over break-even
                max_entry = accuracy - EDGE_BUFFER  # e.g., 74% accuracy -> max $0.69 entry
                if entry_price > max_entry:
                    log.info(f"{crypto}: {direction} ({accuracy*100:.0f}%) but entry ${entry_price:.2f} > ${max_entry:.2f} max (no edge)")
                    # Log to database
                    log_signal_to_db(
                        crypto=crypto, epoch=epoch_start, direction=direction,
                        pattern_accuracy=old_accuracy, magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                        confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change,
                        final_accuracy=accuracy, entry_price=entry_price,
                        decision="SKIP_ENTRY_PRICE", reason=f"Entry ${entry_price:.2f} > ${max_entry:.2f} max"
                    )
                    continue

                # Calculate position size
                size = calculate_position_size(state.current_balance, accuracy)

                if size < MIN_BET_USD:
                    log.warning(f"{crypto}: Position size ${size:.2f} below minimum")
                    continue

                # Log the signal to database BEFORE placing trade
                signal_id = log_signal_to_db(
                    crypto=crypto, epoch=epoch_start, direction=direction,
                    pattern_accuracy=old_accuracy, magnitude_pct=magnitude_pct, magnitude_boost=magnitude_boost,
                    confluence_direction=confluence_dir, confluence_count=agree_count, confluence_change=avg_change,
                    final_accuracy=accuracy, entry_price=entry_price,
                    decision="TRADE", reason=reason
                )

                # Log the signal
                log.info(f"")
                log.info(f"{'='*50}")
                log.info(f"SIGNAL: {crypto} {direction}")
                log.info(f"  Pattern: {reason}")
                log.info(f"  Entry Price: ${entry_price:.2f}")
                log.info(f"  Position Size: ${size:.2f}")
                log.info(f"{'='*50}")

                # Place trade and verify fill
                token_id = prices[direction]['token_id']
                success, filled_size = place_trade(client, crypto, direction, token_id, entry_price, size)

                if success and filled_size > 0:
                    # Record position with ACTUAL filled size (not requested size)
                    state.positions[crypto] = {
                        'direction': direction,
                        'entry_price': entry_price,
                        'size': filled_size,  # Use actual filled amount
                        'epoch': epoch_start,
                        'accuracy': accuracy,
                        'adds': 0  # Track averaging adds
                    }
                    state.last_epoch_traded[crypto] = epoch_start
                    state.total_trades += 1
                    state.save()

                    # Log trade to database
                    log_trade_to_db(
                        crypto=crypto, epoch=epoch_start, direction=direction,
                        entry_price=entry_price, size=filled_size,
                        pattern_accuracy=accuracy, magnitude_pct=magnitude_pct, confluence_count=agree_count
                    )

                    log.info(f"Position recorded: ${filled_size:.2f}. Total positions: {len(state.positions)}")
                    notify_trade(
                        crypto, direction, entry_price, filled_size,
                        accuracy=accuracy, magnitude_boost=magnitude_boost,
                        confluence_count=agree_count, is_averaging=False
                    )
                else:
                    log.warning(f"{crypto}: Order did not fill - no position recorded")

            # Log scan summary
            mins_in = time_in_epoch // 60
            secs_in = time_in_epoch % 60
            log.info(f"[min {mins_in}:{secs_in:02d}] Scan: {' | '.join(scan_results)}")

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
