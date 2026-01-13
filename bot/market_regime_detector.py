#!/usr/bin/env python3
"""
Market Regime Detector
Analyzes price data to classify market regime (bull, bear, volatile, sideways)
and recommends adaptive trading parameters
"""

import requests
from collections import deque
from typing import Dict, Optional
import statistics

CRYPTOS = ['btc', 'eth', 'sol', 'xrp']

# Price API endpoints
PRICE_APIS = {
    'binance': {
        'btc': 'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
        'eth': 'https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT',
        'sol': 'https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT',
        'xrp': 'https://api.binance.com/api/v3/ticker/price?symbol=XRPUSDT',
    }
}

class MarketRegimeDetector:
    """Detect market regime from price data."""

    def __init__(self, lookback_windows: int = 20):
        self.lookback = lookback_windows
        self.price_history: Dict[str, deque] = {
            crypto: deque(maxlen=lookback_windows)
            for crypto in CRYPTOS
        }

    def update_prices(self, crypto: str, price: float):
        """Add new price data point."""
        if crypto in self.price_history:
            self.price_history[crypto].append(price)

    def calculate_trend(self, crypto: str) -> dict:
        """Calculate trend metrics for a crypto."""
        prices = list(self.price_history[crypto])

        if len(prices) < 3:
            return {'trend': 'unknown', 'strength': 0, 'volatility': 0}

        # Calculate returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices))]

        # Trend direction
        mean_return = statistics.mean(returns)
        trend = 'bullish' if mean_return > 0.001 else ('bearish' if mean_return < -0.001 else 'sideways')

        # Trend strength (how consistent the direction is)
        positive_returns = sum(1 for r in returns if r > 0)
        strength = abs(positive_returns / len(returns) - 0.5) * 2  # 0-1 scale

        # Volatility (std dev of returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0

        return {
            'trend': trend,
            'strength': strength,
            'volatility': volatility,
            'mean_return': mean_return
        }

    def detect_regime(self) -> dict:
        """
        Detect overall market regime.

        Returns:
            dict with keys:
                - regime: 'bull_momentum', 'bear_momentum', 'volatile', 'sideways'
                - confidence: 0-1
                - volatility: average volatility
                - crypto_details: dict of per-crypto analysis
        """
        crypto_analysis = {}

        for crypto in CRYPTOS:
            crypto_analysis[crypto] = self.calculate_trend(crypto)

        # Aggregate trends
        trends = [a['trend'] for a in crypto_analysis.values()]
        strengths = [a['strength'] for a in crypto_analysis.values()]
        volatilities = [a['volatility'] for a in crypto_analysis.values()]

        avg_strength = statistics.mean(strengths) if strengths else 0
        avg_volatility = statistics.mean(volatilities) if volatilities else 0

        # Count trend directions
        bullish_count = sum(1 for t in trends if t == 'bullish')
        bearish_count = sum(1 for t in trends if t == 'bearish')

        # Determine regime
        if avg_volatility > 0.015:  # High volatility
            regime = 'volatile'
            confidence = min(avg_volatility / 0.025, 1.0)
        elif bullish_count >= 3:  # Majority bullish
            regime = 'bull_momentum'
            confidence = avg_strength
        elif bearish_count >= 3:  # Majority bearish
            regime = 'bear_momentum'
            confidence = avg_strength
        else:  # Mixed signals
            regime = 'sideways'
            confidence = 1.0 - avg_strength  # High confidence when low directional strength

        return {
            'regime': regime,
            'confidence': confidence,
            'volatility': avg_volatility,
            'crypto_details': crypto_analysis
        }

    def recommend_parameters(self, regime_data: dict) -> dict:
        """
        Recommend trading parameters based on regime.

        Returns dict of parameter overrides for momentum_bot_v12.py
        """
        regime = regime_data['regime']
        volatility = regime_data['volatility']

        # Base parameters (defaults from bot)
        params = {}

        if regime == 'bull_momentum':
            # Strong uptrend - favor momentum following
            params.update({
                'CONTRARIAN_ENABLED': False,           # Don't fade in trends!
                'MIN_SIGNAL_STRENGTH': 0.60,           # Lower threshold for momentum
                'EARLY_MAX_ENTRY': 0.35,               # Allow slightly higher entries
                'CONTRARIAN_MAX_ENTRY': 0.10,          # Very cheap contrarian only
                'MIN_TREND_SCORE': 0.20,               # Allow easier trend detection
                'strategy_focus': 'momentum_following'
            })

        elif regime == 'bear_momentum':
            # Strong downtrend - favor momentum following
            params.update({
                'CONTRARIAN_ENABLED': False,           # Don't fade in trends!
                'MIN_SIGNAL_STRENGTH': 0.60,
                'EARLY_MAX_ENTRY': 0.35,
                'CONTRARIAN_MAX_ENTRY': 0.10,
                'MIN_TREND_SCORE': 0.20,
                'strategy_focus': 'momentum_following'
            })

        elif regime == 'volatile':
            # High volatility - very conservative
            params.update({
                'CONTRARIAN_ENABLED': False,           # Too risky in volatility
                'MIN_SIGNAL_STRENGTH': 0.80,           # Much stronger signals
                'EARLY_MAX_ENTRY': 0.20,               # Only very cheap entries
                'CONTRARIAN_MAX_ENTRY': 0.10,
                'MAX_POSITION_USD': 10,                # Smaller positions
                'strategy_focus': 'ultra_conservative'
            })

        elif regime == 'sideways':
            # Range-bound - contrarian can work
            params.update({
                'CONTRARIAN_ENABLED': True,            # Fade extremes
                'MIN_SIGNAL_STRENGTH': 0.65,           # Standard threshold
                'EARLY_MAX_ENTRY': 0.30,               # Standard entries
                'CONTRARIAN_MAX_ENTRY': 0.20,          # Good contrarian entries
                'CONTRARIAN_PRICE_THRESHOLD': 0.70,    # Standard extreme
                'strategy_focus': 'mean_reversion'
            })

        return params


