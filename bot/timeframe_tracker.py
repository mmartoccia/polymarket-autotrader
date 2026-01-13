#!/usr/bin/env python3
"""
Multi-Timeframe Tracker for Polymarket Trading Analysis

Tracks hourly, daily, weekly, monthly conditions and session performance
to determine if higher timeframe alignment correlates with win rate.

Data captured at trade time:
- Hourly: direction, RSI, % change
- Daily: open-to-now direction, % change
- Weekly: week-to-date direction, % change
- Monthly: month-to-date direction, % change
- Session: Asian/European performance before trade
"""

import requests
import json
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

log = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Data storage - use server path if exists, else local
if os.path.exists("/opt/polymarket-bot"):
    TRACKER_DATA_DIR = "/opt/polymarket-bot/timeframe_analysis"
else:
    TRACKER_DATA_DIR = os.path.join(os.path.dirname(__file__), "timeframe_analysis")

TRADES_FILE = os.path.join(TRACKER_DATA_DIR, "trades_with_timeframes.json")
ANALYSIS_FILE = os.path.join(TRACKER_DATA_DIR, "correlation_analysis.json")

# Session times (UTC)
ASIAN_SESSION_START = 0    # 00:00 UTC (Tokyo open)
ASIAN_SESSION_END = 8      # 08:00 UTC
EURO_SESSION_START = 7     # 07:00 UTC (London open)
EURO_SESSION_END = 16      # 16:00 UTC
US_SESSION_START = 13      # 13:00 UTC (NYSE open)
US_SESSION_END = 21        # 21:00 UTC

# Binance kline intervals
KLINE_INTERVALS = {
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
    "1M": "1M"
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TimeframeCondition:
    """Condition for a single timeframe."""
    timeframe: str              # "1h", "4h", "1d", "1w", "1M"
    direction: str              # "up", "down", "flat"
    pct_change: float           # Percentage change
    rsi: Optional[float] = None # RSI if calculable
    trend_strength: float = 0.0 # 0-1 strength of trend


@dataclass
class SessionPerformance:
    """Performance during a trading session."""
    session: str           # "asian", "european", "us_premarket"
    direction: str         # "up", "down", "flat"
    pct_change: float      # % change during session
    volatility: float      # High-low range as %


@dataclass
class MarketConditions:
    """Complete market conditions at trade time."""
    timestamp: float
    crypto: str

    # Timeframe conditions
    hourly: TimeframeCondition
    four_hour: TimeframeCondition
    daily: TimeframeCondition
    weekly: TimeframeCondition
    monthly: TimeframeCondition

    # Session performance (if applicable)
    asian_session: Optional[SessionPerformance] = None
    euro_session: Optional[SessionPerformance] = None

    # Derived signals
    all_timeframes_aligned: bool = False
    major_timeframes_aligned: bool = False  # Daily + Weekly
    trend_score: float = 0.0  # -1 (strong down) to +1 (strong up)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "crypto": self.crypto,
            "hourly": asdict(self.hourly),
            "four_hour": asdict(self.four_hour),
            "daily": asdict(self.daily),
            "weekly": asdict(self.weekly),
            "monthly": asdict(self.monthly),
            "asian_session": asdict(self.asian_session) if self.asian_session else None,
            "euro_session": asdict(self.euro_session) if self.euro_session else None,
            "all_timeframes_aligned": self.all_timeframes_aligned,
            "major_timeframes_aligned": self.major_timeframes_aligned,
            "trend_score": self.trend_score
        }


@dataclass
class TrackedTrade:
    """Trade with timeframe conditions for analysis."""
    # Trade info
    timestamp: float
    crypto: str
    direction: str          # "Up" or "Down"
    entry_price: float
    cost: float
    strategy: str           # "early" or "late"

    # Market conditions at trade time
    conditions: MarketConditions

    # Outcome (filled in after resolution)
    outcome: Optional[str] = None   # "win", "loss"
    payout: Optional[float] = None
    profit: Optional[float] = None

    # Analysis flags
    traded_with_trend: bool = False
    traded_with_major_trend: bool = False

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "crypto": self.crypto,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "cost": self.cost,
            "strategy": self.strategy,
            "conditions": self.conditions.to_dict(),
            "outcome": self.outcome,
            "payout": self.payout,
            "profit": self.profit,
            "traded_with_trend": self.traded_with_trend,
            "traded_with_major_trend": self.traded_with_major_trend
        }


