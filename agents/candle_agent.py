"""
CandlestickAgent - Technical Analysis Expert

Analyzes candlestick patterns and positioning within broader trends
to identify high-confidence 15-minute epoch outcomes.

Key Insights:
- In bull trend, starting at bottom of green candle = likely Up
- In bear trend, starting at top of red candle = likely Down  
- Candle position + trend = powerful predictive combination
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from .base_agent import BaseAgent, Vote

@dataclass
class CandlePosition:
    """Where we are within current candle"""
    percent_from_bottom: float  # 0.0 = candle low, 1.0 = candle high
    candle_direction: str  # "Up" or "Down"
    candle_size: float  # % range of candle
    time_in_candle: int  # seconds into current candle
    
@dataclass  
class TrendContext:
    """Broader market trend"""
    trend: str  # "bull", "bear", "neutral"
    strength: float  # 0.0 to 1.0
    duration: int  # minutes in current trend
    

class CandlestickAgent(BaseAgent):
    """
    Analyzes candlestick positioning within trend context.
    
    Strategy:
    - Bull + bottom of candle = High confidence Up
    - Bear + top of candle = High confidence Down
    - Reversal patterns at extremes = Contrarian opportunities
    """
    
    def __init__(self):
        super().__init__("CandlestickAgent")
        self.candle_cache = {}  # Cache recent candle data
        
    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze candlestick position within trend context.
        
        High confidence signals:
        1. Bull trend + epoch starts at bottom 25% of candle
        2. Bear trend + epoch starts at top 25% of candle
        3. Strong trend (>0.7) + candle aligns with trend
        """
        try:
            # Get current candle position
            candle_pos = self._get_candle_position(crypto, data)
            
            # Get broader trend context  
            trend_ctx = self._get_trend_context(crypto, data)
            
            # Analyze for high-confidence signals
            signal = self._analyze_candle_trend_alignment(
                candle_pos, trend_ctx, data
            )
            
            return signal
            
        except Exception as e:
            # Neutral on error
            return Vote(
                agent_name=self.name,
                direction="Up",  # Default to Up on error/uncertainty
                confidence=0.0,
                quality=0.0,
                reasoning=f"Error: {e}"
            )
    
    def _get_candle_position(self, crypto: str, data: dict) -> CandlePosition:
        """
        Calculate where we are within current 15-min candle.
        
        Uses exchange prices to determine:
        - Candle open (epoch start price)
        - Candle high/low (range during epoch)
        - Current price (where we are now)
        """
        prices = data.get('prices', {})
        current_price = prices.get(crypto, 0)
        
        # Get epoch start time and current time
        time_in_epoch = data.get('time_in_epoch', 0)
        
        # Estimate candle range from price history
        # In real implementation, would fetch actual OHLC from exchange
        # For now, use simple approximation
        orderbook = data.get('orderbook', {})
        up_price = orderbook.get('yes', {}).get('price', 0.50)
        down_price = orderbook.get('no', {}).get('price', 0.50)
        
        # Approximate candle direction from current market sentiment
        if up_price > down_price:
            candle_direction = "Up"
            candle_size = up_price - 0.50
        else:
            candle_direction = "Down"
            candle_size = 0.50 - down_price
            
        # Estimate position within candle (0-1)
        # 0 = bottom, 1 = top
        percent_from_bottom = up_price if candle_direction == "Up" else (1 - down_price)
        
        return CandlePosition(
            percent_from_bottom=percent_from_bottom,
            candle_direction=candle_direction,
            candle_size=candle_size,
            time_in_candle=time_in_epoch
        )
    
    def _get_trend_context(self, crypto: str, data: dict) -> TrendContext:
        """
        Determine broader market trend from regime data.
        
        Uses:
        - Multi-timeframe trend scores
        - Regime classification (bull/bear/neutral)
        - Trend strength and duration
        """
        regime = data.get('regime', 'unknown')
        
        # Map regime to trend context
        if isinstance(regime, (int, float)):
            # Numeric trend score
            if regime > 0.25:
                trend = "bull"
                strength = min(regime, 1.0)
            elif regime < -0.25:
                trend = "bear"  
                strength = min(abs(regime), 1.0)
            else:
                trend = "neutral"
                strength = 0.0
        else:
            # String regime classification
            if 'bull' in str(regime).lower():
                trend = "bull"
                strength = 0.7
            elif 'bear' in str(regime).lower():
                trend = "bear"
                strength = 0.7
            else:
                trend = "neutral"
                strength = 0.3
                
        return TrendContext(
            trend=trend,
            strength=strength,
            duration=0  # Would track from state
        )
    
    def _analyze_candle_trend_alignment(
        self,
        candle: CandlePosition,
        trend: TrendContext,
        data: dict
    ) -> Vote:
        """
        Core analysis: Does candle position align with trend?
        
        HIGH CONFIDENCE SCENARIOS:
        
        1. BULL TREND + BOTTOM OF CANDLE
           - In strong uptrend (>0.6 strength)
           - Epoch starts at bottom 30% of current candle
           - Candle is green (Up direction)
           → Bet Up with 75-85% confidence
           
        2. BEAR TREND + TOP OF CANDLE  
           - In strong downtrend (>0.6 strength)
           - Epoch starts at top 30% of current candle
           - Candle is red (Down direction)
           → Bet Down with 75-85% confidence
           
        3. STRONG TREND + MID-CANDLE
           - Any strong trend (>0.7)
           - Middle 40-60% of candle
           → Bet with trend, 65-70% confidence
           
        4. REVERSAL PATTERNS
           - Candle exhaustion at extremes
           - Contrarian opportunity
        """
        
        # CRITICAL: Default direction (will be overridden if strong signal found)
        direction = "Up"  # Default bias
        confidence = 0.35  # Raised floor for quality control
        quality = 0.5
        reasoning = []

        time_in_epoch = data.get('time_in_epoch', 0)

        # Only analyze if early in epoch (first 5 minutes)
        # After that, candle position is stale
        if time_in_epoch > 300:
            return Vote(
                agent_name=self.name,
                direction="Up",  # Default to Up on error/uncertainty
                confidence=0.0,
                quality=0.3,
                reasoning="Too late in epoch for candle analysis"
            )
        
        # === HIGH CONFIDENCE SIGNAL #1: BULL + BOTTOM ===
        if (trend.trend == "bull" and 
            trend.strength > 0.6 and
            candle.percent_from_bottom < 0.30 and
            candle.candle_direction == "Up"):
            
            direction = "Up"
            confidence = 0.75 + (trend.strength * 0.10)  # 75-85%
            quality = 0.90
            reasoning.append(
                f"Bull trend ({trend.strength:.2f}) + bottom of Up candle "
                f"({candle.percent_from_bottom:.1%}) = High confidence Up"
            )
        
        # === HIGH CONFIDENCE SIGNAL #2: BEAR + TOP ===
        elif (trend.trend == "bear" and
              trend.strength > 0.6 and
              candle.percent_from_bottom > 0.70 and
              candle.candle_direction == "Down"):
            
            direction = "Down"
            confidence = 0.75 + (trend.strength * 0.10)  # 75-85%
            quality = 0.90
            reasoning.append(
                f"Bear trend ({trend.strength:.2f}) + top of Down candle "
                f"({candle.percent_from_bottom:.1%}) = High confidence Down"
            )
        
        # === MODERATE SIGNAL: TREND CONTINUATION ===
        elif trend.strength > 0.7:
            # Strong trend, mid-candle
            direction = "Up" if trend.trend == "bull" else "Down"
            confidence = 0.60 + (trend.strength * 0.10)
            quality = 0.70
            reasoning.append(
                f"Strong {trend.trend} trend ({trend.strength:.2f}) "
                f"suggests {direction}"
            )
        
        # === REVERSAL PATTERNS ===
        elif (candle.candle_size > 0.20 and  # Large candle
              candle.percent_from_bottom > 0.85):  # At extreme top
            # Potential reversal - candle exhaustion
            direction = "Down"
            confidence = 0.60
            quality = 0.65
            reasoning.append(
                f"Candle exhaustion at top ({candle.percent_from_bottom:.1%}) "
                f"suggests reversal Down"
            )
            
        elif (candle.candle_size > 0.20 and
              candle.percent_from_bottom < 0.15):  # At extreme bottom
            # Potential reversal
            direction = "Up"
            confidence = 0.60
            quality = 0.65
            reasoning.append(
                f"Candle exhaustion at bottom ({candle.percent_from_bottom:.1%}) "
                f"suggests reversal Up"
            )
        
        # Build final reasoning
        if not reasoning:
            reasoning.append(f"No clear candle pattern (trend={trend.trend}, pos={candle.percent_from_bottom:.1%})")
        
        return Vote(
            agent_name=self.name,
            direction=direction,
            confidence=confidence,
            quality=quality,
            reasoning=" | ".join(reasoning)
        )
    
    def update_performance(self, crypto: str, epoch: int, 
                          actual_outcome: str, profit: float):
        """Track candlestick pattern success rates"""
        # Would implement pattern tracking here
        pass
