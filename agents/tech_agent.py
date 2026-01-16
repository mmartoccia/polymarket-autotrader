#!/usr/bin/env python3
"""
Technical Analysis Expert Agent

Analyzes price movements, RSI indicators, and multi-exchange confluence
to generate trading signals based on technical analysis.
"""

import time
import logging
import requests
from typing import Dict, Tuple, Optional, List
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from .base_agent import BaseAgent, Vote

log = logging.getLogger(__name__)


# Technical indicator thresholds
RSI_PERIOD = 14
RSI_HISTORY_SIZE = 50
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
# Lowered from 0.30% to 0.20% to detect cumulative multi-epoch trends (US-BF-017)
CONFLUENCE_THRESHOLD = 0.002  # 0.20% minimum price change


# Exchange symbol mappings
EXCHANGE_SYMBOLS = {
    "btc": {"binance": "BTCUSDT", "kraken": "XBTUSD", "coinbase": "BTC-USD"},
    "eth": {"binance": "ETHUSDT", "kraken": "ETHUSD", "coinbase": "ETH-USD"},
    "sol": {"binance": "SOLUSDT", "kraken": "SOLUSD", "coinbase": "SOL-USD"},
    "xrp": {"binance": "XRPUSDT", "kraken": "XRPUSD", "coinbase": "XRP-USD"},
}


class RSICalculator:
    """Calculate RSI indicator for technical analysis."""

    def __init__(self, period: int = RSI_PERIOD):
        self.period = period
        self.price_history: Dict[str, deque] = {}
        self.rsi_values: Dict[str, float] = {}

    def add_price(self, crypto: str, price: float, timestamp: float):
        """Add price data point and update RSI."""
        if crypto not in self.price_history:
            self.price_history[crypto] = deque(maxlen=RSI_HISTORY_SIZE)
            self.rsi_values[crypto] = 50.0

        self.price_history[crypto].append((timestamp, price))
        self._calculate_rsi(crypto)

    def _calculate_rsi(self, crypto: str):
        """Calculate RSI using average gains/losses."""
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
        """Get current RSI value."""
        return self.rsi_values.get(crypto, 50.0)

    def get_rsi_signal(self, crypto: str, direction: str) -> Tuple[float, str]:
        """
        Get RSI-based signal strength.

        Returns:
            (score, description): Score 0.0-1.0 and human-readable description
        """
        rsi = self.get_rsi(crypto)

        if direction == "Up":
            if rsi > RSI_OVERBOUGHT:
                return 0.0, f"RSI {rsi:.0f} OVERBOUGHT"
            elif rsi > 60:
                return 0.5, f"RSI {rsi:.0f} elevated"
            elif rsi >= 40:
                return 0.5, f"RSI {rsi:.0f} neutral → low confidence"
            else:
                return 0.8, f"RSI {rsi:.0f} oversold (good for Up)"
        else:  # Down
            if rsi < RSI_OVERSOLD:
                return 0.0, f"RSI {rsi:.0f} OVERSOLD"
            elif rsi < 40:
                return 0.5, f"RSI {rsi:.0f} low"
            elif rsi <= 60:
                return 0.5, f"RSI {rsi:.0f} neutral → low confidence"
            else:
                return 0.8, f"RSI {rsi:.0f} overbought (good for Down)"