# =============================================================================
# TIMEFRAME TRACKER
# =============================================================================

class TimeframeTracker:
    """
    Fetches and tracks multi-timeframe conditions for each crypto.
    Uses Binance as primary, Kraken as fallback (for US IPs where Binance is blocked).
    """

    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
    KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

    BINANCE_SYMBOLS = {
        "btc": "BTCUSDT",
        "eth": "ETHUSDT",
        "sol": "SOLUSDT",
        "xrp": "XRPUSDT"
    }

    KRAKEN_SYMBOLS = {
        "btc": "XBTUSD",
        "eth": "ETHUSD",
        "sol": "SOLUSD",
        "xrp": "XRPUSD"
    }

    # Kraken interval mappings (in minutes)
    KRAKEN_INTERVALS = {
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
        "1M": 21600  # 15 days as proxy for monthly
    }

    def __init__(self):
        os.makedirs(TRACKER_DATA_DIR, exist_ok=True)
        self.trades: List[TrackedTrade] = []
        self._load_trades()

        # Cache for kline data (to reduce API calls)
        self._kline_cache: Dict[str, Tuple[float, list]] = {}
        self._cache_ttl = 60  # 1 minute cache

    def _load_trades(self):
        """Load existing trades from file."""
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE, 'r') as f:
                    data = json.load(f)
                    # Just store raw data, we'll convert when needed
                    self._raw_trades = data
                    log.info(f"Loaded {len(data)} tracked trades")
            except Exception as e:
                log.error(f"Error loading trades: {e}")
                self._raw_trades = []
        else:
            self._raw_trades = []

    def _save_trades(self):
        """Save trades to file."""
        try:
            with open(TRADES_FILE, 'w') as f:
                json.dump(self._raw_trades, f, indent=2)
        except Exception as e:
            log.error(f"Error saving trades: {e}")

    def _get_klines(self, crypto: str, interval: str, limit: int = 50) -> list:
        """Fetch kline data from Binance, fallback to Kraken if blocked."""
        cache_key = f"{crypto}_{interval}"
        now = time.time()

        # Check cache
        if cache_key in self._kline_cache:
            cached_time, cached_data = self._kline_cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_data

        # Try Binance first
        try:
            symbol = self.BINANCE_SYMBOLS.get(crypto)
            if symbol:
                resp = requests.get(
                    self.BINANCE_KLINES_URL,
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "limit": limit
                    },
                    timeout=10
                )

                if resp.status_code == 200:
                    data = resp.json()
                    self._kline_cache[cache_key] = (now, data)
                    return data
                elif resp.status_code != 451:  # Not a geo-block
                    log.warning(f"Binance kline fetch failed: {resp.status_code}")
        except Exception as e:
            log.debug(f"Binance error: {e}")

        # Fallback to Kraken
        try:
            symbol = self.KRAKEN_SYMBOLS.get(crypto)
            kraken_interval = self.KRAKEN_INTERVALS.get(interval)
            if not symbol or not kraken_interval:
                return []

            resp = requests.get(
                self.KRAKEN_OHLC_URL,
                params={
                    "pair": symbol,
                    "interval": kraken_interval
                },
                timeout=10
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("error"):
                    log.warning(f"Kraken error: {data['error']}")
                    return []

                # Convert Kraken format to Binance-like format
                result_key = list(data["result"].keys())[0]
                kraken_klines = data["result"][result_key]

                # Kraken format: [time, open, high, low, close, vwap, volume, count]
                # Convert to Binance format: [time, open, high, low, close, volume, ...]
                binance_format = []
                for k in kraken_klines[-limit:]:
                    binance_format.append([
                        k[0] * 1000,  # timestamp in ms
                        k[1],  # open
                        k[2],  # high
                        k[3],  # low
                        k[4],  # close
                        k[6],  # volume
                        0, 0, 0, 0, 0, 0  # padding
                    ])

                self._kline_cache[cache_key] = (now, binance_format)
                return binance_format
            else:
                log.warning(f"Kraken kline fetch failed: {resp.status_code}")
                return []

        except Exception as e:
            log.error(f"Error fetching klines from Kraken: {e}")
            return []

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI from closing prices."""
        if len(closes) < period + 1:
            return None

        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [c if c > 0 else 0 for c in changes[-period:]]
        losses = [-c if c < 0 else 0 for c in changes[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _get_timeframe_condition(self, crypto: str, interval: str) -> TimeframeCondition:
        """Get condition for a specific timeframe."""
        klines = self._get_klines(crypto, interval, limit=20)

        if not klines or len(klines) < 2:
            return TimeframeCondition(
                timeframe=interval,
                direction="flat",
                pct_change=0.0
            )

        # Current candle
        current = klines[-1]
        open_price = float(current[1])
        close_price = float(current[4])
        high = float(current[2])
        low = float(current[3])

        # Calculate % change
        if open_price > 0:
            pct_change = ((close_price - open_price) / open_price) * 100
        else:
            pct_change = 0.0

        # Determine direction
        if pct_change > 0.1:
            direction = "up"
        elif pct_change < -0.1:
            direction = "down"
        else:
            direction = "flat"

        # Calculate RSI from closes
        closes = [float(k[4]) for k in klines]
        rsi = self._calculate_rsi(closes)

        # Trend strength (0-1 based on candle body vs range)
        candle_range = high - low
        body = abs(close_price - open_price)
        trend_strength = (body / candle_range) if candle_range > 0 else 0

        return TimeframeCondition(
            timeframe=interval,
            direction=direction,
            pct_change=round(pct_change, 3),
            rsi=round(rsi, 1) if rsi else None,
            trend_strength=round(trend_strength, 2)
        )

    def _get_session_performance(self, crypto: str, session: str) -> Optional[SessionPerformance]:
        """Get performance for a trading session."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Determine if session is complete or in progress
        if session == "asian":
            if hour < ASIAN_SESSION_END:
                return None  # Session not complete
            start_hour = ASIAN_SESSION_START
            end_hour = ASIAN_SESSION_END
        elif session == "european":
            if hour < EURO_SESSION_END:
                return None
            start_hour = EURO_SESSION_START
            end_hour = EURO_SESSION_END
        else:
            return None

        # Get hourly klines for session
        klines = self._get_klines(crypto, "1h", limit=24)
        if not klines:
            return None

        # Filter klines for session hours (this is approximate)
        # We'll use the most recent session's data
        session_klines = klines[-8:]  # Last 8 hours as proxy

        if not session_klines:
            return None

        # Calculate session stats
        opens = [float(k[1]) for k in session_klines]
        closes = [float(k[4]) for k in session_klines]
        highs = [float(k[2]) for k in session_klines]
        lows = [float(k[3]) for k in session_klines]

        session_open = opens[0]
        session_close = closes[-1]
        session_high = max(highs)
        session_low = min(lows)

        if session_open > 0:
            pct_change = ((session_close - session_open) / session_open) * 100
            volatility = ((session_high - session_low) / session_open) * 100
        else:
            pct_change = 0.0
            volatility = 0.0

        if pct_change > 0.1:
            direction = "up"
        elif pct_change < -0.1:
            direction = "down"
        else:
            direction = "flat"

        return SessionPerformance(
            session=session,
            direction=direction,
            pct_change=round(pct_change, 3),
            volatility=round(volatility, 3)
        )

    def get_market_conditions(self, crypto: str) -> MarketConditions:
        """Get complete market conditions for a crypto."""
        now = time.time()

        # Fetch all timeframe conditions
        hourly = self._get_timeframe_condition(crypto, "1h")
        four_hour = self._get_timeframe_condition(crypto, "4h")
        daily = self._get_timeframe_condition(crypto, "1d")
        weekly = self._get_timeframe_condition(crypto, "1w")
        monthly = self._get_timeframe_condition(crypto, "1M")

        # Get session performance
        asian = self._get_session_performance(crypto, "asian")
        euro = self._get_session_performance(crypto, "european")

        # Check alignment
        directions = [hourly.direction, four_hour.direction, daily.direction,
                      weekly.direction, monthly.direction]

        all_up = all(d == "up" for d in directions)
        all_down = all(d == "down" for d in directions)
        all_aligned = all_up or all_down

        major_aligned = (daily.direction == weekly.direction and
                        daily.direction != "flat")

        # Calculate trend score (-1 to +1)
        score = 0.0
        weights = {"1h": 0.1, "4h": 0.15, "1d": 0.25, "1w": 0.3, "1M": 0.2}

        for tf, cond in [("1h", hourly), ("4h", four_hour), ("1d", daily),
                         ("1w", weekly), ("1M", monthly)]:
            if cond.direction == "up":
                score += weights[tf]
            elif cond.direction == "down":
                score -= weights[tf]

        return MarketConditions(
            timestamp=now,
            crypto=crypto,
            hourly=hourly,
            four_hour=four_hour,
            daily=daily,
            weekly=weekly,
            monthly=monthly,
            asian_session=asian,
            euro_session=euro,
            all_timeframes_aligned=all_aligned,
            major_timeframes_aligned=major_aligned,
            trend_score=round(score, 3)
        )

    def record_trade(self, crypto: str, direction: str, entry_price: float,
                     cost: float, strategy: str) -> TrackedTrade:
        """Record a trade with its market conditions."""
        conditions = self.get_market_conditions(crypto)

        # Determine if we're trading with the trend
        if direction == "Up":
            with_trend = conditions.trend_score > 0
            with_major = conditions.major_timeframes_aligned and conditions.daily.direction == "up"
        else:
            with_trend = conditions.trend_score < 0
            with_major = conditions.major_timeframes_aligned and conditions.daily.direction == "down"

        trade = TrackedTrade(
            timestamp=time.time(),
            crypto=crypto,
            direction=direction,
            entry_price=entry_price,
            cost=cost,
            strategy=strategy,
            conditions=conditions,
            traded_with_trend=with_trend,
            traded_with_major_trend=with_major
        )

        self._raw_trades.append(trade.to_dict())
        self._save_trades()

        log.info(f"[TRACKER] Recorded {crypto} {direction} trade | "
                f"Trend score: {conditions.trend_score:.2f} | "
                f"With trend: {with_trend} | Major aligned: {with_major}")

        return trade

    def update_trade_outcome(self, crypto: str, timestamp: float,
                             outcome: str, payout: float):
        """Update a trade with its outcome."""
        for trade_data in self._raw_trades:
            if (trade_data["crypto"] == crypto and
                abs(trade_data["timestamp"] - timestamp) < 60):
                trade_data["outcome"] = outcome
                trade_data["payout"] = payout
                trade_data["profit"] = payout - trade_data["cost"]
                self._save_trades()
                log.info(f"[TRACKER] Updated {crypto} trade outcome: {outcome}")
                return

        log.warning(f"[TRACKER] Could not find trade to update: {crypto} @ {timestamp}")

    def analyze_correlations(self) -> dict:
        """
        Analyze correlations between timeframe conditions and win rate.
        Returns analysis results.
        """
        if len(self._raw_trades) < 10:
            return {"error": "Not enough trades for analysis", "count": len(self._raw_trades)}

        # Filter trades with outcomes
        completed = [t for t in self._raw_trades if t.get("outcome")]

        if len(completed) < 10:
            return {"error": "Not enough completed trades", "count": len(completed)}

        analysis = {
            "total_trades": len(completed),
            "overall_win_rate": 0.0,
            "correlations": {}
        }

        wins = sum(1 for t in completed if t["outcome"] == "win")
        analysis["overall_win_rate"] = wins / len(completed)

        # Analyze by trend alignment
        with_trend = [t for t in completed if t.get("traded_with_trend")]
        against_trend = [t for t in completed if not t.get("traded_with_trend")]

        if with_trend:
            with_trend_wins = sum(1 for t in with_trend if t["outcome"] == "win")
            analysis["correlations"]["with_trend"] = {
                "trades": len(with_trend),
                "win_rate": with_trend_wins / len(with_trend),
                "avg_profit": statistics.mean([t.get("profit", 0) for t in with_trend])
            }

        if against_trend:
            against_wins = sum(1 for t in against_trend if t["outcome"] == "win")
            analysis["correlations"]["against_trend"] = {
                "trades": len(against_trend),
                "win_rate": against_wins / len(against_trend),
                "avg_profit": statistics.mean([t.get("profit", 0) for t in against_trend])
            }

        # Analyze by major timeframe alignment
        with_major = [t for t in completed if t.get("traded_with_major_trend")]
        without_major = [t for t in completed if not t.get("traded_with_major_trend")]

        if with_major:
            major_wins = sum(1 for t in with_major if t["outcome"] == "win")
            analysis["correlations"]["with_major_trend"] = {
                "trades": len(with_major),
                "win_rate": major_wins / len(with_major),
                "avg_profit": statistics.mean([t.get("profit", 0) for t in with_major])
            }

        if without_major:
            without_wins = sum(1 for t in without_major if t["outcome"] == "win")
            analysis["correlations"]["without_major_trend"] = {
                "trades": len(without_major),
                "win_rate": without_wins / len(without_major),
                "avg_profit": statistics.mean([t.get("profit", 0) for t in without_major])
            }

        # Analyze by hourly RSI
        high_rsi_up = [t for t in completed
                       if t["direction"] == "Up" and
                       t["conditions"]["hourly"].get("rsi", 50) > 60]
        low_rsi_down = [t for t in completed
                        if t["direction"] == "Down" and
                        t["conditions"]["hourly"].get("rsi", 50) < 40]

        if high_rsi_up:
            wins = sum(1 for t in high_rsi_up if t["outcome"] == "win")
            analysis["correlations"]["high_rsi_bet_up"] = {
                "trades": len(high_rsi_up),
                "win_rate": wins / len(high_rsi_up),
                "description": "Betting Up when hourly RSI > 60"
            }

        if low_rsi_down:
            wins = sum(1 for t in low_rsi_down if t["outcome"] == "win")
            analysis["correlations"]["low_rsi_bet_down"] = {
                "trades": len(low_rsi_down),
                "win_rate": wins / len(low_rsi_down),
                "description": "Betting Down when hourly RSI < 40"
            }

        # Analyze by strategy
        for strategy in ["early", "late"]:
            strat_trades = [t for t in completed if t.get("strategy") == strategy]
            if strat_trades:
                wins = sum(1 for t in strat_trades if t["outcome"] == "win")
                analysis["correlations"][f"{strategy}_strategy"] = {
                    "trades": len(strat_trades),
                    "win_rate": wins / len(strat_trades),
                    "avg_profit": statistics.mean([t.get("profit", 0) for t in strat_trades])
                }

        # Save analysis
        try:
            with open(ANALYSIS_FILE, 'w') as f:
                json.dump(analysis, f, indent=2)
        except Exception as e:
            log.error(f"Error saving analysis: {e}")

        return analysis

    def get_trade_recommendation(self, crypto: str, direction: str) -> Tuple[float, str]:
        """
        Get a recommendation score based on historical correlations.
        Returns (score 0-1, reason)
        """
        conditions = self.get_market_conditions(crypto)

        # Base score
        score = 0.5
        reasons = []

        # Check trend alignment
        if direction == "Up" and conditions.trend_score > 0.3:
            score += 0.2
            reasons.append(f"Strong uptrend ({conditions.trend_score:.2f})")
        elif direction == "Down" and conditions.trend_score < -0.3:
            score += 0.2
            reasons.append(f"Strong downtrend ({conditions.trend_score:.2f})")
        elif (direction == "Up" and conditions.trend_score < -0.3) or \
             (direction == "Down" and conditions.trend_score > 0.3):
            score -= 0.2
            reasons.append("Against major trend")

        # Check major timeframe alignment
        if conditions.major_timeframes_aligned:
            if (direction == "Up" and conditions.daily.direction == "up") or \
               (direction == "Down" and conditions.daily.direction == "down"):
                score += 0.15
                reasons.append("Daily+Weekly aligned")
            else:
                score -= 0.15
                reasons.append("Against Daily+Weekly")

        # Check RSI
        hourly_rsi = conditions.hourly.rsi or 50
        if direction == "Up" and hourly_rsi > 70:
            score -= 0.1
            reasons.append(f"Overbought (RSI {hourly_rsi:.0f})")
        elif direction == "Down" and hourly_rsi < 30:
            score -= 0.1
            reasons.append(f"Oversold (RSI {hourly_rsi:.0f})")

        # Clamp score
        score = max(0.0, min(1.0, score))

        reason = " | ".join(reasons) if reasons else "Neutral conditions"

        return score, reason

    def print_conditions(self, crypto: str):
        """Print current conditions for a crypto."""
        cond = self.get_market_conditions(crypto)

        print(f"\n{'='*60}")
        print(f"MARKET CONDITIONS: {crypto.upper()}")
        print(f"{'='*60}")
        print(f"Trend Score: {cond.trend_score:+.2f} (-1 bearish to +1 bullish)")
        print(f"All TFs Aligned: {cond.all_timeframes_aligned}")
        print(f"Major TFs (D+W) Aligned: {cond.major_timeframes_aligned}")
        print(f"\nTimeframes:")
        print(f"  1H:  {cond.hourly.direction:5} {cond.hourly.pct_change:+6.2f}% RSI:{cond.hourly.rsi or '?':>5}")
        print(f"  4H:  {cond.four_hour.direction:5} {cond.four_hour.pct_change:+6.2f}% RSI:{cond.four_hour.rsi or '?':>5}")
        print(f"  1D:  {cond.daily.direction:5} {cond.daily.pct_change:+6.2f}% RSI:{cond.daily.rsi or '?':>5}")
        print(f"  1W:  {cond.weekly.direction:5} {cond.weekly.pct_change:+6.2f}% RSI:{cond.weekly.rsi or '?':>5}")
        print(f"  1M:  {cond.monthly.direction:5} {cond.monthly.pct_change:+6.2f}% RSI:{cond.monthly.rsi or '?':>5}")

        if cond.asian_session:
            print(f"\nAsian Session: {cond.asian_session.direction} {cond.asian_session.pct_change:+.2f}%")
        if cond.euro_session:
            print(f"Euro Session: {cond.euro_session.direction} {cond.euro_session.pct_change:+.2f}%")


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    tracker = TimeframeTracker()

    # Print conditions for all cryptos
    for crypto in ["btc", "eth", "sol", "xrp"]:
        tracker.print_conditions(crypto)

        # Get recommendation for Up bet
        score, reason = tracker.get_trade_recommendation(crypto, "Up")
        print(f"\nUp bet recommendation: {score:.2f} - {reason}")

        score, reason = tracker.get_trade_recommendation(crypto, "Down")
        print(f"Down bet recommendation: {score:.2f} - {reason}")

    # Run analysis if we have data
    print("\n" + "="*60)
    print("CORRELATION ANALYSIS")
    print("="*60)
    analysis = tracker.analyze_correlations()
    print(json.dumps(analysis, indent=2))