def get_current_prices() -> Dict[str, float]:
    """Fetch current prices from Binance."""
    prices = {}

    for crypto, url in PRICE_APIS['binance'].items():
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                prices[crypto] = float(data['price'])
        except Exception as e:
            print(f"Error fetching {crypto}: {e}")
            continue

    return prices


if __name__ == "__main__":
    # Test regime detection
    print("Testing Market Regime Detector...")
    print()

    detector = MarketRegimeDetector(lookback_windows=10)

    # Collect some sample data
    print("Collecting price samples...")
    import time

    for i in range(10):
        prices = get_current_prices()

        for crypto, price in prices.items():
            detector.update_prices(crypto, price)

        print(f"  Sample {i+1}/10: BTC=${prices.get('btc', 0):,.2f}")
        time.sleep(3)

    print()
    print("=" * 60)
    print("REGIME ANALYSIS")
    print("=" * 60)

    regime = detector.detect_regime()

    print(f"Regime: {regime['regime']}")
    print(f"Confidence: {regime['confidence']:.1%}")
    print(f"Volatility: {regime['volatility']:.4f}")
    print()

    print("Crypto Details:")
    for crypto, details in regime['crypto_details'].items():
        print(f"  {crypto.upper()}: {details['trend']} "
              f"(strength: {details['strength']:.2f}, vol: {details['volatility']:.4f})")

    print()
    print("=" * 60)
    print("RECOMMENDED PARAMETERS")
    print("=" * 60)

    params = detector.recommend_parameters(regime)

    print(f"Strategy Focus: {params['strategy_focus']}")
    print()
    print("Parameters:")
    for key, value in params.items():
        if key != 'strategy_focus':
            print(f"  {key} = {value}")