class MultiExchangePriceFeed:
    """Fetches and tracks prices from multiple exchanges."""

    def __init__(self, rsi_calculator: RSICalculator):
        self.executor = ThreadPoolExecutor(max_workers=12)
        self.rsi = rsi_calculator
        self.epoch_starts: Dict[str, Dict[int, Dict[str, float]]] = {}
        self.current_prices: Dict[str, Dict[str, float]] = {}
        self.log = logging.getLogger(__name__)

    def get_binance_price(self, symbol: str) -> Optional[float]:
        """Fetch price from Binance."""
        try:
            resp = requests.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                timeout=2
            )
            return float(resp.json()["price"])
        except:
            return None

    def get_kraken_price(self, symbol: str) -> Optional[float]:
        """Fetch price from Kraken."""
        try:
            resp = requests.get(
                f"https://api.kraken.com/0/public/Ticker?pair={symbol}",
                timeout=2
            )
            data = resp.json()
            if data.get("error"):
                return None
            for key, val in data.get("result", {}).items():
                return float(val["c"][0])
            return None
        except:
            return None

    def get_coinbase_price(self, symbol: str) -> Optional[float]:
        """Fetch price from Coinbase."""
        try:
            resp = requests.get(
                f"https://api.coinbase.com/v2/prices/{symbol}/spot",
                timeout=2
            )
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

        # Update RSI with average price
        avg_price = sum(prices.values()) / len(prices)
        self.rsi.add_price(crypto, avg_price, time.time())

        # Track epoch start prices
        epoch = self.get_current_epoch()
        if crypto not in self.epoch_starts:
            self.epoch_starts[crypto] = {}

        if epoch not in self.epoch_starts[crypto]:
            self.epoch_starts[crypto][epoch] = prices.copy()

    def get_current_epoch(self) -> int:
        """Get current 15-minute epoch timestamp."""
        return (int(time.time()) // 900) * 900

    def get_confluence_signal(self, crypto: str) -> Tuple[Optional[str], int, float, Dict]:
        """
        Get price confluence signal from multiple exchanges.

        Returns:
            (direction, agreeing_count, avg_change, exchange_signals)
        """
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
                self.log.debug(f"✅ {exchange}: {change:+.3%} > {CONFLUENCE_THRESHOLD:.3%} → Up")
            elif change < -CONFLUENCE_THRESHOLD:
                direction = "Down"
                down_count += 1
                self.log.debug(f"✅ {exchange}: {change:+.3%} < -{CONFLUENCE_THRESHOLD:.3%} → Down")
            else:
                direction = "Flat"
                self.log.debug(f"❌ {exchange}: {change:+.3%} within ±{CONFLUENCE_THRESHOLD:.3%} → Flat (filtered)")

            signals[exchange] = (direction, change)
            total_change += change

        if not signals:
            return None, 0, 0, {}

        avg_change = total_change / len(signals)

        # Need at least 2 exchanges agreeing
        MIN_EXCHANGES_AGREE = 2

        if up_count >= MIN_EXCHANGES_AGREE:
            return "Up", up_count, avg_change, signals
        elif down_count >= MIN_EXCHANGES_AGREE:
            return "Down", down_count, avg_change, signals
        else:
            return None, max(up_count, down_count), avg_change, signals


class TechAgent(BaseAgent):
    """
    Technical Analysis Expert Agent.

    Analyzes:
    - Multi-exchange price confluence (2+ exchanges agreeing)
    - RSI momentum indicators
    - Price movement magnitude
    - Entry price value assessment

    Voting Formula:
        confidence = (exchange_score × 0.35) + (magnitude_score × 0.25) +
                    (rsi_score × 0.25) + (price_score × 0.15)
        quality = Average of individual component scores
    """

    def __init__(self, name: str = "TechAgent", weight: float = 1.0):
        super().__init__(name, weight)

        self.rsi_calculator = RSICalculator()
        self.price_feed = MultiExchangePriceFeed(self.rsi_calculator)

        # Track when we last updated prices for each crypto
        self.last_update: Dict[str, float] = {}

        # Track last 5 epochs of direction per crypto (US-BF-017: multi-epoch trend detection)
        self.epoch_history: Dict[str, deque] = {}

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze technical indicators and return vote.

        Args:
            crypto: Crypto symbol (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            data: Shared context with:
                - prices: Multi-exchange price data (optional - we fetch our own)
                - orderbook: Current orderbook
                - positions: Open positions
                - balance: Current balance

        Returns:
            Vote with technical analysis prediction
        """
        # Update prices if needed (every 2 seconds max)
        now = time.time()
        if crypto not in self.last_update or now - self.last_update[crypto] > 2.0:
            self.price_feed.update_prices(crypto)
            self.last_update[crypto] = now

        # Get price confluence signal
        direction, agreeing_count, avg_change, exchange_signals = \
            self.price_feed.get_confluence_signal(crypto)

        # CRITICAL FIX: If no clear direction, abstain (Skip) instead of defaulting to Up
        if direction is None:
            # Count Up vs Down from exchange signals
            up_count = sum(1 for sig in exchange_signals.values() if sig == "Up")
            down_count = sum(1 for sig in exchange_signals.values() if sig == "Down")

            # Pick majority direction, or Skip on tie (no default-to-Up bias)
            if up_count > down_count:
                direction = "Up"
            elif down_count > up_count:
                direction = "Down"
            else:
                # Tie or flat market - ABSTAIN instead of guessing
                vote = Vote(
                    direction="Skip",
                    confidence=0.0,
                    quality=0.0,
                    agent_name=self.name,
                    reasoning=f"No confluence detected: {up_count}Up/{down_count}Down tie, avg {avg_change:+.2%} → ABSTAINING",
                    details={
                        'agreeing_count': agreeing_count,
                        'avg_change': avg_change,
                        'exchange_signals': exchange_signals
                    }
                )
                self.log.debug(f"[{self.name}] {crypto}: {vote.direction} (conf={vote.confidence:.2f}) - {vote.reasoning}")
                return vote

            # Low confidence since no confluence
            vote = Vote(
                direction=direction,
                confidence=0.35,  # Raised floor for quality control
                quality=0.4,
                agent_name=self.name,
                reasoning=f"Weak signal: {up_count}Up/{down_count}Down, avg {avg_change:+.2%} → {direction}",
                details={
                    'agreeing_count': agreeing_count,
                    'avg_change': avg_change,
                    'exchange_signals': exchange_signals
                }
            )
            self.log.debug(f"[{self.name}] {crypto}: {vote.direction} (conf={vote.confidence:.2f}) - {vote.reasoning}")
            return vote

        # Get orderbook entry price if available
        orderbook = data.get('orderbook', {})
        if direction == "Up":
            entry_price = float(orderbook.get('yes', {}).get('price', 0.50))
        else:
            entry_price = float(orderbook.get('no', {}).get('price', 0.50))

        # Calculate component scores
        scores = self._calculate_scores(
            crypto,
            direction,
            exchange_signals,
            avg_change,
            entry_price
        )

        # Combined confidence (weighted average)
        confidence = (
            scores['exchange'] * 0.35 +
            scores['magnitude'] * 0.25 +
            scores['rsi'] * 0.25 +
            scores['price'] * 0.15
        )

        # Quality = average of all component scores
        quality = sum(scores.values()) / len(scores)

        # Build reasoning
        rsi = self.rsi_calculator.get_rsi(crypto)
        reasoning = (
            f"{direction} signal: {agreeing_count}/3 exchanges agreeing, "
            f"avg change {avg_change*100:+.2f}%, RSI {rsi:.0f}, "
            f"entry ${entry_price:.2f}"
        )

        # US-BF-017: Check for multi-epoch trend conflicts
        # Initialize epoch history for this crypto if needed
        if crypto not in self.epoch_history:
            self.epoch_history[crypto] = deque(maxlen=5)

        # Detect 3+ consecutive epochs in same direction (trend) BEFORE adding current
        trend_direction = None
        if len(self.epoch_history[crypto]) >= 3:
            last_3 = list(self.epoch_history[crypto])[-3:]
            if all(d == "Up" for d in last_3):
                trend_direction = "Up"
            elif all(d == "Down" for d in last_3):
                trend_direction = "Down"

        # If current vote conflicts with 3+ epoch trend, reduce confidence by 50%
        trend_conflict = False
        if trend_direction and direction != trend_direction:
            confidence *= 0.5
            trend_conflict = True
            epoch_str = ", ".join(list(self.epoch_history[crypto]))
            reasoning += f" | ⚠️ CONFLICTS with 3-epoch {trend_direction.lower()}trend [{epoch_str}], reducing confidence"
            self.log.info(f"🔴 [{self.name}] {crypto}: Detected 3-epoch {trend_direction.lower()}trend, but voting {direction} → reducing confidence by 50%")

        # Log trend detection
        if trend_direction:
            epoch_str = ", ".join(list(self.epoch_history[crypto]))
            self.log.debug(f"[{self.name}] Detected 3-epoch {trend_direction.lower()}trend ({crypto}): [{epoch_str}]")

        # Add current direction to history AFTER conflict detection
        self.epoch_history[crypto].append(direction)

        vote = Vote(
            direction=direction,
            confidence=confidence,
            quality=quality,
            agent_name=self.name,
            reasoning=reasoning,
            details={
                'agreeing_count': agreeing_count,
                'avg_change': avg_change * 100,
                'rsi': rsi,
                'entry_price': entry_price,
                'scores': scores,
                'exchange_signals': {ex: (d, c*100) for ex, (d, c) in exchange_signals.items()},
                'epoch_trend': trend_direction,
                'trend_conflict': trend_conflict
            }
        )
        self.log.debug(f"[{self.name}] {crypto}: {vote.direction} (conf={vote.confidence:.2f}) - {vote.reasoning}")
        return vote

    def _calculate_scores(self,
                         crypto: str,
                         direction: str,
                         exchange_signals: Dict,
                         avg_change: float,
                         entry_price: float) -> Dict[str, float]:
        """
        Calculate individual component scores.

        Returns:
            Dict with 'exchange', 'magnitude', 'rsi', 'price' scores
        """
        scores = {}

        # 1. Exchange Agreement Score
        agreeing = sum(1 for ex, (d, c) in exchange_signals.items() if d == direction)

        if agreeing >= 3:
            scores['exchange'] = 1.0
        elif agreeing >= 2:
            scores['exchange'] = 0.7
        else:
            scores['exchange'] = 0.0

        # 2. Move Magnitude Score
        magnitude = abs(avg_change)

        if magnitude > 0.005:  # 0.5%+
            scores['magnitude'] = 1.0
        elif magnitude > 0.003:  # 0.3%+
            scores['magnitude'] = 0.8
        elif magnitude > 0.0015:  # 0.15%+
            scores['magnitude'] = 0.5
        else:
            scores['magnitude'] = 0.2

        # 3. RSI Score
        rsi_score, rsi_desc = self.rsi_calculator.get_rsi_signal(crypto, direction)
        scores['rsi'] = rsi_score

        # 4. Entry Price Value Score (cheaper = better)
        if entry_price < 0.35:
            scores['price'] = 1.0
        elif entry_price < 0.45:
            scores['price'] = 0.8
        elif entry_price < 0.55:
            scores['price'] = 0.5
        else:
            scores['price'] = 0.2

        return scores
