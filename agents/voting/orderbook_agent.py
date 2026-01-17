#!/usr/bin/env python3
"""
OrderBook Microstructure Expert Agent

Analyzes order book dynamics to generate trading signals based on:
- Bid-ask spread (tight = liquid, wide = volatile)
- Order book imbalance (bid volume vs ask volume)
- Market depth at key price levels
- Large order walls (support/resistance indicators)

This agent detects microstructure patterns that indicate:
- Liquidity conditions (tight spreads = easier execution)
- Directional pressure (imbalance = momentum building)
- Support/resistance (walls = price boundaries)
"""

import logging
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from base_agent import BaseAgent, Vote

log = logging.getLogger(__name__)


# Orderbook analysis thresholds
IMBALANCE_THRESHOLD = 0.15      # 15% imbalance to indicate directional pressure
SPREAD_TIGHT = 0.02             # <2% spread = liquid market
SPREAD_WIDE = 0.10              # >10% spread = volatile/illiquid
WALL_SIZE_THRESHOLD = 100.0     # $100+ order = significant wall
DEPTH_LEVELS = [0.10, 0.50, 0.90]  # Key price levels to analyze


@dataclass
class OrderBookMetrics:
    """Computed metrics from orderbook analysis."""

    # Spread metrics
    bid_price: float
    ask_price: float
    spread_pct: float
    mid_price: float

    # Volume metrics
    total_bid_volume: float
    total_ask_volume: float
    imbalance: float  # (bid_vol - ask_vol) / (bid_vol + ask_vol)

    # Depth metrics
    bid_depth_10: float  # Volume at 0.10 price
    ask_depth_10: float
    bid_depth_50: float  # Volume at 0.50 price
    ask_depth_50: float
    bid_depth_90: float  # Volume at 0.90 price
    ask_depth_90: float

    # Wall detection
    largest_bid_wall: float
    largest_ask_wall: float
    bid_wall_price: Optional[float]
    ask_wall_price: Optional[float]


