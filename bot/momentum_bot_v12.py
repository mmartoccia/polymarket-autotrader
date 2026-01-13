#!/usr/bin/env python3
"""
Momentum Trading Bot v12.1 - FUTURE WINDOW ENHANCED EDITION

Based on comprehensive audit by the "Hacker Team" (v2 analysis):

CRITICAL FIXES IN V12:
1. FIXED: Undefined constants (STOP_LOSS_CHECK_INTERVAL, STOP_LOSS_MIN_TIME)
2. FIXED: Contrarian logic was broken - now properly fades extreme prices
3. FIXED: Peak balance reset on new day (prevents false drawdown halts)
4. EVEN LOWER ENTRY: Max entry $0.30 (was $0.40) - fee economics require this
5. STRONGER SIGNALS: MIN_SIGNAL_STRENGTH 0.72 (was 0.65)
6. DISABLED: Fallback forced bets (were causing losses)
7. SCAN INTERVAL: Back to 2s (faster wasn't helping, just API load)

NEW IN V12.1 - FUTURE WINDOW TRADING:
8. FUTURE ANALYSIS: Looks ahead 2-3 windows for pricing anomalies
9. MOMENTUM LAG: Trades cheap future windows that haven't caught up to current trend
10. CONTRADICTION CHECK: Warns when future windows contradict current trades
11. CONFIDENCE BOOST: Increases position when future windows align with current

FEE ECONOMICS (why $0.30 max entry):
- At $0.50 entry: 3.15% fee per side = 6.3% round-trip, need 53%+ win rate
- At $0.40 entry: 2.50% fee per side = 5.0% round-trip, need 52.5%+ win rate
- At $0.30 entry: 1.88% fee per side = 3.75% round-trip, need 51.5%+ win rate
- At $0.25 entry: 1.56% fee per side = 3.12% round-trip, need 51%+ win rate

SWEET SPOT: Trade only when entry is $0.25-0.35 for manageable fee drag.

RETAINED:
- Tiered position sizing
- Correlation protection
- Trend filter
- Recovery mode
- All 4 cryptos (BTC, ETH, SOL, XRP)
"""

import requests
import time
import logging
import json
import os
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL
from web3 import Web3
from eth_account import Account

