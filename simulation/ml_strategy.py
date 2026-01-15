#!/usr/bin/env python3
"""
ML Strategy for Shadow Trading

Integrates trained ML models (Random Forest, Logistic Regression) into the
shadow trading system for real-world validation.

Features:
- Loads pre-trained models from ml/models/
- Extracts features from live market data
- Makes predictions (win probability)
- Executes virtual trades based on probability threshold
- Tracks performance metrics
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pickle
import numpy as np
from typing import Dict, Optional
import logging

log = logging.getLogger(__name__)


class MLStrategy:
    """
    ML-based trading strategy using pre-trained models.

    Predicts win/loss probability and trades when confidence exceeds threshold.
    """

    def __init__(
        self,
        model_path: str,
        scaler_path: Optional[str] = None,
        threshold: float = 0.50,
        name: str = "ML Strategy"
    ):
        """
        Initialize ML strategy.

        Args:
            model_path: Path to pickled model file
            scaler_path: Path to pickled scaler (for LogReg)
            threshold: Minimum win probability to trade (default 0.50)
            name: Strategy name for logging
        """
        self.name = name
        self.threshold = threshold
        self.model = None
        self.scaler = None

        # Load model
        try:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            log.info(f"[{self.name}] Loaded model from: {model_path}")
        except Exception as e:
            log.error(f"[{self.name}] Failed to load model: {e}")
            raise

        # Load scaler if provided
        if scaler_path:
            try:
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                log.info(f"[{self.name}] Loaded scaler from: {scaler_path}")
            except Exception as e:
                log.warning(f"[{self.name}] Failed to load scaler: {e}")

        # Feature names (must match training order)
        # IMPORTANT: Exclude leaked features (market_wide_direction, multi_crypto_agreement, btc_correlation)
        self.feature_names = [
            'day_of_week',
            'minute_in_session',
            'epoch_sequence',
            'is_market_open',
            'rsi',
            'volatility',
            'price_momentum',
            'spread_proxy',
            'position_in_range',
            'price_z_score'
        ]

    def extract_features(self, market_data: dict) -> Optional[np.ndarray]:
        """
        Extract features from market data.

        Args:
            market_data: Dictionary with price data, RSI, etc.

        Returns:
            Feature vector as numpy array, or None if insufficient data
        """
        try:
            # Extract features in EXACT order used during training
            features = []

            # Time features
            dt = market_data.get('datetime', None)
            if dt:
                features.append(dt.weekday())  # day_of_week (0=Monday)
                minute_in_session = (dt.hour * 60 + dt.minute) % (24 * 60)
                features.append(minute_in_session)
            else:
                features.extend([0, 0])  # Default if datetime missing

            # Epoch sequence (approximation)
            epoch_sequence = market_data.get('epoch_sequence', 0)
            features.append(epoch_sequence)

            # Market open (9:30 AM - 4:00 PM ET)
            is_market_open = market_data.get('is_market_open', 1)
            features.append(is_market_open)

            # Price features
            features.append(market_data.get('rsi', 50.0))  # RSI
            features.append(market_data.get('volatility', 0.01))  # Volatility
            features.append(market_data.get('price_momentum', 0.0))  # Price momentum
            features.append(market_data.get('spread_proxy', 0.01))  # Spread proxy
            features.append(market_data.get('position_in_range', 0.5))  # Position in range
            features.append(market_data.get('price_z_score', 0.0))  # Price Z-score

            # Convert to numpy array
            feature_vector = np.array(features, dtype=np.float32).reshape(1, -1)

            # Sanity check
            if feature_vector.shape[1] != len(self.feature_names):
                log.error(f"[{self.name}] Feature count mismatch: expected {len(self.feature_names)}, got {feature_vector.shape[1]}")
                return None

            # Apply scaling if scaler exists (for LogReg)
            if self.scaler:
                feature_vector = self.scaler.transform(feature_vector)

            return feature_vector

        except Exception as e:
            log.error(f"[{self.name}] Feature extraction failed: {e}")
            return None

    def predict(self, market_data: dict) -> Optional[Dict[str, float]]:
        """
        Make prediction on market data.

        Args:
            market_data: Dictionary with price data, features, etc.

        Returns:
            Dictionary with prediction results:
                - win_probability: Probability of winning (0-1)
                - loss_probability: Probability of losing (0-1)
                - direction: 'Up' or 'Down' (predicted winning side)
                - confidence: win_probability (alias)
                - should_trade: True if win_probability > threshold
        """
        # Extract features
        features = self.extract_features(market_data)
        if features is None:
            log.warning(f"[{self.name}] Cannot predict - feature extraction failed")
            return None

        try:
            # Get prediction probabilities
            proba = self.model.predict_proba(features)[0]
            loss_prob = proba[0]
            win_prob = proba[1]

            # Determine direction based on market prices
            # If UP side is cheaper, predict UP; if DOWN side is cheaper, predict DOWN
            up_price = market_data.get('up_price', 0.5)
            down_price = market_data.get('down_price', 0.5)

            # Trade the cheaper side if model predicts win probability > threshold
            if up_price < down_price:
                direction = 'Up'
                entry_price = up_price
            else:
                direction = 'Down'
                entry_price = down_price

            # Decision: trade if win probability exceeds threshold
            should_trade = win_prob >= self.threshold

            return {
                'win_probability': float(win_prob),
                'loss_probability': float(loss_prob),
                'direction': direction,
                'entry_price': float(entry_price),
                'confidence': float(win_prob),
                'should_trade': should_trade,
                'threshold': self.threshold
            }

        except Exception as e:
            log.error(f"[{self.name}] Prediction failed: {e}")
            return None

    def get_decision(
        self,
        crypto: str,
        epoch: int,
        market_data: dict
    ) -> dict:
        """
        Make trading decision for shadow trading system.

        Args:
            crypto: Cryptocurrency (BTC, ETH, SOL, XRP)
            epoch: Epoch timestamp
            market_data: Market data including prices, RSI, etc.

        Returns:
            Decision dictionary with:
                - should_trade: bool
                - direction: 'Up' or 'Down'
                - confidence: 0-1
                - entry_price: predicted optimal entry
                - reason: explanation of decision
        """
        # Make prediction
        prediction = self.predict(market_data)

        if prediction is None:
            return {
                'should_trade': False,
                'direction': None,
                'confidence': 0.0,
                'entry_price': 0.0,
                'reason': 'Feature extraction or prediction failed'
            }

        # Extract decision components
        should_trade = prediction['should_trade']
        direction = prediction['direction']
        confidence = prediction['confidence']
        entry_price = prediction['entry_price']

        # Generate reason
        if should_trade:
            reason = (
                f"ML predicts {confidence:.1%} win probability (threshold {self.threshold:.0%}). "
                f"Trade {direction} @ ${entry_price:.3f}"
            )
        else:
            reason = (
                f"ML predicts {confidence:.1%} win probability < {self.threshold:.0%} threshold. Skip."
            )

        return {
            'should_trade': should_trade,
            'direction': direction,
            'confidence': confidence,
            'entry_price': entry_price,
            'reason': reason,
            'win_probability': prediction['win_probability'],
            'loss_probability': prediction['loss_probability']
        }


def create_random_forest_strategy(threshold: float = 0.50) -> MLStrategy:
    """
    Create ML strategy using Random Forest model.

    Args:
        threshold: Minimum win probability to trade (default 0.50)

    Returns:
        MLStrategy instance with Random Forest model
    """
    model_path = Path(__file__).parent.parent / 'ml' / 'models' / 'random_forest_baseline.pkl'
    return MLStrategy(
        model_path=str(model_path),
        scaler_path=None,  # Random Forest doesn't need scaling
        threshold=threshold,
        name="Random Forest ML"
    )


def create_logistic_regression_strategy(threshold: float = 0.50) -> MLStrategy:
    """
    Create ML strategy using Logistic Regression model.

    Args:
        threshold: Minimum win probability to trade (default 0.50)

    Returns:
        MLStrategy instance with Logistic Regression model
    """
    model_path = Path(__file__).parent.parent / 'ml' / 'models' / 'logistic_regression_baseline.pkl'
    scaler_path = Path(__file__).parent.parent / 'ml' / 'models' / 'scaler.pkl'

    return MLStrategy(
        model_path=str(model_path),
        scaler_path=str(scaler_path),
        threshold=threshold,
        name="Logistic Regression ML"
    )


if __name__ == '__main__':
    """Test ML strategy with sample data."""
    logging.basicConfig(level=logging.INFO)

    # Create strategies
    rf_strategy = create_random_forest_strategy(threshold=0.55)
    lr_strategy = create_logistic_regression_strategy(threshold=0.55)

    # Sample market data
    from datetime import datetime
    sample_data = {
        'crypto': 'BTC',
        'epoch': 1234567890,
        'datetime': datetime.now(),
        'up_price': 0.18,
        'down_price': 0.82,
        'rsi': 45.0,
        'volatility': 0.015,
        'price_momentum': 0.002,
        'spread_proxy': 0.012,
        'position_in_range': 0.35,
        'price_z_score': -0.5,
        'epoch_sequence': 10,
        'is_market_open': 1
    }

    print("\n" + "="*80)
    print("ML STRATEGY TEST")
    print("="*80 + "\n")

    # Test Random Forest
    print("Random Forest Strategy:")
    rf_decision = rf_strategy.get_decision('BTC', 1234567890, sample_data)
    print(f"  Should Trade: {rf_decision['should_trade']}")
    print(f"  Direction: {rf_decision['direction']}")
    print(f"  Confidence: {rf_decision['confidence']:.1%}")
    print(f"  Entry Price: ${rf_decision['entry_price']:.3f}")
    print(f"  Reason: {rf_decision['reason']}")
    print()

    # Test Logistic Regression
    print("Logistic Regression Strategy:")
    lr_decision = lr_strategy.get_decision('BTC', 1234567890, sample_data)
    print(f"  Should Trade: {lr_decision['should_trade']}")
    print(f"  Direction: {lr_decision['direction']}")
    print(f"  Confidence: {lr_decision['confidence']:.1%}")
    print(f"  Entry Price: ${lr_decision['entry_price']:.3f}")
    print(f"  Reason: {lr_decision['reason']}")
    print()

    print("="*80)
    print("✓ ML strategies loaded and tested successfully")
    print("="*80 + "\n")