class OrderBookAgent(BaseAgent):
    """
    Orderbook Microstructure Expert Agent.

    Analyzes:
    - Bid-ask spread (liquidity indicator)
    - Order book imbalance (directional pressure)
    - Market depth at key levels
    - Large order walls (support/resistance)

    Voting Formula:
        confidence = (imbalance_score × 0.40) + (spread_score × 0.20) +
                    (depth_score × 0.25) + (wall_score × 0.15)
        quality = Liquidity quality (spread-based)

    High confidence when:
    - Strong imbalance (>20%) indicates directional pressure
    - Tight spread (<5%) indicates liquid market
    - Deep support at favorable price levels
    - Large walls reinforcing direction
    """

    def __init__(self, name: str = "OrderBookAgent", weight: float = 1.0):
        super().__init__(name, weight)

        # Track historical metrics for trend detection
        self.historical_metrics: Dict[str, List[OrderBookMetrics]] = {}

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze orderbook microstructure and return vote.

        Args:
            crypto: Crypto symbol (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            data: Shared context with:
                - orderbook: Detailed orderbook data with bids/asks
                    Expected format (from ClobClient.get_order_book):
                    {
                        'bids': [{'price': str, 'size': str}, ...],
                        'asks': [{'price': str, 'size': str}, ...],
                        'spread': float (optional, pre-computed),
                    }
                - Or simplified format:
                    {
                        'Up': {'price': float, 'ask': float},
                        'Down': {'price': float, 'ask': float}
                    }

        Returns:
            Vote with orderbook analysis prediction
        """
        orderbook = data.get('orderbook', {})

        if not orderbook:
            # No orderbook data available - abstain
            return Vote(
                direction="Neutral",  # Abstain when no data (avoid bias)
                confidence=0.0,       # Zero confidence = won't affect consensus
                quality=0.0,          # No signal quality
                agent_name=self.name,
                reasoning="No orderbook data available - abstaining",
                details={}
            )

        # Check if we have detailed orderbook or simplified format
        if 'bids' in orderbook and 'asks' in orderbook:
            # Detailed orderbook format (from ClobClient.get_order_book)
            metrics = self._analyze_detailed_orderbook(orderbook)
        else:
            # Simplified format (from current bot implementation)
            metrics = self._analyze_simplified_orderbook(orderbook)

        # Store historical metrics
        if crypto not in self.historical_metrics:
            self.historical_metrics[crypto] = []

        self.historical_metrics[crypto].append(metrics)

        # Keep last 10 metrics for trend analysis
        if len(self.historical_metrics[crypto]) > 10:
            self.historical_metrics[crypto].pop(0)

        # Determine direction based on orderbook signals
        direction = self._determine_direction(metrics)

        # Calculate component scores
        scores = self._calculate_scores(metrics, direction)

        # Combined confidence (weighted average)
        confidence = (
            scores['imbalance'] * 0.40 +
            scores['spread'] * 0.20 +
            scores['depth'] * 0.25 +
            scores['wall'] * 0.15
        )

        # Quality based on market liquidity (tight spread = high quality)
        quality = scores['liquidity']

        # Build reasoning
        reasoning = self._build_reasoning(direction, metrics, scores)

        return Vote(
            direction=direction,
            confidence=confidence,
            quality=quality,
            agent_name=self.name,
            reasoning=reasoning,
            details={
                'spread_pct': metrics.spread_pct,
                'imbalance': metrics.imbalance,
                'bid_volume': metrics.total_bid_volume,
                'ask_volume': metrics.total_ask_volume,
                'largest_bid_wall': metrics.largest_bid_wall,
                'largest_ask_wall': metrics.largest_ask_wall,
                'scores': scores
            }
        )

    def _analyze_detailed_orderbook(self, orderbook: dict) -> OrderBookMetrics:
        """
        Analyze detailed orderbook from ClobClient.get_order_book.

        Expected format:
        {
            'bids': [{'price': '0.45', 'size': '100.5'}, ...],
            'asks': [{'price': '0.47', 'size': '85.2'}, ...]
        }
        """
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            # Empty orderbook - return neutral metrics
            return OrderBookMetrics(
                bid_price=0.45,
                ask_price=0.55,
                spread_pct=0.20,
                mid_price=0.50,
                total_bid_volume=0,
                total_ask_volume=0,
                imbalance=0,
                bid_depth_10=0, ask_depth_10=0,
                bid_depth_50=0, ask_depth_50=0,
                bid_depth_90=0, ask_depth_90=0,
                largest_bid_wall=0,
                largest_ask_wall=0,
                bid_wall_price=None,
                ask_wall_price=None
            )

        # Parse best bid/ask
        best_bid_price = float(bids[0]['price'])
        best_ask_price = float(asks[0]['price'])
        mid_price = (best_bid_price + best_ask_price) / 2
        spread_pct = (best_ask_price - best_bid_price) / mid_price if mid_price > 0 else 0

        # Calculate total volumes
        total_bid_volume = sum(float(bid['size']) for bid in bids)
        total_ask_volume = sum(float(ask['size']) for ask in asks)

        # Calculate imbalance
        total_volume = total_bid_volume + total_ask_volume
        if total_volume > 0:
            imbalance = (total_bid_volume - total_ask_volume) / total_volume
        else:
            imbalance = 0

        # Calculate depth at key levels
        bid_depth_10 = self._calculate_depth_at_level(bids, 0.10, 'bid')
        ask_depth_10 = self._calculate_depth_at_level(asks, 0.10, 'ask')
        bid_depth_50 = self._calculate_depth_at_level(bids, 0.50, 'bid')
        ask_depth_50 = self._calculate_depth_at_level(asks, 0.50, 'ask')
        bid_depth_90 = self._calculate_depth_at_level(bids, 0.90, 'bid')
        ask_depth_90 = self._calculate_depth_at_level(asks, 0.90, 'ask')

        # Detect walls (largest orders)
        largest_bid_wall = 0
        bid_wall_price = None
        for bid in bids:
            size = float(bid['size'])
            if size > largest_bid_wall:
                largest_bid_wall = size
                bid_wall_price = float(bid['price'])

        largest_ask_wall = 0
        ask_wall_price = None
        for ask in asks:
            size = float(ask['size'])
            if size > largest_ask_wall:
                largest_ask_wall = size
                ask_wall_price = float(ask['price'])

        return OrderBookMetrics(
            bid_price=best_bid_price,
            ask_price=best_ask_price,
            spread_pct=spread_pct,
            mid_price=mid_price,
            total_bid_volume=total_bid_volume,
            total_ask_volume=total_ask_volume,
            imbalance=imbalance,
            bid_depth_10=bid_depth_10,
            ask_depth_10=ask_depth_10,
            bid_depth_50=bid_depth_50,
            ask_depth_50=ask_depth_50,
            bid_depth_90=bid_depth_90,
            ask_depth_90=ask_depth_90,
            largest_bid_wall=largest_bid_wall,
            largest_ask_wall=largest_ask_wall,
            bid_wall_price=bid_wall_price,
            ask_wall_price=ask_wall_price
        )

    def _analyze_simplified_orderbook(self, orderbook: dict) -> OrderBookMetrics:
        """
        Analyze simplified orderbook format.

        Expected format:
        {
            'Up': {'price': 0.47, 'ask': 0.47},
            'Down': {'price': 0.53, 'ask': 0.53}
        }
        """
        # In Polymarket binary markets:
        # - 'Up' price = cost to buy Up outcome
        # - 'Down' price = cost to buy Down outcome
        # - Up + Down should equal ~1.00 (minus fees)

        up_price = float(orderbook.get('Up', {}).get('price', 0.50))
        down_price = float(orderbook.get('Down', {}).get('price', 0.50))

        # In binary markets, the price represents market probability:
        # - Up = $0.30 means market implies 30% chance Up wins (bearish for Up)
        # - Up = $0.70 means market implies 70% chance Up wins (bullish for Up)
        #
        # For orderbook "imbalance", we interpret:
        # - High Up price = bullish sentiment (positive imbalance)
        # - High Down price = bearish sentiment (negative imbalance)

        mid_price = (up_price + down_price) / 2

        # Synthetic imbalance based on price deviation from 0.50
        # If Up > 0.50, market is bullish → positive imbalance
        # If Down > 0.50 (Up < 0.50), market is bearish → negative imbalance
        synthetic_imbalance = (up_price - down_price) / 2  # Range: -0.5 to +0.5

        # Spread calculation
        spread_pct = abs(up_price - down_price) / mid_price if mid_price > 0 else 0

        # Since we don't have detailed data, use estimated values
        return OrderBookMetrics(
            bid_price=min(up_price, down_price),
            ask_price=max(up_price, down_price),
            spread_pct=spread_pct,
            mid_price=mid_price,
            total_bid_volume=0,  # Unknown in simplified format
            total_ask_volume=0,  # Unknown in simplified format
            imbalance=synthetic_imbalance,
            bid_depth_10=0,
            ask_depth_10=0,
            bid_depth_50=0,
            ask_depth_50=0,
            bid_depth_90=0,
            ask_depth_90=0,
            largest_bid_wall=0,
            largest_ask_wall=0,
            bid_wall_price=None,
            ask_wall_price=None
        )

    def _calculate_depth_at_level(self, orders: List[dict], price_level: float, side: str) -> float:
        """
        Calculate total volume at a specific price level.

        Args:
            orders: List of {'price': str, 'size': str}
            price_level: Target price (0.10, 0.50, 0.90)
            side: 'bid' or 'ask'

        Returns:
            Total volume within ±5% of price level
        """
        total_volume = 0
        tolerance = 0.05  # ±5% range

        for order in orders:
            price = float(order['price'])
            size = float(order['size'])

            # Check if price is within tolerance of target level
            if abs(price - price_level) / price_level <= tolerance:
                total_volume += size

        return total_volume

    def _determine_direction(self, metrics: OrderBookMetrics) -> str:
        """
        Determine trading direction based on orderbook metrics.

        Logic:
        - Positive imbalance (more bids) → Bullish → Up
        - Negative imbalance (more asks) → Bearish → Down
        - Walls reinforce direction
        """
        # Primary signal: imbalance
        if metrics.imbalance > IMBALANCE_THRESHOLD:
            direction = "Up"  # More buyers than sellers
        elif metrics.imbalance < -IMBALANCE_THRESHOLD:
            direction = "Down"  # More sellers than buyers
        else:
            # Weak imbalance - use walls as tiebreaker
            if metrics.largest_bid_wall > metrics.largest_ask_wall * 1.5:
                direction = "Up"  # Stronger bid support
            elif metrics.largest_ask_wall > metrics.largest_bid_wall * 1.5:
                direction = "Down"  # Stronger ask resistance
            else:
                # No clear signal - abstain to avoid directional bias
                direction = "Neutral"

        return direction

    def _calculate_scores(self, metrics: OrderBookMetrics, direction: str) -> Dict[str, float]:
        """
        Calculate component scores for confidence calculation.

        Returns:
            Dict with 'imbalance', 'spread', 'depth', 'wall', 'liquidity' scores
        """
        scores = {}

        # 1. Imbalance Score (0.0 - 1.0)
        # Strong imbalance (>30%) = 1.0, weak (<10%) = 0.3
        abs_imbalance = abs(metrics.imbalance)

        if abs_imbalance >= 0.30:
            scores['imbalance'] = 1.0
        elif abs_imbalance >= 0.20:
            scores['imbalance'] = 0.8
        elif abs_imbalance >= 0.15:
            scores['imbalance'] = 0.6
        elif abs_imbalance >= 0.10:
            scores['imbalance'] = 0.4
        else:
            scores['imbalance'] = 0.3

        # Check if imbalance aligns with direction
        if direction == "Up" and metrics.imbalance < 0:
            scores['imbalance'] *= 0.5  # Penalize misalignment
        elif direction == "Down" and metrics.imbalance > 0:
            scores['imbalance'] *= 0.5

        # 2. Spread Score (market quality)
        # Tight spread (<2%) = 1.0, wide (>10%) = 0.2
        if metrics.spread_pct < SPREAD_TIGHT:
            scores['spread'] = 1.0
        elif metrics.spread_pct < 0.05:
            scores['spread'] = 0.8
        elif metrics.spread_pct < 0.08:
            scores['spread'] = 0.6
        elif metrics.spread_pct < SPREAD_WIDE:
            scores['spread'] = 0.4
        else:
            scores['spread'] = 0.2

        # 3. Depth Score
        # Check depth at favorable price levels
        if direction == "Up":
            # For Up direction, we want strong bid support at 0.50
            depth_support = metrics.bid_depth_50
            depth_resistance = metrics.ask_depth_50
        else:
            # For Down direction, we want strong ask resistance at 0.50
            depth_support = metrics.ask_depth_50
            depth_resistance = metrics.bid_depth_50

        # Score based on support vs resistance ratio
        if depth_support > 0 and depth_resistance > 0:
            depth_ratio = depth_support / depth_resistance

            if depth_ratio > 2.0:
                scores['depth'] = 1.0
            elif depth_ratio > 1.5:
                scores['depth'] = 0.8
            elif depth_ratio > 1.0:
                scores['depth'] = 0.6
            else:
                scores['depth'] = 0.4
        else:
            scores['depth'] = 0.5  # Unknown depth

        # 4. Wall Score
        # Large walls (>$100) reinforce direction
        if direction == "Up":
            wall_strength = metrics.largest_bid_wall
        else:
            wall_strength = metrics.largest_ask_wall

        if wall_strength > WALL_SIZE_THRESHOLD * 2:
            scores['wall'] = 1.0
        elif wall_strength > WALL_SIZE_THRESHOLD:
            scores['wall'] = 0.8
        elif wall_strength > WALL_SIZE_THRESHOLD * 0.5:
            scores['wall'] = 0.6
        else:
            scores['wall'] = 0.4

        # 5. Liquidity Score (for quality metric)
        # Same as spread score - tight spread = high liquidity
        scores['liquidity'] = scores['spread']

        return scores

    def _build_reasoning(self, direction: str, metrics: OrderBookMetrics, scores: Dict[str, float]) -> str:
        """Build human-readable reasoning string."""

        imbalance_pct = metrics.imbalance * 100
        spread_pct = metrics.spread_pct * 100

        reasoning_parts = [
            f"{direction} signal:",
            f"imbalance {imbalance_pct:+.1f}%",
            f"spread {spread_pct:.1f}%"
        ]

        # Add wall info if significant
        if metrics.largest_bid_wall > WALL_SIZE_THRESHOLD:
            reasoning_parts.append(f"bid wall ${metrics.largest_bid_wall:.0f}")

        if metrics.largest_ask_wall > WALL_SIZE_THRESHOLD:
            reasoning_parts.append(f"ask wall ${metrics.largest_ask_wall:.0f}")

        # Add confidence indicators
        if scores['imbalance'] >= 0.8:
            reasoning_parts.append("STRONG imbalance")

        if scores['spread'] >= 0.8:
            reasoning_parts.append("liquid")
        elif scores['spread'] <= 0.4:
            reasoning_parts.append("WIDE spread")

        return ", ".join(reasoning_parts)