# Load environment variables
# Try to load from parent directory first (when run from bots/), then current dir
env_paths = [
    Path(__file__).parent.parent / '.env',  # Parent directory
    Path(__file__).parent / '.env',         # Current directory
    Path.cwd() / '.env'                     # Working directory
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break

# Import timeframe tracker for multi-timeframe analysis
try:
    from timeframe_tracker import TimeframeTracker
    TIMEFRAME_TRACKING_ENABLED = True
except ImportError:
    TIMEFRAME_TRACKING_ENABLED = False
    log = logging.getLogger(__name__)
    log.warning("TimeframeTracker not available - running without multi-TF tracking")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Wallet - from environment variables
KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
EOA = os.getenv('POLYMARKET_WALLET')

# Validate required environment variables
if not KEY or not EOA:
    print("=" * 60)
    print("ERROR: Missing required environment variables")
    print("=" * 60)
    print("Please set the following in your .env file:")
    print("  POLYMARKET_WALLET=0xYourWalletAddress")
    print("  POLYMARKET_PRIVATE_KEY=0xYourPrivateKey")
    print()
    print("See .env.example for template")
    print("=" * 60)
    sys.exit(1)

# =============================================================================
# POSITION SIZING - FIX #1: Tiered percentage cap based on balance
# =============================================================================
# Tiered approach: smaller balances need higher % to recover
# But NEVER allow the catastrophic 80%+ bets that killed us
POSITION_TIERS = [
    (30, 0.15),     # Balance < $30: max 15% per trade (need to risk to recover)
    (75, 0.10),     # Balance $30-75: max 10% per trade
    (150, 0.07),    # Balance $75-150: max 7% per trade
    (float('inf'), 0.05),  # Balance > $150: max 5% per trade
]
MAX_POSITION_USD = 15               # Absolute max regardless of balance
MIN_BET_USD = 1.10                  # Minimum CLOB order value
MIN_SHARES = 5                      # Minimum shares required by CLOB

# =============================================================================
# TREND FILTER - FIX #5: Only trade when higher timeframes show clear trend
# =============================================================================
# Avoid whipsaw/choppy markets by requiring trend confirmation
TREND_FILTER_ENABLED = True         # Enable trend-based filtering
MIN_TREND_SCORE = 0.25              # Minimum |trend_score| to trade (0-1 scale)
REQUIRE_MAJOR_ALIGNMENT = False     # Require Daily+Weekly alignment (stricter)
CHOPPY_MARKET_THRESHOLD = 0.15      # Below this = choppy, skip trading
# When enabled, bot will:
# - Only trade Up when trend_score > MIN_TREND_SCORE
# - Only trade Down when trend_score < -MIN_TREND_SCORE
# - Skip trading entirely when |trend_score| < CHOPPY_MARKET_THRESHOLD

# =============================================================================
# CORRELATION PROTECTION - FIX #2: Limit same-direction exposure
# =============================================================================
MAX_SAME_DIRECTION_POSITIONS = 4    # Allow 1 bet per crypto (BTC, ETH, SOL, XRP)
MAX_TOTAL_POSITIONS = 4             # Max 4 positions total (1 per crypto)
MAX_DIRECTIONAL_EXPOSURE_PCT = 0.08 # Max 8% exposure in one direction

# =============================================================================
# STOP-LOSS - FIX #3: DISABLED for binary markets
# =============================================================================
# NOTE: Traditional stop-loss is WRONG for binary outcome markets!
# Mid-epoch prices are probability estimates, NOT value.
# Final payout is always $1 (correct) or $0 (wrong).
# A stop-loss would cut winning trades based on temporary price movements.
STOP_LOSS_ENABLED = False          # DISABLED - binary markets don't work this way
STOP_LOSS_PCT = 0.20               # Only used if manually re-enabled
STOP_LOSS_CHECK_INTERVAL = 30      # v12 FIX: Was undefined - check every 30 seconds
STOP_LOSS_MIN_TIME = 120           # v12 FIX: Was undefined - don't stop-loss in first 2 mins

# =============================================================================
# RECOVERY MODE - FIX #4: Conservative after losses (adjusted for small balances)
# =============================================================================
# Use BOTH percentage AND absolute thresholds - whichever is MORE lenient
# Adjusted to be reasonable for ALL balance sizes
RECOVERY_TRIGGER_PCT = 0.25        # Enter recovery at 25% daily loss
RECOVERY_TRIGGER_USD = 5.0         # OR $5 loss (reasonable for small balances)
DEFENSIVE_TRIGGER_PCT = 0.15       # Enter defensive at 15% daily loss
DEFENSIVE_TRIGGER_USD = 3.0        # OR $3 loss
CONSERVATIVE_TRIGGER_PCT = 0.08    # Enter conservative at 8% daily loss
CONSERVATIVE_TRIGGER_USD = 2.0     # OR $2 loss

# Recovery mode bet sizes - less aggressive reduction to allow recovery
RECOVERY_BET_MULTIPLIER = 0.50     # 50% of normal (was 10% - too aggressive)
DEFENSIVE_BET_MULTIPLIER = 0.65    # 65% of normal (was 25%)
CONSERVATIVE_BET_MULTIPLIER = 0.80 # 80% of normal (was 50%)

# =============================================================================
# OTHER RISK MANAGEMENT
# =============================================================================
DAILY_LOSS_LIMIT_USD = 30          # Reduced from $100 - hard stop
DAILY_LOSS_LIMIT_PCT = 0.20        # 20% daily loss = halt
MAX_DRAWDOWN_PCT = 0.30            # Kill switch at 30% drawdown
KILL_SWITCH_FILE = "./HALT"

# Signal Thresholds - FURTHER STRENGTHENED in v12
MIN_EXCHANGES_AGREE = 2
CONFLUENCE_THRESHOLD = 0.0025       # 0.25% move (slightly relaxed from 0.30% for more signals)
MIN_SIGNAL_STRENGTH = 0.65          # v12.1: Lowered to catch contrarian opportunities

# RSI Configuration
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
RSI_HISTORY_SIZE = 50

# Strategy: Early Momentum - FURTHER TIGHTENED in v12
EARLY_MIN_ENTRY = 0.12              # v12: Slightly up from 0.10 - avoid extreme illiquidity
EARLY_MAX_ENTRY = 0.30              # v12: Down from 0.40 - fee economics require this
EARLY_MIN_TIME = 15                 # v12: Back to 15s - let prices stabilize slightly
EARLY_MAX_TIME = 300

# Strategy: Epoch Boundary (NEW in v11) - Trade when prices are stale at epoch start
EPOCH_BOUNDARY_ENABLED = True
EPOCH_BOUNDARY_MAX_TIME = 45        # v12: Reduced to 45s - prices stabilize faster
EPOCH_BOUNDARY_TARGET_PRICE = 0.50  # Prices often start near 50/50
EPOCH_BOUNDARY_MAX_ENTRY = 0.45     # v12: Reduced from 0.52 - still apply fee discipline

# Strategy: Contrarian Fade (v12 TIGHTENED) - Only take CHEAP entries
# Last night's winners were $0.06-0.13 entries. Skip the $0.30+ entries that lost.
CONTRARIAN_ENABLED = True
CONTRARIAN_PRICE_THRESHOLD = 0.70   # When one side is >70%, consider fading
CONTRARIAN_RSI_EXTREME = 60         # v12.1: Lower to catch current extremes
CONTRARIAN_MAX_ENTRY = 0.20         # v12.1: Raised to catch $0.06-0.08 opportunities!
CONTRARIAN_MIN_TIME = 30            # v12.1: Start very early to catch cheap prices
CONTRARIAN_MAX_TIME = 700           # Extended to catch more opportunities

# Strategy: 12-Minute Bot Exit Detection (NEW in v11)
BOT_EXIT_DETECTION_ENABLED = True
BOT_EXIT_TIME_START = 700           # 11:40 into epoch
BOT_EXIT_TIME_END = 780             # 13:00 into epoch
BOT_EXIT_PRICE_DROP = 0.08          # 8% price drop = bot exit cascade
BOT_EXIT_WINDOW = 45                # Must happen within 45 seconds

# Strategy: Late Confirmation
LATE_MIN_ENTRY = 0.85               # Buy when probability is 85%+
LATE_MAX_ENTRY = 0.95               # Cap at 95% (above this, profit too small)
LATE_MIN_TIME = 720                 # Start looking at 12 minutes (3 mins left)
LATE_STABILITY_PERIOD = 180         # Direction must be stable for 3 minutes

# =============================================================================
# LATE CONFIRMATION ONLY MODE (NEW in v12)
# =============================================================================
# When enabled, bot ONLY trades late confirmation - no early momentum
# Lower risk, lower reward, but much higher win rate (~90-95%)
# Good for rebuilding small balances with consistent wins
LATE_ONLY_MODE = False              # v12: Disabled - use all strategies including cheap contrarian

# Late-only specific settings
LATE_ONLY_MIN_ENTRY = 0.85          # Minimum probability to enter
LATE_ONLY_MAX_ENTRY = 0.95          # Maximum (above this, profit too small for fees)
LATE_ONLY_MIN_TIME = 720            # Start at 12 minutes (3 mins before resolution)
LATE_ONLY_MAX_TIME = 870            # Stop at 14:30 (30 seconds before resolution)
LATE_ONLY_STABILITY_SECONDS = 180   # Price must be stable in this direction for 3 mins
LATE_ONLY_MIN_PRICE_DIFF = 0.60     # One side must be >60% for at least stability period
LATE_ONLY_POSITION_SIZE_PCT = 0.20  # Can risk more (20%) since win rate is high

# Strategy: Mandatory Fallback Bet - DISABLED in v12
# The hacker team found that forced bets were causing losses
FALLBACK_BET_ENABLED = False        # v12: DISABLED - no forced bets
FALLBACK_BET_TIME = 720
FALLBACK_BET_SIZE = 1.10
FALLBACK_MAX_ENTRY = 0.35           # v12: Reduced further if ever re-enabled

# Scan Cycle - REVERTED in v12
SCAN_INTERVAL = 2.0                 # v12: Back to 2s - faster wasn't helping, just API load

# Annealing - ULTRA FAST RESPONSE
LOSS_TRIGGER = 1                    # React after SINGLE loss (was 2)
WIN_TRIGGER = 3
ADJUSTMENT_COOLDOWN = 180           # Reduced from 300

# Polygon/Redemption
RPC_URL = "https://polygon-rpc.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

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

# Cryptos to track
CRYPTOS = ["btc", "eth", "sol", "xrp"]

EXCHANGE_SYMBOLS = {
    "btc": {"binance": "BTCUSDT", "kraken": "XBTUSD", "coinbase": "BTC-USD"},
    "eth": {"binance": "ETHUSDT", "kraken": "ETHUSD", "coinbase": "ETH-USD"},
    "sol": {"binance": "SOLUSDT", "kraken": "SOLUSD", "coinbase": "SOL-USD"},
    "xrp": {"binance": "XRPUSDT", "kraken": "XRPUSD", "coinbase": "XRP-USD"},
}

# State directory
STATE_DIR = "./v12_state"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TradingState:
    """Persistent trading state."""
    day_start_balance: float = 0.0
    current_balance: float = 0.0
    peak_balance: float = 0.0
    daily_pnl: float = 0.0
    mode: str = "normal"  # aggressive, normal, conservative, defensive, recovery, halted
    halt_reason: str = ""
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    total_trades: int = 0
    total_wins: int = 0
    last_adjustment: float = 0.0
    last_trade_time: float = 0.0
    # v10 additions
    loss_streak_cost: float = 0.0   # Total cost of current loss streak
    daily_loss_count: int = 0       # Number of losses today


@dataclass
class TradeRecord:
    """Record of a single trade."""
    timestamp: float
    crypto: str
    direction: str
    strategy: str
    entry_price: float
    shares: float
    cost: float
    signal_strength: float
    rsi: float
    confluence_count: int
    balance_before: float
    outcome: Optional[str] = None
    payout: Optional[float] = None


@dataclass
class Position:
    """Open position with stop-loss tracking."""
    crypto: str
    direction: str
    epoch: int
    shares: float
    entry_price: float
    cost: float
    token_id: str              # Needed for stop-loss exit
    open_time: float = 0.0     # When position was opened
    stop_loss_price: float = 0.0  # Price at which to exit


# =============================================================================
# RSI CALCULATOR (unchanged from v9)
# =============================================================================

class RSICalculator:
    """Calculate RSI for each crypto."""

    def __init__(self, period: int = RSI_PERIOD):
        self.period = period
        self.price_history: Dict[str, deque] = {
            crypto: deque(maxlen=RSI_HISTORY_SIZE) for crypto in CRYPTOS
        }
        self.rsi_values: Dict[str, float] = {crypto: 50.0 for crypto in CRYPTOS}

    def add_price(self, crypto: str, price: float, timestamp: float):
        self.price_history[crypto].append((timestamp, price))
        self._calculate_rsi(crypto)

    def _calculate_rsi(self, crypto: str):
        prices = [p[1] for p in self.price_history[crypto]]
        if len(prices) < self.period + 1:
            return

        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]

        recent_gains = gains[-self.period:]
        recent_losses = losses[-self.period:]

        avg_gain = sum(recent_gains) / self.period
        avg_loss = sum(recent_losses) / self.period

        if avg_loss == 0:
            self.rsi_values[crypto] = 100.0
        else:
            rs = avg_gain / avg_loss
            self.rsi_values[crypto] = 100 - (100 / (1 + rs))

    def get_rsi(self, crypto: str) -> float:
        return self.rsi_values.get(crypto, 50.0)

    def is_overbought(self, crypto: str) -> bool:
        return self.get_rsi(crypto) > RSI_OVERBOUGHT

    def is_oversold(self, crypto: str) -> bool:
        return self.get_rsi(crypto) < RSI_OVERSOLD

    def get_rsi_signal(self, crypto: str, direction: str) -> Tuple[float, str]:
        rsi = self.get_rsi(crypto)
        if direction == "Up":
            if rsi > RSI_OVERBOUGHT:
                return 0.0, f"RSI {rsi:.0f} OVERBOUGHT"
            elif rsi > 60:
                return 0.5, f"RSI {rsi:.0f} elevated"
            elif rsi > 40:
                return 1.0, f"RSI {rsi:.0f} neutral"
            else:
                return 0.8, f"RSI {rsi:.0f} oversold"
        else:
            if rsi < RSI_OVERSOLD:
                return 0.0, f"RSI {rsi:.0f} OVERSOLD"
            elif rsi < 40:
                return 0.5, f"RSI {rsi:.0f} low"
            elif rsi < 60:
                return 1.0, f"RSI {rsi:.0f} neutral"
            else:
                return 0.8, f"RSI {rsi:.0f} overbought"


# =============================================================================
# GUARDIAN - ENHANCED RISK MANAGEMENT
# =============================================================================

