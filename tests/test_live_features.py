#!/usr/bin/env python3
"""
Unit tests for LiveFeatureExtractor.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import unittest
import numpy as np
import time
from ml.live_features import (
    LiveFeatureExtractor,
    EpochData,
    FeatureVector,
    get_feature_names
)


class TestEpochData(unittest.TestCase):
    """Test EpochData dataclass."""

    def test_epoch_data_creation(self):
        """Test creating EpochData."""
        epoch = EpochData(
            crypto='btc',
            timestamp=1704988800.0,
            start_price=95000.0,
            end_price=95100.0,
            change_pct=0.105,
            hour=14,
            direction='Up'
        )

        self.assertEqual(epoch.crypto, 'btc')
        self.assertEqual(epoch.timestamp, 1704988800.0)
        self.assertEqual(epoch.start_price, 95000.0)
        self.assertEqual(epoch.end_price, 95100.0)
        self.assertEqual(epoch.change_pct, 0.105)
        self.assertEqual(epoch.hour, 14)
        self.assertEqual(epoch.direction, 'Up')


class TestFeatureVector(unittest.TestCase):
    """Test FeatureVector dataclass."""

    def test_feature_vector_creation(self):
        """Test creating FeatureVector with all features."""
        fv = FeatureVector(
            hour=14,
            day_of_week=2,
            minute_in_session=840,
            epoch_sequence=100,
            is_market_open=1,
            rsi=55.5,
            volatility=0.02,
            price_momentum=0.01,
            spread_proxy=0.1,
            position_in_range=0.6,
            price_z_score=0.5,
            btc_correlation=0.8,
            multi_crypto_agreement=0.75,
            market_wide_direction=1.0,
            data_quality=0.9,
            features_available=14
        )

        self.assertEqual(fv.hour, 14)
        self.assertEqual(fv.rsi, 55.5)
        self.assertEqual(fv.data_quality, 0.9)

    def test_to_array(self):
        """Test converting FeatureVector to numpy array."""
        fv = FeatureVector(
            hour=14, day_of_week=2, minute_in_session=840, epoch_sequence=100, is_market_open=1,
            rsi=55.5, volatility=0.02, price_momentum=0.01, spread_proxy=0.1,
            position_in_range=0.6, price_z_score=0.5,
            btc_correlation=0.8, multi_crypto_agreement=0.75, market_wide_direction=1.0
        )

        arr = fv.to_array()
        self.assertEqual(len(arr), 14)
        self.assertEqual(arr.dtype, np.float32)
        self.assertEqual(arr[0], 14)  # hour
        self.assertEqual(arr[5], 55.5)  # rsi

    def test_to_dict(self):
        """Test converting FeatureVector to dictionary."""
        fv = FeatureVector(
            hour=14, day_of_week=2, minute_in_session=840, epoch_sequence=100, is_market_open=1,
            rsi=55.5, volatility=0.02, price_momentum=0.01, spread_proxy=0.1,
            position_in_range=0.6, price_z_score=0.5,
            btc_correlation=0.8, multi_crypto_agreement=0.75, market_wide_direction=1.0
        )

        d = fv.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['hour'], 14)
        self.assertEqual(d['rsi'], 55.5)
        self.assertIn('data_quality', d)


class TestLiveFeatureExtractor(unittest.TestCase):
    """Test LiveFeatureExtractor."""

    def setUp(self):
        """Set up test extractor."""
        self.extractor = LiveFeatureExtractor(window_size=50)

    def test_initialization(self):
        """Test extractor initialization."""
        self.assertEqual(self.extractor.window_size, 50)
        self.assertEqual(len(self.extractor.history), 0)
        self.assertEqual(len(self.extractor.epoch_counts), 0)

    def test_add_epoch_single(self):
        """Test adding a single epoch."""
        epoch = EpochData(
            crypto='btc',
            timestamp=time.time(),
            start_price=95000.0,
            end_price=95100.0,
            change_pct=0.105,
            hour=14,
            direction='Up'
        )

        self.extractor.add_epoch(epoch)

        self.assertIn('btc', self.extractor.history)
        self.assertEqual(len(self.extractor.history['btc']), 1)
        self.assertEqual(self.extractor.epoch_counts['btc'], 1)

    def test_add_epoch_multiple(self):
        """Test adding multiple epochs."""
        for i in range(10):
            epoch = EpochData(
                crypto='btc',
                timestamp=time.time() - (10 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + 50,
                change_pct=0.05,
                hour=14,
                direction='Up'
            )
            self.extractor.add_epoch(epoch)

        self.assertEqual(len(self.extractor.history['btc']), 10)
        self.assertEqual(self.extractor.epoch_counts['btc'], 10)

    def test_add_epoch_window_overflow(self):
        """Test that deque auto-evicts when exceeding window_size."""
        extractor = LiveFeatureExtractor(window_size=10)

        for i in range(15):
            epoch = EpochData(
                crypto='btc',
                timestamp=time.time() - (15 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + 50,
                change_pct=0.05,
                hour=14,
                direction='Up'
            )
            extractor.add_epoch(epoch)

        # Should keep only last 10 epochs
        self.assertEqual(len(extractor.history['btc']), 10)
        # But total count should be 15
        self.assertEqual(extractor.epoch_counts['btc'], 15)

    def test_extract_features_no_data(self):
        """Test extracting features with no data returns None."""
        features = self.extractor.extract_features('btc')
        self.assertIsNone(features)

    def test_extract_features_insufficient_data(self):
        """Test extracting features with minimal data."""
        epoch = EpochData(
            crypto='btc',
            timestamp=time.time(),
            start_price=95000.0,
            end_price=95100.0,
            change_pct=0.105,
            hour=14,
            direction='Up'
        )
        self.extractor.add_epoch(epoch)

        features = self.extractor.extract_features('btc')

        # Should return FeatureVector but with many NaN values
        self.assertIsNotNone(features)
        self.assertIsInstance(features, FeatureVector)
        self.assertLess(features.data_quality, 0.1)  # Very low quality (1/50)
        self.assertLess(features.features_available, 14)  # Some features will be NaN

    def test_extract_features_sufficient_data(self):
        """Test extracting features with sufficient historical data."""
        # Add 30 epochs
        for i in range(30):
            epoch = EpochData(
                crypto='btc',
                timestamp=time.time() - (30 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + np.random.randn() * 200,
                change_pct=np.random.randn() * 0.5,
                hour=(14 + i // 4) % 24,
                direction='Up' if i % 2 == 0 else 'Down'
            )
            self.extractor.add_epoch(epoch)

        features = self.extractor.extract_features('btc')

        self.assertIsNotNone(features)
        self.assertIsInstance(features, FeatureVector)
        self.assertGreater(features.data_quality, 0.5)  # 30/50 = 0.6
        self.assertGreaterEqual(features.features_available, 10)  # Most features should be valid

    def test_time_features(self):
        """Test time feature extraction."""
        # Use current time for testing (timezone-agnostic)
        current_time = time.time()
        epoch_count = 10

        time_features = self.extractor._extract_time_features(current_time, epoch_count=epoch_count)

        self.assertEqual(len(time_features), 5)
        self.assertIn(time_features[0], range(24))  # hour (0-23)
        self.assertIn(time_features[1], range(7))  # day_of_week (0-6)
        self.assertIn(time_features[2], range(1440))  # minute_in_session (0-1439)
        self.assertEqual(time_features[3], epoch_count)  # epoch_sequence
        self.assertIn(time_features[4], [0, 1])  # is_market_open

    def test_rsi_calculation(self):
        """Test RSI calculation."""
        # Create price array with known pattern
        prices = np.array([100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
                          111, 110, 112, 114, 113, 115])  # 16 prices

        rsi = self.extractor._calculate_rsi(prices, period=14)

        # RSI should be between 0 and 100
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
        # Uptrend should have RSI > 50
        self.assertGreater(rsi, 50)

    def test_rsi_insufficient_data(self):
        """Test RSI returns NaN with insufficient data."""
        prices = np.array([100, 102, 101])  # Only 3 prices, need 15 for 14-period RSI

        rsi = self.extractor._calculate_rsi(prices, period=14)

        self.assertTrue(np.isnan(rsi))

    def test_price_features(self):
        """Test price feature extraction."""
        # Add epochs with known price pattern
        for i in range(30):
            epoch = EpochData(
                crypto='btc',
                timestamp=time.time() - (30 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + 50,
                change_pct=0.05,
                hour=14,
                direction='Up'
            )
            self.extractor.add_epoch(epoch)

        epochs = list(self.extractor.history['btc'])
        price_features = self.extractor._extract_price_features('btc', epochs)

        self.assertEqual(len(price_features), 6)
        # All features should be valid (not NaN) with 30 epochs
        self.assertFalse(np.isnan(price_features[0]))  # rsi
        self.assertFalse(np.isnan(price_features[1]))  # volatility
        # Others may be NaN depending on lookback requirements

    def test_cross_asset_features(self):
        """Test cross-asset feature extraction."""
        # Add epochs for BTC
        for i in range(20):
            self.extractor.add_epoch(EpochData(
                crypto='btc',
                timestamp=time.time() - (20 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + 50,
                change_pct=0.05,
                hour=14,
                direction='Up' if i % 2 == 0 else 'Down'
            ))

        # Add epochs for ETH
        for i in range(20):
            self.extractor.add_epoch(EpochData(
                crypto='eth',
                timestamp=time.time() - (20 - i) * 900,
                start_price=3500 + i * 10,
                end_price=3500 + i * 10 + 5,
                change_pct=0.05,
                hour=14,
                direction='Up' if i % 2 == 0 else 'Down'
            ))

        cross_features = self.extractor._extract_cross_asset_features(time.time())

        self.assertEqual(len(cross_features), 3)
        # multi_crypto_agreement and market_wide_direction should be valid
        self.assertFalse(np.isnan(cross_features[1]))  # multi_crypto_agreement
        self.assertFalse(np.isnan(cross_features[2]))  # market_wide_direction

    def test_get_history_stats(self):
        """Test getting history statistics."""
        # Add epochs for BTC
        for i in range(15):
            self.extractor.add_epoch(EpochData(
                crypto='btc',
                timestamp=time.time() - (15 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + 50,
                change_pct=0.05,
                hour=14,
                direction='Up'
            ))

        stats = self.extractor.get_history_stats()

        self.assertIn('btc', stats)
        self.assertEqual(stats['btc']['epochs_in_memory'], 15)
        self.assertEqual(stats['btc']['total_epochs'], 15)
        self.assertAlmostEqual(stats['btc']['data_quality'], 0.3, places=1)  # 15/50
        self.assertIsNotNone(stats['btc']['oldest_timestamp'])
        self.assertIsNotNone(stats['btc']['newest_timestamp'])

    def test_clear_history_single_crypto(self):
        """Test clearing history for single crypto."""
        # Add epochs for BTC and ETH
        for crypto in ['btc', 'eth']:
            for i in range(10):
                self.extractor.add_epoch(EpochData(
                    crypto=crypto,
                    timestamp=time.time() - (10 - i) * 900,
                    start_price=95000,
                    end_price=95100,
                    change_pct=0.1,
                    hour=14,
                    direction='Up'
                ))

        # Clear only BTC
        self.extractor.clear_history('btc')

        self.assertEqual(len(self.extractor.history['btc']), 0)
        self.assertEqual(self.extractor.epoch_counts['btc'], 0)
        self.assertEqual(len(self.extractor.history['eth']), 10)  # ETH untouched

    def test_clear_history_all(self):
        """Test clearing all history."""
        # Add epochs for multiple cryptos
        for crypto in ['btc', 'eth', 'sol']:
            for i in range(10):
                self.extractor.add_epoch(EpochData(
                    crypto=crypto,
                    timestamp=time.time() - (10 - i) * 900,
                    start_price=95000,
                    end_price=95100,
                    change_pct=0.1,
                    hour=14,
                    direction='Up'
                ))

        # Clear all
        self.extractor.clear_history()

        self.assertEqual(len(self.extractor.history), 0)
        self.assertEqual(len(self.extractor.epoch_counts), 0)

    def test_multiple_cryptos(self):
        """Test extracting features for multiple cryptos independently."""
        # Add epochs for BTC and ETH
        for i in range(30):
            self.extractor.add_epoch(EpochData(
                crypto='btc',
                timestamp=time.time() - (30 - i) * 900,
                start_price=95000 + i * 100,
                end_price=95000 + i * 100 + 50,
                change_pct=0.05,
                hour=14,
                direction='Up'
            ))

            self.extractor.add_epoch(EpochData(
                crypto='eth',
                timestamp=time.time() - (30 - i) * 900,
                start_price=3500 + i * 10,
                end_price=3500 + i * 10 + 5,
                change_pct=0.05,
                hour=14,
                direction='Down'
            ))

        btc_features = self.extractor.extract_features('btc')
        eth_features = self.extractor.extract_features('eth')

        self.assertIsNotNone(btc_features)
        self.assertIsNotNone(eth_features)
        # Both should have similar data quality
        self.assertAlmostEqual(btc_features.data_quality, eth_features.data_quality, places=2)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_get_feature_names(self):
        """Test getting feature names."""
        names = get_feature_names()

        self.assertEqual(len(names), 14)
        self.assertIn('hour', names)
        self.assertIn('rsi', names)
        self.assertIn('btc_correlation', names)
        self.assertEqual(names[0], 'hour')
        self.assertEqual(names[13], 'market_wide_direction')


if __name__ == '__main__':
    unittest.main()
