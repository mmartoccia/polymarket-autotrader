#!/usr/bin/env python3
"""
Market Sentiment Expert Agent

Analyzes orderbook depth, bid/ask imbalances, and contrarian signals
to identify crowd psychology and mean reversion opportunities.
"""

import logging
from typing import Dict, Tuple, Optional

from .base_agent import BaseAgent, Vote

log = logging.getLogger(__name__)


# Sentiment thresholds
CONTRARIAN_PRICE_THRESHOLD = 0.70  # When one side >70%, consider fading
CONTRARIAN_MAX_ENTRY = 0.20        # Max price to pay for contrarian entry
EXTREME_PRICE_THRESHOLD = 0.85     # >85% is extreme overpricing
CHEAP_ENTRY_THRESHOLD = 0.10       # <$0.10 is very cheap
MODERATE_ENTRY_THRESHOLD = 0.15    # <$0.15 is moderately cheap

# Liquidity scoring thresholds
MIN_LIQUIDITY_DEPTH = 100          # Minimum shares for decent liquidity
GOOD_LIQUIDITY_DEPTH = 500         # Good liquidity threshold


class SentimentAgent(BaseAgent):
    """
    Market Sentiment Expert Agent.

    Analyzes:
    - Orderbook bid/ask imbalances
    - Contrarian opportunities (fade overpriced side)
    - Crowd psychology (when >70% confident, often wrong)
    - Liquidity depth and quality
    - Bot exit patterns (cascade selling near resolution)

    Strategy Focus:
    - Contrarian fade: Buy cheap when crowd overconfident
    - Mean reversion: Extreme prices tend to revert
    - Liquidity arbitrage: Better fills in liquid markets

    Voting Formula:
        confidence = (contrarian_score × 0.40) + (liquidity_score × 0.20) +
                    (extremity_score × 0.30) + (rsi_confirmation × 0.10)
        quality = Strength of contrarian signal + liquidity quality
    """

    def __init__(self, name: str = "SentimentAgent", weight: float = 1.0):
        super().__init__(name, weight)

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze market sentiment and return vote.

        Args:
            crypto: Crypto symbol (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            data: Shared context with:
                - orderbook: Current orderbook {'yes': {...}, 'no': {...}}
                - prices: Market prices
                - time_in_epoch: Seconds into current epoch
                - rsi: Current RSI value (optional)

        Returns:
            Vote with sentiment analysis prediction
        """
        orderbook = data.get('orderbook', {})
        time_in_epoch = data.get('time_in_epoch', 0)
        rsi = data.get('rsi', 50.0)

        if not orderbook:
            # CRITICAL FIX: No orderbook - default to Up with low confidence
            return Vote(
                direction="Up",  # Default when no data
                confidence=0.35,  # Raised floor for quality control
                quality=0.2,
                agent_name=self.name,
                reasoning="No orderbook → defaulting to Up",
                details={}
            )

        # Extract prices (check both 'Up'/'Down' and legacy 'yes'/'no' keys)
        up_data = orderbook.get('Up', orderbook.get('yes', {}))
        down_data = orderbook.get('Down', orderbook.get('no', {}))

        up_price = float(up_data.get('price', up_data.get('ask', 0.50)))
        down_price = float(down_data.get('price', down_data.get('ask', 0.50)))

        # Check for contrarian opportunity
        contrarian_signal = self._check_contrarian_opportunity(
            up_price,
            down_price,
            time_in_epoch,
            rsi
        )

        if contrarian_signal is None:
            # CRITICAL FIX: No contrarian signal - pick based on value
            # Cheaper side has better value (even if not extreme)
            if down_price < up_price:
                direction = "Down"
                reasoning = f"Down cheaper (${down_price:.2f} vs ${up_price:.2f})"
            else:
                direction = "Up"
                reasoning = f"Up cheaper (${up_price:.2f} vs ${down_price:.2f})"

            return Vote(
                direction=direction,  # ALWAYS pick Up or Down
                confidence=0.40,  # Raised floor for quality control
                quality=0.4,
                agent_name=self.name,
                reasoning=reasoning,
                details={
                    'up_price': up_price,
                    'down_price': down_price,
                    'time_in_epoch': time_in_epoch
                }
            )

        direction, entry_price, scores = contrarian_signal

        # Calculate overall confidence and quality
        confidence = (
            scores['contrarian'] * 0.40 +
            scores['liquidity'] * 0.20 +
            scores['extremity'] * 0.30 +
            scores['rsi'] * 0.10
        )

        # Quality based on signal strength and liquidity
        quality = (scores['contrarian'] + scores['liquidity']) / 2

        # Build reasoning
        opposite_side = "Up" if direction == "Down" else "Down"
        opposite_price = up_price if direction == "Down" else down_price

        reasoning = (
            f"Contrarian {direction}: {opposite_side} overpriced @ ${opposite_price:.2f}, "
            f"buying {direction} @ ${entry_price:.2f} "
            f"(extremity: {scores['extremity']:.0%}, liquidity: {scores['liquidity']:.0%})"
        )

        return Vote(
            direction=direction,
            confidence=confidence,
            quality=quality,
            agent_name=self.name,
            reasoning=reasoning,
            details={
                'up_price': up_price,
                'down_price': down_price,
                'entry_price': entry_price,
                'scores': scores,
                'time_in_epoch': time_in_epoch,
                'rsi': rsi
            }
        )

    def _check_contrarian_opportunity(self,
                                     up_price: float,
                                     down_price: float,
                                     time_in_epoch: int,
                                     rsi: float) -> Optional[Tuple[str, float, Dict]]:
        """
        Check if there's a contrarian opportunity.

        Args:
            up_price: Current Up side price
            down_price: Current Down side price
            time_in_epoch: Seconds into epoch
            rsi: Current RSI value

        Returns:
            (direction, entry_price, scores) or None if no opportunity
        """
        # Time window: 30-700 seconds (avoid first 30s chaos and last 3min resolution)
        CONTRARIAN_MIN_TIME = 30
        CONTRARIAN_MAX_TIME = 700

        if not (CONTRARIAN_MIN_TIME <= time_in_epoch <= CONTRARIAN_MAX_TIME):
            return None

        direction = None
        entry_price = None

        # Check if Up is overpriced (Down is cheap)
        if (up_price >= CONTRARIAN_PRICE_THRESHOLD and
            down_price <= CONTRARIAN_MAX_ENTRY):
            direction = "Down"
            entry_price = down_price

        # Check if Down is overpriced (Up is cheap)
        elif (down_price >= CONTRARIAN_PRICE_THRESHOLD and
              up_price <= CONTRARIAN_MAX_ENTRY):
            direction = "Up"
            entry_price = up_price

        if direction is None:
            return None

        # Calculate component scores
        scores = self._calculate_scores(direction, entry_price, up_price, down_price, rsi)

        return direction, entry_price, scores

    def _calculate_scores(self,
                         direction: str,
                         entry_price: float,
                         up_price: float,
                         down_price: float,
                         rsi: float) -> Dict[str, float]:
        """
        Calculate sentiment component scores.

        Returns:
            Dict with 'contrarian', 'liquidity', 'extremity', 'rsi' scores
        """
        scores = {}

        # 1. Contrarian Score (based on entry price cheapness)
        if entry_price <= 0.05:
            scores['contrarian'] = 1.0   # Extremely cheap (<$0.05)
        elif entry_price <= 0.10:
            scores['contrarian'] = 0.9   # Very cheap (<$0.10)
        elif entry_price <= 0.15:
            scores['contrarian'] = 0.75  # Cheap (<$0.15)
        elif entry_price <= 0.20:
            scores['contrarian'] = 0.60  # Moderately cheap (<$0.20)
        else:
            scores['contrarian'] = 0.40  # Above threshold

        # 2. Liquidity Score (placeholder - would need orderbook depth)
        # For now, assume moderate liquidity
        scores['liquidity'] = 0.70

        # 3. Extremity Score (how overpriced is the opposite side)
        opposite_price = up_price if direction == "Down" else down_price

        if opposite_price >= 0.90:
            scores['extremity'] = 1.0    # Extremely overpriced
        elif opposite_price >= 0.85:
            scores['extremity'] = 0.9    # Very overpriced
        elif opposite_price >= 0.80:
            scores['extremity'] = 0.75   # Overpriced
        elif opposite_price >= 0.70:
            scores['extremity'] = 0.60   # Moderately overpriced
        else:
            scores['extremity'] = 0.40   # Not extreme

        # 4. RSI Confirmation Score
        # For contrarian, we want RSI to confirm extremes
        if direction == "Down":
            # Buying Down (expecting price to fall)
            # Good if RSI is high (overbought)
            if rsi >= 70:
                scores['rsi'] = 1.0
            elif rsi >= 60:
                scores['rsi'] = 0.8
            elif rsi >= 50:
                scores['rsi'] = 0.6
            else:
                scores['rsi'] = 0.3  # RSI not confirming

        else:  # direction == "Up"
            # Buying Up (expecting price to rise)
            # Good if RSI is low (oversold)
            if rsi <= 30:
                scores['rsi'] = 1.0
            elif rsi <= 40:
                scores['rsi'] = 0.8
            elif rsi <= 50:
                scores['rsi'] = 0.6
            else:
                scores['rsi'] = 0.3  # RSI not confirming

        return scores

    def analyze_orderbook_depth(self, orderbook: dict) -> Dict[str, float]:
        """
        Analyze orderbook depth and liquidity.

        Args:
            orderbook: Full orderbook with bids/asks

        Returns:
            Dict with liquidity metrics
        """
        # Extract bid/ask data
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        # Calculate total depth
        bid_depth = sum(float(b.get('size', 0)) for b in bids)
        ask_depth = sum(float(a.get('size', 0)) for a in asks)

        # Calculate imbalance
        total_depth = bid_depth + ask_depth
        if total_depth > 0:
            bid_ratio = bid_depth / total_depth
            ask_ratio = ask_depth / total_depth
            imbalance = abs(bid_ratio - ask_ratio)
        else:
            bid_ratio = 0.5
            ask_ratio = 0.5
            imbalance = 0.0

        # Liquidity quality score
        if total_depth >= GOOD_LIQUIDITY_DEPTH:
            liquidity_score = 1.0
        elif total_depth >= MIN_LIQUIDITY_DEPTH:
            liquidity_score = 0.7
        else:
            liquidity_score = 0.3

        return {
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'total_depth': total_depth,
            'bid_ratio': bid_ratio,
            'ask_ratio': ask_ratio,
            'imbalance': imbalance,
            'liquidity_score': liquidity_score
        }

    def detect_bot_exit_pattern(self, time_in_epoch: int, prices: Dict) -> bool:
        """
        Detect if we're in the 12-minute bot exit window.

        Many bots exit positions at 11-13 minutes, causing price cascades.
        This can create contrarian opportunities.

        Args:
            time_in_epoch: Seconds into epoch
            prices: Current market prices

        Returns:
            True if bot exit pattern detected
        """
        BOT_EXIT_TIME_START = 660  # 11 minutes
        BOT_EXIT_TIME_END = 780    # 13 minutes

        if not (BOT_EXIT_TIME_START <= time_in_epoch <= BOT_EXIT_TIME_END):
            return False

        # Look for rapid price movements in this window
        # (Would need historical prices to implement fully)

        return True

    def calculate_crowd_sentiment(self, up_price: float, down_price: float) -> Dict:
        """
        Calculate crowd sentiment based on price distribution.

        Args:
            up_price: Up side price
            down_price: Down side price

        Returns:
            Dict with sentiment metrics
        """
        # Crowd is bullish if Up side is expensive
        # Crowd is bearish if Down side is expensive

        if up_price > 0.70:
            sentiment = "bullish"
            confidence = up_price
            contrarian_direction = "Down"
        elif down_price > 0.70:
            sentiment = "bearish"
            confidence = down_price
            contrarian_direction = "Up"
        else:
            sentiment = "neutral"
            confidence = 0.5
            contrarian_direction = None

        # Extremity level
        max_price = max(up_price, down_price)
        if max_price >= 0.90:
            extremity = "extreme"
        elif max_price >= 0.80:
            extremity = "high"
        elif max_price >= 0.70:
            extremity = "moderate"
        else:
            extremity = "low"

        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'extremity': extremity,
            'contrarian_direction': contrarian_direction,
            'up_price': up_price,
            'down_price': down_price
        }