class Guardian:
    """Risk management with correlation protection and stop-loss."""

    def __init__(self, state: TradingState):
        self.state = state
        self.open_positions: List[Position] = []
        self.epoch_bets: Dict[str, Dict[int, int]] = {c: {} for c in CRYPTOS}
        self.last_stop_loss_check: float = 0

    def check_kill_switch(self) -> Tuple[bool, str]:
        """Check if trading should be halted."""
        if os.path.exists(KILL_SWITCH_FILE):
            return True, "Manual HALT file exists"

        if self.state.peak_balance > 0:
            cash_balance = get_usdc_balance()  # FIX: Use cash only, not position estimates
            drawdown = (self.state.peak_balance - cash_balance) / self.state.peak_balance
            if drawdown > MAX_DRAWDOWN_PCT:
                return True, f"Drawdown {drawdown*100:.1f}% exceeds {MAX_DRAWDOWN_PCT*100}% (peak ${self.state.peak_balance:.2f} -> ${cash_balance:.2f})"

        if self.state.consecutive_losses >= 5:
            return True, "5 consecutive losses - manual review needed"

        return False, ""

    def get_open_positions_value(self) -> float:
        """Get current value of all open positions."""
        try:
            resp = requests.get(
                "https://data-api.polymarket.com/positions",
                params={"user": EOA, "limit": 20},
                timeout=10
            )
            if resp.status_code != 200:
                return 0

            positions = resp.json()
            total_value = 0
            for pos in positions:
                size = float(pos.get('size', 0))
                cur_price = float(pos.get('curPrice', 0))
                total_value += size * cur_price
            return total_value
        except Exception as e:
            log.error(f"Error getting position value: {e}")
            return 0

    def get_portfolio_value(self) -> float:
        """Get total portfolio value (cash + positions)."""
        cash = get_usdc_balance()
        positions_value = self.get_open_positions_value()
        return cash + positions_value

    def check_daily_limit(self) -> Tuple[bool, str]:
        """Check if daily loss limit reached."""
        if self.state.day_start_balance <= 0:
            return True, ""

        portfolio_value = self.get_portfolio_value()
        daily_pnl = portfolio_value - self.state.day_start_balance

        if daily_pnl < -DAILY_LOSS_LIMIT_USD:
            return False, f"Daily loss ${-daily_pnl:.2f} exceeds ${DAILY_LOSS_LIMIT_USD}"

        if self.state.day_start_balance > 0:
            pct_loss = -daily_pnl / self.state.day_start_balance
            if pct_loss > DAILY_LOSS_LIMIT_PCT:
                return False, f"Daily loss {pct_loss*100:.1f}% exceeds {DAILY_LOSS_LIMIT_PCT*100}%"

        return True, ""

    def calculate_position_size(self, signal_strength: float) -> float:
        """
        FIX #1: Tiered percentage cap based on balance size.
        Smaller balances can risk more % to enable recovery.
        But NEVER the catastrophic 80%+ that killed us.
        """
        balance = self.state.current_balance

        # Get tier-appropriate max percentage
        max_pct = 0.05  # Default fallback
        for threshold, pct in POSITION_TIERS:
            if balance < threshold:
                max_pct = pct
                break

        # Calculate base size from balance
        max_from_balance = balance * max_pct

        # Apply mode multiplier (less aggressive now)
        mode_multiplier = self._get_mode_multiplier()
        base_size = max_from_balance * mode_multiplier

        # Adjust for consecutive losses (gentler reduction)
        if self.state.consecutive_losses >= 4:
            base_size *= 0.50  # 50% after 4 losses
        elif self.state.consecutive_losses >= 3:
            base_size *= 0.65  # 65% after 3 losses
        elif self.state.consecutive_losses >= 2:
            base_size *= 0.80  # 80% after 2 losses
        # No reduction after 1 loss - normal variance

        # Adjust for signal strength
        size = base_size * (0.7 + 0.3 * signal_strength)

        # Apply absolute maximum
        size = min(size, MAX_POSITION_USD)

        # If below minimum, check if we can afford minimum bet
        if size < MIN_BET_USD:
            # Allow minimum bet if it's within our tier limit
            if MIN_BET_USD <= (balance * max_pct):
                return MIN_BET_USD
            return 0  # Can't afford even minimum

        return size

    def _get_mode_multiplier(self) -> float:
        """Get bet multiplier based on current mode."""
        multipliers = {
            "aggressive": 1.0,
            "normal": 0.75,
            "conservative": CONSERVATIVE_BET_MULTIPLIER,
            "defensive": DEFENSIVE_BET_MULTIPLIER,
            "recovery": RECOVERY_BET_MULTIPLIER,
            "halted": 0.0
        }
        return multipliers.get(self.state.mode, 0.75)

    def check_correlation_limits(self, direction: str) -> Tuple[bool, str]:
        """
        FIX #2: Check correlation/directional exposure limits.
        """
        # Count positions by direction
        up_positions = [p for p in self.open_positions if p.direction == "Up"]
        down_positions = [p for p in self.open_positions if p.direction == "Down"]

        same_direction_count = len(up_positions) if direction == "Up" else len(down_positions)

        # Check max same direction
        if same_direction_count >= MAX_SAME_DIRECTION_POSITIONS:
            return False, f"Already have {same_direction_count} {direction} position(s)"

        # Check total positions
        if len(self.open_positions) >= MAX_TOTAL_POSITIONS:
            return False, f"Already have {len(self.open_positions)} total positions"

        # Check directional exposure
        direction_exposure = sum(p.cost for p in self.open_positions if p.direction == direction)
        balance = self.state.current_balance
        if balance > 0 and (direction_exposure / balance) >= MAX_DIRECTIONAL_EXPOSURE_PCT:
            return False, f"{direction} exposure {direction_exposure/balance*100:.1f}% exceeds {MAX_DIRECTIONAL_EXPOSURE_PCT*100}%"

        return True, ""

    def can_open_position(self, crypto: str, epoch: int, direction: str) -> Tuple[bool, str]:
        """Check if we can open a new position (includes correlation check)."""
        # Correlation check first
        can_corr, reason = self.check_correlation_limits(direction)
        if not can_corr:
            return False, reason

        # Check per crypto (only 1 per crypto)
        crypto_positions = [p for p in self.open_positions if p.crypto == crypto]
        if len(crypto_positions) >= 1:
            return False, f"Already have position in {crypto}"

        # Check per epoch (only 1 bet per crypto per epoch)
        if self.epoch_bets.get(crypto, {}).get(epoch, 0) >= 1:
            return False, f"Already bet this epoch for {crypto}"

        return True, ""

    def record_position(self, position: Position):
        """Record a new position."""
        self.open_positions.append(position)
        if position.crypto not in self.epoch_bets:
            self.epoch_bets[position.crypto] = {}
        self.epoch_bets[position.crypto][position.epoch] = \
            self.epoch_bets[position.crypto].get(position.epoch, 0) + 1

    def clear_position(self, crypto: str, epoch: int):
        """Clear resolved position."""
        self.open_positions = [
            p for p in self.open_positions
            if not (p.crypto == crypto and p.epoch == epoch)
        ]


# =============================================================================
# STOP-LOSS MANAGER - FIX #3
# =============================================================================

class StopLossManager:
    """Monitor positions and exit via CLOB SELL if stop-loss triggered."""

    def __init__(self, clob_client: ClobClient, guardian: Guardian):
        self.client = clob_client
        self.guardian = guardian
        self.last_check = 0

    def check_stop_losses(self) -> List[str]:
        """Check all positions for stop-loss triggers. Returns list of exited positions."""
        now = time.time()

        if now - self.last_check < STOP_LOSS_CHECK_INTERVAL:
            return []

        self.last_check = now
        exited = []

        for position in self.guardian.open_positions:
            # Don't stop-loss in first 2 minutes (volatility)
            if now - position.open_time < STOP_LOSS_MIN_TIME:
                continue

            # Get current price for this token
            current_price = self._get_current_price(position.token_id)
            if current_price is None:
                continue

            # Calculate unrealized P&L
            entry_value = position.cost
            current_value = position.shares * current_price
            pnl_pct = (current_value - entry_value) / entry_value

            # Check stop-loss
            if pnl_pct <= -STOP_LOSS_PCT:
                log.warning(f"STOP-LOSS TRIGGERED for {position.crypto} {position.direction}")
                log.warning(f"  Entry: ${position.entry_price:.2f}, Current: ${current_price:.2f}")
                log.warning(f"  Loss: {pnl_pct*100:.1f}%")

                # Try to exit position
                if self._exit_position(position, current_price):
                    exited.append(f"{position.crypto}_{position.direction}")
                    log.info(f"  EXIT SUCCESSFUL - saved remaining ${current_value:.2f}")

        return exited

    def _get_current_price(self, token_id: str) -> Optional[float]:
        """Get current bid price for a token (what we'd sell at)."""
        try:
            resp = requests.get(
                f"https://clob.polymarket.com/book?token_id={token_id}",
                timeout=3
            )
            book = resp.json()
            bids = book.get("bids", [])
            # Best bid is highest price (first in sorted list)
            return float(bids[0]["price"]) if bids else None
        except:
            return None

    def _exit_position(self, position: Position, price: float) -> bool:
        """Exit position by selling shares."""
        try:
            # Place market sell order (use best bid price)
            order_args = OrderArgs(
                token_id=position.token_id,
                price=price,
                size=position.shares,
                side=SELL,
            )
            result = self.client.create_and_post_order(order_args)

            if result and result.get("success"):
                # Remove from guardian tracking
                self.guardian.open_positions = [
                    p for p in self.guardian.open_positions
                    if not (p.crypto == position.crypto and p.epoch == position.epoch)
                ]
                return True
            return False
        except Exception as e:
            log.error(f"Stop-loss exit failed: {e}")
            return False


# =============================================================================
# RECOVERY MODE CONTROLLER - FIX #4
# =============================================================================

