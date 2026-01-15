#!/usr/bin/env python3
"""
Unit tests for Week3Validator
"""

import unittest
import sqlite3
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.week3_validator import Week3Validator, SignalQuality, ValidationResult


class TestWeek3Validator(unittest.TestCase):
    """Test cases for Week3Validator."""

    def setUp(self):
        """Create temporary database with test data."""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Create database schema
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE agent_votes (
                id INTEGER PRIMARY KEY,
                decision_id INTEGER,
                agent_name TEXT,
                direction TEXT,
                confidence REAL,
                quality REAL,
                reasoning TEXT,
                details TEXT
            )
        ''')
        conn.commit()
        conn.close()

        self.validator = Week3Validator(self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.validator.close()
        os.unlink(self.db_path)

    def test_empty_database(self):
        """Test with no votes in database."""
        quality = self.validator.get_signal_quality('OnChainAgent')

        self.assertEqual(quality.agent_name, 'OnChainAgent')
        self.assertEqual(quality.total_votes, 0)
        self.assertEqual(quality.avg_confidence, 0.0)
        self.assertEqual(quality.avg_quality, 0.0)

    def test_signal_quality_calculation(self):
        """Test signal quality metrics calculation."""
        # Insert test votes
        conn = sqlite3.connect(self.db_path)
        votes = [
            (1, 'OnChainAgent', 'Up', 0.70, 0.80, 'Strong outflow', 'Exchange flows detected'),
            (1, 'OnChainAgent', 'Down', 0.60, 0.75, 'Whale inflow', 'Whale alert triggered'),
            (2, 'OnChainAgent', 'Up', 0.50, 0.65, 'Moderate signal', 'OnChain data available'),
            (2, 'OnChainAgent', 'Down', 0.80, 0.90, 'Strong signal', 'Exchange flow + whale activity'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        quality = self.validator.get_signal_quality('OnChainAgent')

        self.assertEqual(quality.total_votes, 4)
        self.assertEqual(quality.votes_up, 2)
        self.assertEqual(quality.votes_down, 2)
        self.assertAlmostEqual(quality.avg_confidence, 0.65, places=2)
        self.assertAlmostEqual(quality.avg_quality, 0.775, places=2)
        self.assertEqual(quality.min_confidence, 0.50)
        self.assertEqual(quality.max_confidence, 0.80)
        self.assertIn('OnChain', quality.data_sources_active)

    def test_low_quality_votes_detection(self):
        """Test detection of low quality votes."""
        conn = sqlite3.connect(self.db_path)
        votes = [
            (1, 'SocialSentimentAgent', 'Up', 0.40, 0.20, 'Low quality', 'Twitter API error'),
            (2, 'SocialSentimentAgent', 'Down', 0.50, 0.25, 'Low quality', 'Reddit API error'),
            (3, 'SocialSentimentAgent', 'Up', 0.60, 0.70, 'Good quality', 'All sources active'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        quality = self.validator.get_signal_quality('SocialSentimentAgent')

        self.assertEqual(quality.total_votes, 3)
        self.assertEqual(quality.low_quality_votes, 2)  # Quality < 0.30

    def test_stale_data_detection(self):
        """Test detection of stale data votes."""
        conn = sqlite3.connect(self.db_path)
        votes = [
            (1, 'OnChainAgent', 'Up', 0.50, 0.40, 'Stale data', 'Data is stale (120s old)'),
            (2, 'OnChainAgent', 'Down', 0.60, 0.80, 'Fresh data', 'Recent whale transfer'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        quality = self.validator.get_signal_quality('OnChainAgent')

        self.assertEqual(quality.total_votes, 2)
        self.assertEqual(quality.stale_votes, 1)

    def test_api_error_detection(self):
        """Test detection of API errors."""
        conn = sqlite3.connect(self.db_path)
        votes = [
            (1, 'SocialSentimentAgent', 'Up', 0.30, 0.15, 'API error', 'Twitter API failed with 429 error'),
            (2, 'SocialSentimentAgent', 'Down', 0.40, 0.20, 'API error', 'Reddit API connection error'),
            (3, 'SocialSentimentAgent', 'Up', 0.70, 0.80, 'Success', 'All APIs responding'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        quality = self.validator.get_signal_quality('SocialSentimentAgent')

        self.assertEqual(quality.total_votes, 3)
        self.assertEqual(quality.api_errors, 2)

    def test_data_source_detection(self):
        """Test detection of active data sources."""
        conn = sqlite3.connect(self.db_path)
        votes = [
            (1, 'SocialSentimentAgent', 'Up', 0.60, 0.70, 'Multi-source', 'Twitter + Reddit + GoogleTrends active'),
            (2, 'SocialSentimentAgent', 'Down', 0.50, 0.60, 'Partial', 'Twitter + Reddit only'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        quality = self.validator.get_signal_quality('SocialSentimentAgent')

        self.assertEqual(quality.total_votes, 2)
        self.assertIn('Twitter', quality.data_sources_active)
        self.assertIn('Reddit', quality.data_sources_active)
        self.assertIn('GoogleTrends', quality.data_sources_active)

    def test_validation_passed(self):
        """Test validation passing with good metrics."""
        conn = sqlite3.connect(self.db_path)
        # Insert 15 high-quality votes
        votes = [
            (i, 'OnChainAgent', 'Up' if i % 2 == 0 else 'Down', 0.60 + (i % 5) * 0.05, 0.70 + (i % 3) * 0.10, 'Good signal', 'Exchange flows + OnChain data')
            for i in range(1, 16)
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        result = self.validator.validate_agent('OnChainAgent')

        self.assertTrue(result.passed)
        self.assertEqual(result.agent, 'OnChainAgent')
        self.assertGreaterEqual(result.metrics.avg_quality, 0.50)

    def test_validation_failed_insufficient_votes(self):
        """Test validation failing with insufficient votes."""
        conn = sqlite3.connect(self.db_path)
        votes = [
            (1, 'OnChainAgent', 'Up', 0.70, 0.80, 'Good signal', 'Exchange flows'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        result = self.validator.validate_agent('OnChainAgent')

        self.assertFalse(result.passed)
        self.assertTrue(any('Insufficient votes' in issue for issue in result.issues))

    def test_validation_failed_low_quality(self):
        """Test validation failing with low average quality."""
        conn = sqlite3.connect(self.db_path)
        # Insert 15 low-quality votes
        votes = [
            (i, 'SocialSentimentAgent', 'Up', 0.30, 0.20, 'Low quality', 'API errors')
            for i in range(1, 16)
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        result = self.validator.validate_agent('SocialSentimentAgent')

        self.assertFalse(result.passed)
        self.assertTrue(any('Low average quality' in issue for issue in result.issues))
        self.assertTrue(any('API keys' in rec for rec in result.recommendations))

    def test_validation_failed_high_stale_data(self):
        """Test validation failing with high stale data percentage."""
        conn = sqlite3.connect(self.db_path)
        # Insert 15 votes, 6 with stale data (40%)
        votes = [
            (i, 'OnChainAgent', 'Up', 0.50, 0.60, 'Data issue', 'Data is stale' if i <= 6 else 'Fresh data')
            for i in range(1, 16)
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        result = self.validator.validate_agent('OnChainAgent')

        # Check if stale data was detected
        self.assertGreater(result.metrics.stale_votes, 0)
        # Should have recommendation about stale data
        self.assertTrue(any('stale' in issue.lower() for issue in result.issues))

    def test_validation_unbalanced_distribution(self):
        """Test validation detecting unbalanced vote distribution."""
        conn = sqlite3.connect(self.db_path)
        # Insert 15 votes, all UP (100%)
        votes = [
            (i, 'OnChainAgent', 'Up', 0.60, 0.70, 'Always up', 'Signal')
            for i in range(1, 16)
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        result = self.validator.validate_agent('OnChainAgent')

        self.assertTrue(any('Unbalanced' in issue for issue in result.issues))
        self.assertTrue(any('directional bias' in rec.lower() for rec in result.recommendations))

    def test_validate_all_agents(self):
        """Test validating all Week 3 agents."""
        conn = sqlite3.connect(self.db_path)
        # Insert votes for both agents
        votes = [
            (1, 'OnChainAgent', 'Up', 0.70, 0.80, 'Good', 'OnChain data'),
            (2, 'SocialSentimentAgent', 'Down', 0.60, 0.70, 'Good', 'Twitter sentiment'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        results = self.validator.validate_all()

        self.assertEqual(len(results), 2)
        self.assertIn('OnChainAgent', results)
        self.assertIn('SocialSentimentAgent', results)

    def test_generate_report(self):
        """Test report generation."""
        conn = sqlite3.connect(self.db_path)
        # Insert minimal test data
        votes = [
            (1, 'OnChainAgent', 'Up', 0.70, 0.80, 'Good', 'Exchange flows'),
        ]
        conn.executemany(
            'INSERT INTO agent_votes (decision_id, agent_name, direction, confidence, quality, reasoning, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
            votes
        )
        conn.commit()
        conn.close()

        report = self.validator.generate_report()

        # Check report contains key sections
        self.assertIn('Week 3 Agent Signal Quality Validation Report', report)
        self.assertIn('OnChainAgent', report)
        self.assertIn('SocialSentimentAgent', report)
        self.assertIn('Signal Quality Metrics', report)
        self.assertIn('Validation Criteria', report)

    def test_api_health_check_no_keys(self):
        """Test API health check with no keys configured."""
        # Clear environment variables
        for key in ['WHALE_ALERT_API_KEY', 'ETHERSCAN_API_KEY', 'TWITTER_BEARER_TOKEN', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET']:
            os.environ.pop(key, None)

        health = self.validator.check_api_health()

        self.assertIn('OnChainAgent', health)
        self.assertIn('SocialSentimentAgent', health)

        # OnChain should be degraded (no keys)
        self.assertIn(health['OnChainAgent']['overall_status'], ['degraded', 'critical'])

        # Social should have GoogleTrends at minimum
        self.assertEqual(health['SocialSentimentAgent']['apis']['GoogleTrends']['status'], 'ready')

    def test_api_health_check_with_keys(self):
        """Test API health check with keys configured."""
        # Set mock environment variables
        os.environ['WHALE_ALERT_API_KEY'] = 'test_key'
        os.environ['TWITTER_BEARER_TOKEN'] = 'test_token'
        os.environ['REDDIT_CLIENT_ID'] = 'test_id'
        os.environ['REDDIT_CLIENT_SECRET'] = 'test_secret'

        health = self.validator.check_api_health()

        # OnChain should be healthy
        self.assertEqual(health['OnChainAgent']['overall_status'], 'healthy')
        self.assertEqual(health['OnChainAgent']['apis']['WhaleAlert']['status'], 'ready')

        # Social should be healthy
        self.assertEqual(health['SocialSentimentAgent']['overall_status'], 'healthy')
        self.assertEqual(health['SocialSentimentAgent']['apis']['Twitter']['status'], 'ready')
        self.assertEqual(health['SocialSentimentAgent']['apis']['Reddit']['status'], 'ready')

        # Clean up
        os.environ.pop('WHALE_ALERT_API_KEY', None)
        os.environ.pop('TWITTER_BEARER_TOKEN', None)
        os.environ.pop('REDDIT_CLIENT_ID', None)
        os.environ.pop('REDDIT_CLIENT_SECRET', None)


if __name__ == '__main__':
    unittest.main()