class RecoveryController:
    """Manage trading mode transitions based on performance."""

    MODES = ["aggressive", "normal", "conservative", "defensive", "recovery", "halted"]

    def __init__(self, state: TradingState):
        self.state = state

    def get_mode_params(self) -> Dict:
        """Get current mode parameters."""
        mode = self.state.mode

        # v12: EVEN LOWER max_early_entry (fee economics require max $0.30)
        params = {
            "aggressive": {
                "max_early_entry": 0.32,     # v12: Down from 0.42
                "min_signal_strength": 0.68,
                "bet_multiplier": 1.0,
                "max_positions": 2
            },
            "normal": {
                "max_early_entry": 0.30,     # v12: Down from 0.40 - fee sweet spot
                "min_signal_strength": 0.72,
                "bet_multiplier": 0.75,
                "max_positions": 2
            },
            "conservative": {
                "max_early_entry": 0.28,     # v12: Down from 0.38
                "min_signal_strength": 0.75,
                "bet_multiplier": CONSERVATIVE_BET_MULTIPLIER,
                "max_positions": 1
            },
            "defensive": {
                "max_early_entry": 0.25,     # v12: Down from 0.35 - very cheap only
                "min_signal_strength": 0.78,
                "bet_multiplier": DEFENSIVE_BET_MULTIPLIER,
                "max_positions": 1
            },
            "recovery": {
                "max_early_entry": 0.22,     # v12: Down from 0.30 - extremely cheap only
                "min_signal_strength": 0.82,
                "bet_multiplier": RECOVERY_BET_MULTIPLIER,
                "max_positions": 1
            },
            "halted": {
                "max_early_entry": 0.0,
                "min_signal_strength": 1.0,
                "bet_multiplier": 0.0,
                "max_positions": 0
            }
        }

        return params.get(mode, params["normal"])

    def update_mode_from_performance(self):
        """
        FIX #4: Automatically transition modes based on daily performance.
        Uses BOTH percentage AND absolute thresholds - whichever is MORE lenient.
        This prevents mode downgrades from tiny losses on small balances.
        """
        if self.state.day_start_balance <= 0:
            return

        # Calculate daily loss
        portfolio_value = get_usdc_balance()  # Simplified - should use full portfolio
        daily_pnl = portfolio_value - self.state.day_start_balance
        loss_usd = -daily_pnl if daily_pnl < 0 else 0
        loss_pct = loss_usd / self.state.day_start_balance if self.state.day_start_balance > 0 else 0

        old_mode = self.state.mode

        # Use whichever threshold is MORE lenient (higher)
        # This prevents aggressive mode changes on small balances
        recovery_threshold = max(RECOVERY_TRIGGER_PCT, RECOVERY_TRIGGER_USD / self.state.day_start_balance)
        defensive_threshold = max(DEFENSIVE_TRIGGER_PCT, DEFENSIVE_TRIGGER_USD / self.state.day_start_balance)
        conservative_threshold = max(CONSERVATIVE_TRIGGER_PCT, CONSERVATIVE_TRIGGER_USD / self.state.day_start_balance)

        # Determine mode based on loss
        if loss_pct >= recovery_threshold:
            new_mode = "recovery"
        elif loss_pct >= defensive_threshold:
            new_mode = "defensive"
        elif loss_pct >= conservative_threshold:
            new_mode = "conservative"
        else:
            # Can upgrade mode based on wins
            new_mode = self._check_upgrade()

        if new_mode != old_mode:
            log.info(f"MODE TRANSITION: {old_mode} -> {new_mode} (loss: ${loss_usd:.2f} / {loss_pct*100:.1f}%)")
            self.state.mode = new_mode

    def _check_upgrade(self) -> str:
        """Check if we can upgrade mode based on wins."""
        if self.state.consecutive_wins >= WIN_TRIGGER:
            mode_idx = self.MODES.index(self.state.mode)
            if mode_idx > 1:  # Don't go above normal without manual override
                return self.MODES[mode_idx - 1]
        return self.state.mode

    def record_outcome(self, won: bool, cost: float):
        """Record trade outcome and update tracking."""
        if won:
            self.state.consecutive_wins += 1
            self.state.consecutive_losses = 0
            self.state.total_wins += 1
            self.state.loss_streak_cost = 0
        else:
            self.state.consecutive_losses += 1
            self.state.consecutive_wins = 0
            self.state.daily_loss_count += 1
            self.state.loss_streak_cost += cost

        self.state.total_trades += 1

        # Check for immediate mode downgrade after loss
        if not won and self.state.consecutive_losses >= LOSS_TRIGGER:
            self._downgrade_mode()

    def _downgrade_mode(self):
        """Downgrade mode after losses."""
        now = time.time()
        if now - self.state.last_adjustment < ADJUSTMENT_COOLDOWN:
            return

        mode_idx = self.MODES.index(self.state.mode)
        if mode_idx < len(self.MODES) - 1:
            new_mode = self.MODES[mode_idx + 1]
            log.info(f"LOSS DOWNGRADE: {self.state.mode} -> {new_mode}")
            self.state.mode = new_mode
            self.state.last_adjustment = now


# =============================================================================
# SIGNAL ANALYZER (unchanged from v9)
# =============================================================================

class SignalAnalyzer:
    """Analyze signals and calculate combined strength."""

    def __init__(self, rsi_calculator: RSICalculator):
        self.rsi = rsi_calculator

    def calculate_signal_strength(
        self,
        crypto: str,
        direction: str,
        exchange_signals: Dict[str, Tuple[str, float]],
        time_in_epoch: int,
        entry_price: float
    ) -> Tuple[float, Dict]:
        """Calculate combined signal strength."""
        breakdown = {}

        # 1. Exchange Agreement (35%)
        agreeing = sum(1 for ex, (d, c) in exchange_signals.items() if d == direction)
        total_exchanges = len(exchange_signals)

        if agreeing >= 3:
            exchange_score = 1.0
        elif agreeing >= 2:
            exchange_score = 0.7
        else:
            exchange_score = 0.0

        breakdown['exchange'] = {'score': exchange_score, 'agreeing': agreeing, 'total': total_exchanges}

        # 2. Move Magnitude (25%)
        avg_change = sum(abs(c) for _, (_, c) in exchange_signals.items()) / max(1, len(exchange_signals))

        if avg_change > 0.005:
            magnitude_score = 1.0
        elif avg_change > 0.003:
            magnitude_score = 0.8
        elif avg_change > 0.0015:
            magnitude_score = 0.5
        else:
            magnitude_score = 0.2

        breakdown['magnitude'] = {'score': magnitude_score, 'avg_change': avg_change * 100}

        # 3. RSI Confirmation (25%)
        rsi_score, rsi_desc = self.rsi.get_rsi_signal(crypto, direction)
        breakdown['rsi'] = {'score': rsi_score, 'value': self.rsi.get_rsi(crypto), 'description': rsi_desc}

        # 4. Entry Price Value (15%)
        if entry_price < 0.35:
            price_score = 1.0
        elif entry_price < 0.45:
            price_score = 0.8
        elif entry_price < 0.55:
            price_score = 0.5
        else:
            price_score = 0.2

        breakdown['price'] = {'score': price_score, 'entry': entry_price}

        # Combined weighted score
        total_score = (
            exchange_score * 0.35 +
            magnitude_score * 0.25 +
            rsi_score * 0.25 +
            price_score * 0.15
        )

        breakdown['total'] = total_score
        return total_score, breakdown


# =============================================================================
# PRICE FEED (unchanged from v9)
# =============================================================================

class MultiExchangePriceFeed:
    """Fetches prices from multiple exchanges."""

    def __init__(self, rsi_calculator: RSICalculator):
        self.executor = ThreadPoolExecutor(max_workers=12)
        self.rsi = rsi_calculator
        self.epoch_starts: Dict[str, Dict[int, Dict[str, float]]] = {}
        self.current_prices: Dict[str, Dict[str, float]] = {}
        self.price_stability: Dict[str, List[Tuple[float, float]]] = {c: [] for c in CRYPTOS}

    def get_binance_price(self, symbol: str) -> Optional[float]:
        try:
            resp = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=2)
            return float(resp.json()["price"])
        except:
            return None

    def get_kraken_price(self, symbol: str) -> Optional[float]:
        try:
            resp = requests.get(f"https://api.kraken.com/0/public/Ticker?pair={symbol}", timeout=2)
            data = resp.json()
            if data.get("error"):
                return None
            for key, val in data.get("result", {}).items():
                return float(val["c"][0])
            return None
        except:
            return None

    def get_coinbase_price(self, symbol: str) -> Optional[float]:
        try:
            resp = requests.get(f"https://api.coinbase.com/v2/prices/{symbol}/spot", timeout=2)
            return float(resp.json()["data"]["amount"])
        except:
            return None

    def update_prices(self, crypto: str):
        """Update prices from all exchanges."""
        symbols = EXCHANGE_SYMBOLS.get(crypto, {})

        futures = {
            "binance": self.executor.submit(self.get_binance_price, symbols.get("binance", "")),
            "kraken": self.executor.submit(self.get_kraken_price, symbols.get("kraken", "")),
            "coinbase": self.executor.submit(self.get_coinbase_price, symbols.get("coinbase", "")),
        }

        prices = {}
        for exchange, future in futures.items():
            try:
                price = future.result(timeout=3)
                if price:
                    prices[exchange] = price
            except:
                pass

        if not prices:
            return

        self.current_prices[crypto] = prices

        avg_price = sum(prices.values()) / len(prices)
        self.rsi.add_price(crypto, avg_price, time.time())

        now = time.time()
        self.price_stability[crypto].append((now, avg_price))
        cutoff = now - 180
        self.price_stability[crypto] = [(t, p) for t, p in self.price_stability[crypto] if t > cutoff]

        epoch = self.get_current_epoch()
        if crypto not in self.epoch_starts:
            self.epoch_starts[crypto] = {}

        if epoch not in self.epoch_starts[crypto]:
            self.epoch_starts[crypto][epoch] = prices.copy()
            price_str = ", ".join([f"{ex}=${p:,.2f}" for ex, p in prices.items()])
            log.info(f"[{crypto.upper()}] New epoch: {price_str}")

    def get_current_epoch(self) -> int:
        return (int(time.time()) // 900) * 900

    def get_confluence_signal(self, crypto: str) -> Tuple[Optional[str], int, float, Dict]:
        """Get confluence signal from exchanges."""
        epoch = self.get_current_epoch()

        if crypto not in self.epoch_starts or epoch not in self.epoch_starts[crypto]:
            return None, 0, 0, {}

        starts = self.epoch_starts[crypto][epoch]
        currents = self.current_prices.get(crypto, {})

        signals = {}
        up_count = 0
        down_count = 0
        total_change = 0

        for exchange in starts:
            if exchange not in currents:
                continue

            start = starts[exchange]
            current = currents[exchange]
            change = (current - start) / start

            if change > CONFLUENCE_THRESHOLD:
                direction = "Up"
                up_count += 1
            elif change < -CONFLUENCE_THRESHOLD:
                direction = "Down"
                down_count += 1
            else:
                direction = "Flat"

            signals[exchange] = (direction, change)
            total_change += change

        if not signals:
            return None, 0, 0, {}

        avg_change = total_change / len(signals)

        if up_count >= MIN_EXCHANGES_AGREE:
            return "Up", up_count, avg_change, signals
        elif down_count >= MIN_EXCHANGES_AGREE:
            return "Down", down_count, avg_change, signals
        else:
            return None, max(up_count, down_count), avg_change, signals

    def is_direction_stable(self, crypto: str, direction: str, seconds: int = LATE_STABILITY_PERIOD) -> bool:
        history = self.price_stability.get(crypto, [])
        if len(history) < 2:
            return False

        now = time.time()
        cutoff = now - seconds
        recent = [(t, p) for t, p in history if t > cutoff]

        if len(recent) < 2:
            return False

        first_price = recent[0][1]
        last_price = recent[-1][1]
        change = (last_price - first_price) / first_price

        if direction == "Up":
            return change > 0.001
        else:
            return change < -0.001


# =============================================================================
# AUTO REDEEMER (unchanged from v9)
# =============================================================================

class AutoRedeemer:
    """Automatically redeem winning positions."""

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.account = Account.from_key(KEY)
        self.ctf = self.w3.eth.contract(address=CTF_ADDRESS, abi=CTF_ABI)
        self.last_epoch = (int(time.time()) // 900) * 900

    def get_redeemable_positions(self) -> List[Dict]:
        try:
            resp = requests.get(
                "https://data-api.polymarket.com/positions",
                params={"user": EOA, "redeemable": "true", "limit": 20},
                timeout=10
            )
            return resp.json() if resp.status_code == 200 else []
        except:
            return []

    def redeem_position(self, condition_id: str, nonce: int) -> bool:
        try:
            gas_price = int(self.w3.eth.gas_price * 1.5)

            txn = self.ctf.functions.redeemPositions(
                USDC_ADDRESS,
                bytes(32),
                bytes.fromhex(condition_id[2:]),
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
            return receipt.status == 1
        except Exception as e:
            log.error(f"Redemption error: {e}")
            return False

    def check_and_redeem(self) -> float:
        current_epoch = (int(time.time()) // 900) * 900

        if current_epoch == self.last_epoch:
            return 0

        time_since = int(time.time()) - current_epoch
        if time_since < 60:
            return 0

        self.last_epoch = current_epoch

        positions = self.get_redeemable_positions()
        if not positions:
            return 0

        log.info(f"Epoch ended - found {len(positions)} redeemable positions")

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        redeemed = 0
        total_value = 0

        for pos in positions:
            condition_id = pos.get('conditionId') or pos.get('condition_id')
            size = float(pos.get('size', 0))

            if self.redeem_position(condition_id, nonce):
                redeemed += 1
                total_value += size
                nonce += 1
            time.sleep(2)

        if redeemed > 0:
            log.info(f"Redeemed {redeemed} positions (~${total_value:.2f})")

        return total_value


# =============================================================================
# FUTURE WINDOW TRADING - NEW IN V12.1
# =============================================================================

class FutureWindowTrader:
    """Analyzes future 15-minute windows for trading opportunities."""

    def __init__(self, rsi_calculator: RSICalculator):
        self.rsi = rsi_calculator
        self.future_markets_cache = {}
        self.last_cache_update = 0
        self.cache_ttl = 30  # Refresh cache every 30 seconds

    def get_future_markets(self, crypto: str, num_windows: int = 3) -> List[Dict]:
        """Get next N future 15-minute windows."""
        now = time.time()

        # Check cache
        cache_key = f"{crypto}_{num_windows}"
        if cache_key in self.future_markets_cache:
            cached_time, cached_data = self.future_markets_cache[cache_key]
            if now - cached_time < self.cache_ttl:
                return cached_data

        current_epoch = (int(now) // 900) * 900
        future_markets = []

        for i in range(1, num_windows + 1):
            future_epoch = current_epoch + (900 * i)
            market = self._fetch_future_market(crypto, future_epoch)
            if market:
                future_markets.append(market)

        # Update cache
        self.future_markets_cache[cache_key] = (now, future_markets)
        return future_markets

    def _fetch_future_market(self, crypto: str, epoch: int) -> Optional[Dict]:
        """Fetch a specific future market."""
        slug = f"{crypto}-updown-15m-{epoch}"

        try:
            resp = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=3)
            if resp.status_code != 200 or not resp.json():
                return None

            event = resp.json()[0]
            markets = event.get("markets", [])
            if not markets:
                return None

            cid = markets[0].get("conditionId")
            clob = requests.get(f"https://clob.polymarket.com/markets/{cid}", timeout=3)
            if clob.status_code != 200:
                return None

            data = clob.json()
            if not data.get("accepting_orders"):
                return None

            # Get prices
            tokens = data.get("tokens", [])
            prices = {}
            for t in tokens:
                outcome = t.get("outcome")
                token_id = t.get("token_id")
                if not outcome or not token_id:
                    continue

                try:
                    book_resp = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=2)
                    book = book_resp.json()
                    asks = book.get("asks", [])
                    best_ask = float(asks[-1]["price"]) if asks else 0.99
                    prices[outcome] = {"token_id": token_id, "ask": best_ask}
                except:
                    prices[outcome] = {"token_id": token_id, "ask": 0.99}

            return {
                "title": event.get("title"),
                "condition_id": cid,
                "tokens": tokens,
                "epoch": epoch,
                "prices": prices,
                "minutes_away": (epoch - (int(time.time()) // 900) * 900) // 60
            }
        except:
            return None

    def detect_anomalies(self, crypto: str, current_direction: str,
                        current_strength: float) -> List[Dict]:
        """Detect pricing anomalies in future windows."""
        anomalies = []

        # Only check futures if current window has strong momentum
        if current_strength < 0.70:
            return anomalies

        future_markets = self.get_future_markets(crypto, num_windows=3)

        for market in future_markets:
            prices = market.get("prices", {})
            if not prices or "Up" not in prices or "Down" not in prices:
                continue

            up_price = prices["Up"]["ask"]
            down_price = prices["Down"]["ask"]

            # Anomaly 1: Future window hasn't caught up to current momentum
            # If current is strongly Up but future Up is still cheap
            if current_direction == "Up" and current_strength > 0.75:
                if up_price < 0.45:  # Future Up is underpriced
                    anomalies.append({
                        "type": "momentum_lag",
                        "market": market,
                        "direction": "Up",
                        "entry_price": up_price,
                        "expected_move": 0.60 - up_price,  # Expected to move to ~60%
                        "confidence": min(0.85, current_strength * 0.9),  # Decay confidence
                        "reason": f"Current {crypto} strongly Up ({current_strength:.0%}) but {market['minutes_away']}min future only ${up_price:.2f}"
                    })

            elif current_direction == "Down" and current_strength > 0.75:
                if down_price < 0.45:  # Future Down is underpriced
                    anomalies.append({
                        "type": "momentum_lag",
                        "market": market,
                        "direction": "Down",
                        "entry_price": down_price,
                        "expected_move": 0.60 - down_price,
                        "confidence": min(0.85, current_strength * 0.9),
                        "reason": f"Current {crypto} strongly Down ({current_strength:.0%}) but {market['minutes_away']}min future only ${down_price:.2f}"
                    })

            # Anomaly 2: Extreme mispricing (one side way too cheap)
            if up_price < 0.20 and down_price > 0.70:
                anomalies.append({
                    "type": "extreme_mispricing",
                    "market": market,
                    "direction": "Up",
                    "entry_price": up_price,
                    "expected_move": 0.50 - up_price,
                    "confidence": 0.70,
                    "reason": f"Extreme mispricing: Up only ${up_price:.2f} vs Down ${down_price:.2f}"
                })
            elif down_price < 0.20 and up_price > 0.70:
                anomalies.append({
                    "type": "extreme_mispricing",
                    "market": market,
                    "direction": "Down",
                    "entry_price": down_price,
                    "expected_move": 0.50 - down_price,
                    "confidence": 0.70,
                    "reason": f"Extreme mispricing: Down only ${down_price:.2f} vs Up ${up_price:.2f}"
                })

        return anomalies

    def should_adjust_current_trade(self, crypto: str, direction: str,
                                   entry_price: float) -> Tuple[bool, str]:
        """Check if future windows suggest adjusting current trade."""
        future_markets = self.get_future_markets(crypto, num_windows=2)

        if not future_markets:
            return False, ""

        # Check if future markets contradict current direction
        contradiction_count = 0
        avg_future_prob = 0

        for market in future_markets:
            prices = market.get("prices", {})
            if not prices:
                continue

            future_prob = prices.get(direction, {}).get("ask", 0.50)
            avg_future_prob += future_prob

            # If future market strongly contradicts (opposite > 65%)
            opposite = "Down" if direction == "Up" else "Up"
            opposite_prob = prices.get(opposite, {}).get("ask", 0.50)

            if opposite_prob > 0.65:
                contradiction_count += 1

        if future_markets:
            avg_future_prob /= len(future_markets)

        # Warn if multiple future windows contradict
        if contradiction_count >= 2:
            return True, f"WARNING: {contradiction_count} future windows favor opposite direction"

        # Boost confidence if futures align
        if avg_future_prob > 0.60 and entry_price < 0.40:
            return True, f"BOOST: Future windows align at {avg_future_prob:.0%}, good entry at ${entry_price:.2f}"

        return False, ""


# =============================================================================
# MARKET API (unchanged from v9)
# =============================================================================

def get_clob_client() -> ClobClient:
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=KEY,
        signature_type=0,
        funder=EOA,
    )
    creds = client.derive_api_key()
    return ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=KEY,
        signature_type=0,
        funder=EOA,
        creds=creds,
    )


def get_current_market(crypto: str) -> Optional[Dict]:
    epoch = (int(time.time()) // 900) * 900
    slug = f"{crypto}-updown-15m-{epoch}"

    try:
        resp = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5)
        if resp.status_code != 200 or not resp.json():
            return None

        event = resp.json()[0]
        markets = event.get("markets", [])
        if not markets:
            return None

        cid = markets[0].get("conditionId")
        clob = requests.get(f"https://clob.polymarket.com/markets/{cid}", timeout=5)
        if clob.status_code != 200:
            return None

        data = clob.json()
        if not data.get("accepting_orders"):
            return None

        return {
            "title": event.get("title"),
            "condition_id": cid,
            "tokens": data.get("tokens", []),
            "epoch": epoch,
        }
    except:
        return None


def get_market_prices(tokens: List[Dict]) -> Dict[str, Dict]:
    prices = {}

    for t in tokens:
        outcome = t.get("outcome")
        token_id = t.get("token_id")
        if not outcome or not token_id:
            continue

        try:
            resp = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=3)
            book = resp.json()
            asks = book.get("asks", [])
            best_ask = float(asks[-1]["price"]) if asks else 0.99
            prices[outcome] = {"token_id": token_id, "ask": best_ask}
        except:
            prices[outcome] = {"token_id": token_id, "ask": 0.99}

    return prices


def place_order(client: ClobClient, token_id: str, size: float, price: float) -> Optional[Dict]:
    try:
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=BUY,
        )
        return client.create_and_post_order(order_args)
    except Exception as e:
        log.error(f"Order error: {e}")
        return None


# =============================================================================
# STATE PERSISTENCE
# =============================================================================

def load_state() -> TradingState:
    os.makedirs(STATE_DIR, exist_ok=True)
    state_file = os.path.join(STATE_DIR, "trading_state.json")

    try:
        with open(state_file, 'r') as f:
            data = json.load(f)
            return TradingState(**data)
    except:
        return TradingState()


def save_state(state: TradingState):
    os.makedirs(STATE_DIR, exist_ok=True)
    state_file = os.path.join(STATE_DIR, "trading_state.json")

    with open(state_file, 'w') as f:
        json.dump(asdict(state), f, indent=2)


def get_usdc_balance() -> float:
    try:
        resp = requests.post(RPC_URL, json={
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{
                'to': USDC_ADDRESS,
                'data': f'0x70a08231000000000000000000000000{EOA[2:]}'
            }, 'latest'],
            'id': 1
        }, timeout=5)
        balance_hex = resp.json().get('result', '0x0')
        return int(balance_hex, 16) / 1e6
    except:
        return 0


# =============================================================================
# MAIN BOT
# =============================================================================

def run_bot():
    """Main bot loop with v12.1 Future Window enhancements."""
    log.info("=" * 60)
    log.info("MOMENTUM BOT v12.1 - FUTURE WINDOW ENHANCED")
    log.info("=" * 60)
    log.info("v12 Core Improvements:")
    log.info("  • Lower entry: Max $0.30 (fee economics)")
    log.info("  • Stronger signals: 0.72 min strength")
    log.info("  • Fixed contrarian: True fade logic")
    log.info("  • Fallback bets: DISABLED")
    log.info("")
    log.info("v12.1 Future Window Trading:")
    log.info("  • Looks ahead 2-3 windows for anomalies")
    log.info("  • Trades momentum lag opportunities")
    log.info("  • Warns on future contradictions")
    log.info("  • Boosts confidence when futures align")
    log.info("=" * 60)

    # Load state
    state = load_state()

    # Initialize balance tracking
    balance = get_usdc_balance()
    state.current_balance = balance

    # Reset daily tracking at start or new day
    now = datetime.now(timezone.utc)
    if state.day_start_balance == 0 or now.hour == 0:
        state.day_start_balance = balance
        state.daily_pnl = 0
        state.daily_loss_count = 0
        # v12 FIX: Reset peak_balance on new day to prevent false drawdown halts
        state.peak_balance = balance
        log.info(f"New day detected - reset peak_balance to ${balance:.2f}")
    else:
        # Only update peak during the day
        state.peak_balance = max(state.peak_balance, balance)

    log.info(f"Balance: ${balance:.2f}")
    log.info(f"Mode: {state.mode}")
    log.info(f"Daily P&L: ${state.daily_pnl:.2f}")
    log.info("=" * 60)

    # Initialize components
    rsi_calc = RSICalculator()
    price_feed = MultiExchangePriceFeed(rsi_calc)
    signal_analyzer = SignalAnalyzer(rsi_calc)
    guardian = Guardian(state)
    controller = RecoveryController(state)
    redeemer = AutoRedeemer()
    future_trader = FutureWindowTrader(rsi_calc)  # NEW: Future window trader

    # Initialize timeframe tracker
    tf_tracker = None
    if TIMEFRAME_TRACKING_ENABLED:
        try:
            tf_tracker = TimeframeTracker()
            log.info("Timeframe tracker initialized")
        except Exception as e:
            log.warning(f"Timeframe tracker init failed: {e}")

    try:
        client = get_clob_client()
        log.info("CLOB client initialized")
    except Exception as e:
        log.error(f"Failed to init CLOB client: {e}")
        return

    # Initialize stop-loss manager
    stop_loss_mgr = StopLossManager(client, guardian)

    # Track bets per epoch
    epoch_trades: Dict[str, Dict[int, List[str]]] = {c: {} for c in CRYPTOS}
    epoch_bet_placed: Dict[int, bool] = {}

    while True:
        try:
            # 1. GUARDIAN CHECKS
            halt, reason = guardian.check_kill_switch()
            if halt:
                log.warning(f"HALTED: {reason}")
                save_state(state)
                time.sleep(60)
                continue

            can_trade, reason = guardian.check_daily_limit()
            if not can_trade:
                log.warning(f"DAILY LIMIT: {reason}")
                state.mode = "halted"
                state.halt_reason = reason
                save_state(state)
                time.sleep(60)
                continue

            # 2. MODE CHECK AND UPDATE
            if state.mode == "halted":
                time.sleep(60)
                continue

            controller.update_mode_from_performance()
            mode_params = controller.get_mode_params()

            # 3. UPDATE BALANCE
            balance = get_usdc_balance()
            positions_value = guardian.get_open_positions_value()
            portfolio_value = balance + positions_value

            state.current_balance = balance
            state.peak_balance = max(state.peak_balance, balance)  # FIX: Track peak cash, not position estimates
            state.daily_pnl = portfolio_value - state.day_start_balance

            # 4. UPDATE PRICES
            for crypto in CRYPTOS:
                price_feed.update_prices(crypto)

            # 5. CHECK STOP-LOSSES (FIX #3) - DISABLED for binary markets
            # NOTE: Stop-loss is fundamentally wrong for binary outcome markets
            # Mid-epoch prices are probability estimates, not value
            # A stop-loss would cut winning trades based on temporary movements
            if STOP_LOSS_ENABLED:
                exited = stop_loss_mgr.check_stop_losses()
                if exited:
                    for pos_id in exited:
                        log.info(f"Stop-loss exit: {pos_id}")
                        controller.record_outcome(won=False, cost=0)
                    balance = get_usdc_balance()
                    state.current_balance = balance

            # 6. CHECK REDEMPTIONS
            redeemed = redeemer.check_and_redeem()
            if redeemed > 0:
                balance = get_usdc_balance()
                state.current_balance = balance

            # 7. EVALUATE EACH CRYPTO
            current_epoch = price_feed.get_current_epoch()
            time_in_epoch = int(time.time()) - current_epoch
            time_left = 900 - time_in_epoch

            for crypto in CRYPTOS:
                market = get_current_market(crypto)
                if not market:
                    continue

                if current_epoch not in epoch_trades.get(crypto, {}):
                    epoch_trades[crypto] = {current_epoch: []}
                    log.info(f"\n=== [{crypto.upper()}] {market['title']} ===")

                # =================================================================
                # LATE ONLY MODE - Simplified path, no confluence/trend needed
                # =================================================================
                if LATE_ONLY_MODE:
                    # In late-only mode, we skip everything until we're in the late window
                    if time_in_epoch < LATE_ONLY_MIN_TIME:
                        continue  # Too early, wait for late window

                    if time_in_epoch > LATE_ONLY_MAX_TIME:
                        continue  # Too late, risk of not filling before resolution

                    # Get prices directly - no confluence or trend filter needed
                    prices = get_market_prices(market.get("tokens", []))
                    if "Up" not in prices or "Down" not in prices:
                        continue

                    up_price = prices["Up"]["ask"]
                    down_price = prices["Down"]["ask"]

                    # Log current state in late window
                    if int(time.time()) % 10 < 2:  # Log every ~10 seconds
                        log.info(f"  [{crypto.upper()}] LATE WINDOW: Up=${up_price:.2f} Down=${down_price:.2f} (t={time_in_epoch}s)")

                    strategy = None
                    direction = None
                    entry_price = None
                    token_id = None

                    # Check Up side for high probability
                    if LATE_ONLY_MIN_ENTRY <= up_price <= LATE_ONLY_MAX_ENTRY:
                        if price_feed.is_direction_stable(crypto, "Up", LATE_ONLY_STABILITY_SECONDS):
                            direction = "Up"
                            entry_price = up_price
                            token_id = prices["Up"]["token_id"]
                            strategy = "late_only"
                            expected_profit = (1.0 - entry_price) / entry_price * 100
                            log.info(f"  [{crypto.upper()}] LATE ONLY SIGNAL: Up @ ${entry_price:.2f} ({time_left}s left, ~{expected_profit:.1f}% profit)")

                    # Check Down side for high probability
                    elif LATE_ONLY_MIN_ENTRY <= down_price <= LATE_ONLY_MAX_ENTRY:
                        if price_feed.is_direction_stable(crypto, "Down", LATE_ONLY_STABILITY_SECONDS):
                            direction = "Down"
                            entry_price = down_price
                            token_id = prices["Down"]["token_id"]
                            strategy = "late_only"
                            expected_profit = (1.0 - entry_price) / entry_price * 100
                            log.info(f"  [{crypto.upper()}] LATE ONLY SIGNAL: Down @ ${entry_price:.2f} ({time_left}s left, ~{expected_profit:.1f}% profit)")

                    if not strategy:
                        continue  # No late-only opportunity

                    # Set signal strength high for late confirmation
                    signal_strength = 0.90
                    rsi_value = rsi_calc.get_rsi(crypto)

                # =================================================================
                # NORMAL MODE - Full confluence/trend/strategy pipeline
                # =================================================================
                else:
                    # Initialize strategy
                    strategy = None

                    # FIRST: Check contrarian BEFORE confluence (contrarian doesn't need confluence)
                    # This is what worked last night - cheap entries when one side is expensive
                    prices = get_market_prices(market.get("tokens", []))
                    if "Up" not in prices or "Down" not in prices:
                        continue

                    up_price = prices["Up"]["ask"]
                    down_price = prices["Down"]["ask"]
                    rsi_value = rsi_calc.get_rsi(crypto)

                    # Check for contrarian opportunity (no confluence needed!)
                    if (CONTRARIAN_ENABLED and
                        CONTRARIAN_MIN_TIME <= time_in_epoch <= CONTRARIAN_MAX_TIME):

                        # If Up is expensive, check if Down is cheap enough to fade
                        if (up_price >= CONTRARIAN_PRICE_THRESHOLD and
                            down_price <= CONTRARIAN_MAX_ENTRY):
                            # RSI check is optional when price is extremely cheap
                            if down_price <= 0.10 or rsi_value > CONTRARIAN_RSI_EXTREME:
                                direction = "Down"
                                entry_price = down_price
                                token_id = prices["Down"]["token_id"]
                                signal_strength = 0.75 if down_price <= 0.05 else 0.70
                                strategy = "contrarian"
                                log.info(f"  [{crypto.upper()}] CONTRARIAN: Up @ ${up_price:.2f} expensive, buying Down @ ${entry_price:.2f} (RSI={rsi_value:.0f})")

                        # If Down is expensive, check if Up is cheap enough to fade
                        elif (down_price >= CONTRARIAN_PRICE_THRESHOLD and
                              up_price <= CONTRARIAN_MAX_ENTRY):
                            # RSI check is optional when price is extremely cheap
                            if up_price <= 0.10 or rsi_value < (100 - CONTRARIAN_RSI_EXTREME):
                                direction = "Up"
                                entry_price = up_price
                                token_id = prices["Up"]["token_id"]
                                signal_strength = 0.75 if up_price <= 0.05 else 0.70
                                strategy = "contrarian"
                                log.info(f"  [{crypto.upper()}] CONTRARIAN: Down @ ${down_price:.2f} expensive, buying Up @ ${entry_price:.2f} (RSI={rsi_value:.0f})")

                    # If contrarian found a trade, skip the rest
                    if strategy == "contrarian":
                        pass  # Continue to order placement
                    else:
                        # Need confluence for other strategies
                        direction, agree_count, avg_change, signals = price_feed.get_confluence_signal(crypto)
                        if not direction:
                            continue

                    # If contrarian found a trade, skip to order placement
                    if strategy == "contrarian":
                        pass  # Skip other strategy checks
                    else:
                        # For non-contrarian strategies, apply trend filter
                        if TREND_FILTER_ENABLED and tf_tracker:
                            try:
                                conditions = tf_tracker.get_market_conditions(crypto)
                                trend_score = conditions.trend_score

                                if abs(trend_score) < CHOPPY_MARKET_THRESHOLD:
                                    if int(time.time()) % 60 < 2:
                                        log.info(f"  [{crypto.upper()}] SKIP: Choppy market (trend={trend_score:.2f})")
                                    continue

                                if direction == "Up" and trend_score < MIN_TREND_SCORE:
                                    log.info(f"  [{crypto.upper()}] SKIP Up: Weak/negative trend ({trend_score:.2f})")
                                    continue
                                if direction == "Down" and trend_score > -MIN_TREND_SCORE:
                                    log.info(f"  [{crypto.upper()}] SKIP Down: Weak/positive trend ({trend_score:.2f})")
                                    continue

                            except Exception as e:
                                log.warning(f"Trend filter error for {crypto}: {e}")

                        # Set entry price for confluence-based direction
                        entry_price = prices[direction]["ask"]
                        token_id = prices[direction]["token_id"]

                        signal_strength, breakdown = signal_analyzer.calculate_signal_strength(
                            crypto, direction, signals, time_in_epoch, entry_price
                        )

                        # Check which strategy applies (non-contrarian)
                        strategy = None

                        # EPOCH BOUNDARY
                        if (EPOCH_BOUNDARY_ENABLED and
                            time_in_epoch <= EPOCH_BOUNDARY_MAX_TIME and
                            entry_price <= EPOCH_BOUNDARY_MAX_ENTRY and
                            signal_strength >= 0.50):
                            log.info(f"  [{crypto.upper()}] EPOCH BOUNDARY: {direction} @ ${entry_price:.2f} (t={time_in_epoch}s)")
                            strategy = "boundary"

                        # EARLY MOMENTUM
                        elif (EARLY_MIN_TIME <= time_in_epoch <= EARLY_MAX_TIME and
                            EARLY_MIN_ENTRY <= entry_price <= mode_params["max_early_entry"]):
                            if signal_strength >= mode_params["min_signal_strength"]:
                                if direction == "Up" and rsi_calc.is_overbought(crypto):
                                    continue
                                if direction == "Down" and rsi_calc.is_oversold(crypto):
                                    continue
                                strategy = "early"

                        # LATE CONFIRMATION
                        elif (time_in_epoch >= LATE_MIN_TIME and
                              LATE_MIN_ENTRY <= entry_price <= LATE_MAX_ENTRY):
                            if price_feed.is_direction_stable(crypto, direction):
                                strategy = "late"
                                signal_strength = 0.85

                        if not strategy:
                            continue

                if direction in epoch_trades[crypto].get(current_epoch, []):
                    continue

                # NEW: Check future windows for insights
                future_adjust, future_msg = future_trader.should_adjust_current_trade(
                    crypto, direction, entry_price
                )
                if future_adjust:
                    log.info(f"  [{crypto.upper()}] FUTURE INSIGHT: {future_msg}")
                    # If future windows contradict, skip this trade
                    if "WARNING" in future_msg:
                        log.info(f"  [{crypto.upper()}] SKIPPING due to future contradiction")
                        continue
                    # If future windows boost confidence, increase signal strength slightly
                    elif "BOOST" in future_msg:
                        signal_strength = min(1.0, signal_strength * 1.1)

                # FIX #2: Check correlation limits BEFORE guardian limits
                can_open, reason = guardian.can_open_position(crypto, current_epoch, direction)
                if not can_open:
                    log.info(f"  [{crypto.upper()}] BLOCKED: {reason}")
                    continue

                # FIX #1: Calculate position size with true cap
                size = guardian.calculate_position_size(signal_strength)

                if size < MIN_BET_USD:
                    log.info(f"  [{crypto.upper()}] SKIP: Size ${size:.2f} below minimum")
                    continue

                # Ensure minimum 5 shares (CLOB requirement)
                shares = size / entry_price
                if shares < MIN_SHARES:
                    min_cost = MIN_SHARES * entry_price
                    if min_cost > state.current_balance * 0.3:  # Don't exceed 30% for min shares
                        log.info(f"  [{crypto.upper()}] SKIP: Min {MIN_SHARES} shares = ${min_cost:.2f} too expensive")
                        continue
                    shares = MIN_SHARES
                    size = min_cost

                # Get trend info for logging
                trend_info = ""
                if TREND_FILTER_ENABLED and tf_tracker:
                    try:
                        conditions = tf_tracker.get_market_conditions(crypto)
                        trend_info = f" | Trend: {conditions.trend_score:+.2f}"
                        if conditions.major_timeframes_aligned:
                            trend_info += " (D+W aligned)"
                    except:
                        pass

                log.info(f"\n*** [{crypto.upper()}] {strategy.upper()} SIGNAL: {direction} ***")
                log.info(f"  Signal: {signal_strength:.2f} | RSI: {rsi_value:.0f}{trend_info}")
                log.info(f"  Entry: ${entry_price:.2f} | Size: ${size:.2f}")
                log.info(f"  Mode: {state.mode} | Losses: {state.consecutive_losses}")

                result = place_order(client, token_id, shares, entry_price)

                if result and result.get("success"):
                    log.info(f"  ORDER PLACED: {result.get('status')}")

                    # FIX #3: Record position with stop-loss info
                    position = Position(
                        crypto=crypto,
                        direction=direction,
                        epoch=current_epoch,
                        shares=shares,
                        entry_price=entry_price,
                        cost=size,
                        token_id=token_id,
                        open_time=time.time(),
                        stop_loss_price=entry_price * (1 - STOP_LOSS_PCT)
                    )
                    guardian.record_position(position)
                    epoch_trades[crypto][current_epoch].append(direction)
                    epoch_bet_placed[current_epoch] = True

                    if tf_tracker:
                        try:
                            tf_tracker.record_trade(crypto, direction, entry_price, size, strategy)
                        except Exception as e:
                            log.warning(f"TF tracker failed: {e}")

                    state.last_trade_time = time.time()
                else:
                    log.error(f"  ORDER FAILED: {result}")

            # 8. CHECK FUTURE WINDOW ANOMALIES (NEW)
            # After checking current window, look for cheap future opportunities
            for crypto in CRYPTOS:
                # Get current market momentum
                direction, agree_count, avg_change, signals = price_feed.get_confluence_signal(crypto)
                if not direction or agree_count < 2:
                    continue

                # Calculate current signal strength
                prices = get_market_prices(get_current_market(crypto).get("tokens", []))
                if not prices or direction not in prices:
                    continue

                current_entry = prices[direction]["ask"]
                signal_strength, _ = signal_analyzer.calculate_signal_strength(
                    crypto, direction, signals, time_in_epoch, current_entry
                )

                # Detect anomalies in future windows
                anomalies = future_trader.detect_anomalies(crypto, direction, signal_strength)

                for anomaly in anomalies[:1]:  # Trade max 1 anomaly per crypto
                    # Check if we can afford it
                    anomaly_size = guardian.calculate_position_size(anomaly["confidence"])
                    if anomaly_size < MIN_BET_USD:
                        continue

                    # Check position limits
                    can_open, reason = guardian.can_open_position(
                        crypto, anomaly["market"]["epoch"], anomaly["direction"]
                    )
                    if not can_open:
                        continue

                    # Log the anomaly opportunity
                    log.info(f"\n*** [{crypto.upper()}] FUTURE ANOMALY DETECTED ***")
                    log.info(f"  Type: {anomaly['type']}")
                    log.info(f"  Window: +{anomaly['market']['minutes_away']} minutes")
                    log.info(f"  Direction: {anomaly['direction']} @ ${anomaly['entry_price']:.2f}")
                    log.info(f"  Reason: {anomaly['reason']}")
                    log.info(f"  Expected profit: {anomaly['expected_move']*100:.1f}%")

                    # Get token ID for the future market
                    future_prices = anomaly["market"]["prices"]
                    if anomaly["direction"] not in future_prices:
                        continue

                    token_id = future_prices[anomaly["direction"]]["token_id"]
                    shares = max(MIN_SHARES, anomaly_size / anomaly["entry_price"])
                    actual_cost = shares * anomaly["entry_price"]

                    # Place the order
                    result = place_order(client, token_id, shares, anomaly["entry_price"])

                    if result and result.get("success"):
                        log.info(f"  FUTURE ORDER PLACED: {result.get('status')}")

                        # Record position
                        position = Position(
                            crypto=crypto,
                            direction=anomaly["direction"],
                            epoch=anomaly["market"]["epoch"],
                            shares=shares,
                            entry_price=anomaly["entry_price"],
                            cost=actual_cost,
                            token_id=token_id,
                            open_time=time.time(),
                            stop_loss_price=anomaly["entry_price"] * (1 - STOP_LOSS_PCT)
                        )
                        guardian.record_position(position)

                        # Track this future epoch
                        if anomaly["market"]["epoch"] not in epoch_trades.get(crypto, {}):
                            epoch_trades[crypto][anomaly["market"]["epoch"]] = []
                        epoch_trades[crypto][anomaly["market"]["epoch"]].append(anomaly["direction"])

                        state.last_trade_time = time.time()
                    else:
                        log.error(f"  FUTURE ORDER FAILED: {result}")

            # 9. MANDATORY FALLBACK BET (only if no positions and not in recovery)
            # v12: Added FALLBACK_BET_ENABLED check - disabled by default as it was causing losses
            if (FALLBACK_BET_ENABLED and
                time_in_epoch >= FALLBACK_BET_TIME and
                time_in_epoch < 840 and
                current_epoch not in epoch_bet_placed and
                state.mode not in ["recovery", "halted"]):

                log.info(f"\n*** MANDATORY BET CHECK (v12: Consider disabling if causing losses) ***")

                best_bet = None
                best_score = 0

                for crypto in CRYPTOS:
                    market = get_current_market(crypto)
                    if not market:
                        continue

                    direction, agree_count, avg_change, signals = price_feed.get_confluence_signal(crypto)
                    if not direction:
                        rsi = rsi_calc.get_rsi(crypto)
                        direction = "Down" if rsi > 50 else "Up"

                    # Check correlation limit for fallback too
                    can_open, _ = guardian.can_open_position(crypto, current_epoch, direction)
                    if not can_open:
                        continue

                    prices = get_market_prices(market.get("tokens", []))
                    if direction not in prices:
                        continue

                    entry_price = prices[direction]["ask"]
                    token_id = prices[direction]["token_id"]

                    if entry_price > FALLBACK_MAX_ENTRY:
                        continue

                    rsi = rsi_calc.get_rsi(crypto)
                    score = 0.5

                    # FIX #5: Include trend in fallback - SKIP counter-trend bets
                    trend_score = 0
                    if TREND_FILTER_ENABLED and tf_tracker:
                        try:
                            conditions = tf_tracker.get_market_conditions(crypto)
                            trend_score = conditions.trend_score

                            # Skip choppy markets even for fallback
                            if abs(trend_score) < CHOPPY_MARKET_THRESHOLD:
                                log.info(f"  [{crypto.upper()}] SKIP fallback: Choppy market (trend={trend_score:.2f})")
                                continue

                            # SKIP counter-trend bets entirely (not just penalize)
                            if direction == "Up" and trend_score < -MIN_TREND_SCORE:
                                log.info(f"  [{crypto.upper()}] SKIP fallback Up: Downtrend ({trend_score:.2f})")
                                continue
                            if direction == "Down" and trend_score > MIN_TREND_SCORE:
                                log.info(f"  [{crypto.upper()}] SKIP fallback Down: Uptrend ({trend_score:.2f})")
                                continue

                            # Bonus for strong trend alignment
                            if (direction == "Up" and trend_score > 0.3) or \
                               (direction == "Down" and trend_score < -0.3):
                                score += 0.25
                        except Exception as e:
                            log.warning(f"Trend check error: {e}")

                    if agree_count >= 2:
                        score += 0.2
                    if (direction == "Up" and rsi < 50) or (direction == "Down" and rsi > 50):
                        score += 0.15
                    if entry_price < 0.50:
                        score += 0.15

                    if score > best_score:
                        best_score = score
                        best_bet = {
                            "crypto": crypto,
                            "direction": direction,
                            "entry_price": entry_price,
                            "token_id": token_id,
                            "rsi": rsi,
                            "score": score
                        }

                if best_bet:
                    crypto = best_bet["crypto"]
                    direction = best_bet["direction"]
                    entry_price = best_bet["entry_price"]
                    token_id = best_bet["token_id"]

                    # Ensure minimum 5 shares (CLOB requirement)
                    shares = max(MIN_SHARES, FALLBACK_BET_SIZE / entry_price)
                    actual_cost = shares * entry_price

                    # Check if we can afford the minimum
                    if actual_cost > state.current_balance * 0.5:
                        log.info(f"  SKIP FALLBACK: Cost ${actual_cost:.2f} too high for balance ${state.current_balance:.2f}")
                    else:
                        log.info(f"\n*** [{crypto.upper()}] FALLBACK: {direction} ***")
                        log.info(f"  Entry: ${entry_price:.2f} | Shares: {shares:.0f} | Cost: ${actual_cost:.2f}")

                        result = place_order(client, token_id, shares, entry_price)

                        if result and result.get("success"):
                            log.info(f"  FALLBACK PLACED")

                            position = Position(
                                crypto=crypto,
                                direction=direction,
                                epoch=current_epoch,
                                shares=shares,
                                entry_price=entry_price,
                                cost=actual_cost,
                                token_id=token_id,
                                open_time=time.time(),
                                stop_loss_price=entry_price * (1 - STOP_LOSS_PCT)
                            )
                            guardian.record_position(position)
                            if current_epoch not in epoch_trades.get(crypto, {}):
                                epoch_trades[crypto][current_epoch] = []
                            epoch_trades[crypto][current_epoch].append(direction)
                            epoch_bet_placed[current_epoch] = True

                            if tf_tracker:
                                try:
                                    tf_tracker.record_trade(crypto, direction, entry_price, actual_cost, "fallback")
                                except:
                                    pass

                            state.last_trade_time = time.time()
                        else:
                            log.error(f"  FALLBACK ORDER FAILED: {result}")

            # 9. STATUS UPDATE
            if int(time.time()) % 30 < 2:
                status = []
                for crypto in CRYPTOS:
                    rsi = rsi_calc.get_rsi(crypto)
                    direction, count, change, _ = price_feed.get_confluence_signal(crypto)
                    if direction:
                        status.append(f"{crypto.upper()}:{direction[0]}({count})")
                    else:
                        status.append(f"{crypto.upper()}:-")

                positions_str = f"{len(guardian.open_positions)} pos"
                log.info(f"[{time_in_epoch}s] {' | '.join(status)} | {state.mode} | ${portfolio_value:.2f} | {positions_str}")

            # 10. SAVE STATE
            save_state(state)

            # v11: Faster scan cycle for better latency
            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            log.info("Shutting down...")
            save_state(state)
            break
        except Exception as e:
            log.error(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
