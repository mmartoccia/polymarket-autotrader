#!/usr/bin/env python3
"""
Week 3 Agent Signal Quality Validator

Validates OnChainAgent and SocialSentimentAgent signal quality:
- Data source availability and freshness
- Signal strength and confidence levels
- Vote distribution and quality scores
- API health and response times

This validator focuses on signal quality metrics rather than win rate
(which requires live trading data).
"""

import sys
import sqlite3
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent))

from config import agent_config


@dataclass
class SignalQuality:
    """Signal quality metrics for an agent."""
    agent_name: str
    total_votes: int
    avg_confidence: float
    avg_quality: float
    min_confidence: float
    max_confidence: float
    votes_up: int
    votes_down: int
    low_quality_votes: int  # Quality < 0.30
    stale_votes: int  # Votes with stale data
    api_errors: int  # Errors encountered
    data_sources_active: List[str]  # Which data sources are working


@dataclass
class ValidationResult:
    """Validation result for Week 3 agents."""
    passed: bool
    agent: str
    metrics: SignalQuality
    issues: List[str]
    recommendations: List[str]


class Week3Validator:
    """Validator for Week 3 agents (OnChain and SocialSentiment)."""

    WEEK3_AGENTS = ['OnChainAgent', 'SocialSentimentAgent']

    # Quality thresholds
    MIN_CONFIDENCE = 0.35  # Minimum acceptable confidence
    MIN_QUALITY = 0.30  # Minimum acceptable quality
    MIN_VOTES = 10  # Minimum votes needed for validation
    MAX_LOW_QUALITY_PCT = 0.30  # Max 30% low-quality votes
    MAX_STALE_PCT = 0.20  # Max 20% stale data votes
    MIN_AVG_QUALITY = 0.50  # Minimum average quality

    def __init__(self, db_path: str):
        """
        Initialize validator.

        Args:
            db_path: Path to SQLite trade journal database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_signal_quality(self, agent_name: str) -> SignalQuality:
        """
        Calculate signal quality metrics for an agent.

        Args:
            agent_name: Name of agent

        Returns:
            SignalQuality dataclass
        """
        # Get all votes for this agent
        cursor = self.conn.execute('''
            SELECT
                agent_name,
                direction,
                confidence,
                quality,
                details
            FROM agent_votes
            WHERE agent_name = ?
            ORDER BY id DESC
        ''', (agent_name,))

        votes = cursor.fetchall()

        if not votes:
            return SignalQuality(
                agent_name=agent_name,
                total_votes=0,
                avg_confidence=0.0,
                avg_quality=0.0,
                min_confidence=0.0,
                max_confidence=0.0,
                votes_up=0,
                votes_down=0,
                low_quality_votes=0,
                stale_votes=0,
                api_errors=0,
                data_sources_active=[]
            )

        # Calculate metrics
        confidences = [v['confidence'] for v in votes]
        qualities = [v['quality'] for v in votes]

        votes_up = sum(1 for v in votes if v['direction'] == 'Up')
        votes_down = sum(1 for v in votes if v['direction'] == 'Down')

        low_quality = sum(1 for q in qualities if q < self.MIN_QUALITY)

        # Parse details for stale data and API errors
        stale_count = 0
        error_count = 0
        data_sources = set()

        for vote in votes:
            details = vote['details'] or ''

            # Check for stale data indicators
            if 'stale' in details.lower() or 'old data' in details.lower():
                stale_count += 1

            # Check for API errors
            if 'error' in details.lower() or 'failed' in details.lower():
                error_count += 1

            # Detect active data sources
            if 'twitter' in details.lower():
                data_sources.add('Twitter')
            if 'reddit' in details.lower():
                data_sources.add('Reddit')
            if 'trends' in details.lower() or 'google' in details.lower():
                data_sources.add('GoogleTrends')
            if 'whale' in details.lower() or 'onchain' in details.lower():
                data_sources.add('OnChain')
            if 'exchange flow' in details.lower():
                data_sources.add('ExchangeFlows')

        return SignalQuality(
            agent_name=agent_name,
            total_votes=len(votes),
            avg_confidence=sum(confidences) / len(confidences),
            avg_quality=sum(qualities) / len(qualities),
            min_confidence=min(confidences),
            max_confidence=max(confidences),
            votes_up=votes_up,
            votes_down=votes_down,
            low_quality_votes=low_quality,
            stale_votes=stale_count,
            api_errors=error_count,
            data_sources_active=sorted(data_sources)
        )

    def validate_agent(self, agent_name: str) -> ValidationResult:
        """
        Validate an agent's signal quality.

        Args:
            agent_name: Name of agent

        Returns:
            ValidationResult with pass/fail and recommendations
        """
        metrics = self.get_signal_quality(agent_name)
        issues = []
        recommendations = []
        passed = True

        # Check minimum votes
        if metrics.total_votes < self.MIN_VOTES:
            issues.append(f"Insufficient votes: {metrics.total_votes} < {self.MIN_VOTES}")
            recommendations.append("Continue collecting data - validation needs more samples")
            passed = False

        # Check average quality
        if metrics.avg_quality < self.MIN_AVG_QUALITY:
            issues.append(f"Low average quality: {metrics.avg_quality:.2f} < {self.MIN_AVG_QUALITY}")
            recommendations.append("Check API keys and data source configuration")
            passed = False

        # Check low quality percentage
        if metrics.total_votes > 0:
            low_quality_pct = metrics.low_quality_votes / metrics.total_votes
            if low_quality_pct > self.MAX_LOW_QUALITY_PCT:
                issues.append(f"High low-quality votes: {low_quality_pct:.1%} > {self.MAX_LOW_QUALITY_PCT:.1%}")
                recommendations.append("Investigate data source failures or missing API keys")
                passed = False

        # Check stale data percentage
        if metrics.total_votes > 0:
            stale_pct = metrics.stale_votes / metrics.total_votes
            if stale_pct > self.MAX_STALE_PCT:
                issues.append(f"High stale data: {stale_pct:.1%} > {self.MAX_STALE_PCT:.1%}")
                recommendations.append("Check data source update frequency and caching logic")

        # Check API errors
        if metrics.total_votes > 0:
            error_pct = metrics.api_errors / metrics.total_votes
            if error_pct > 0.10:  # > 10% errors
                issues.append(f"High API error rate: {error_pct:.1%}")
                recommendations.append("Check API credentials, rate limits, and network connectivity")
                passed = False

        # Check data source availability
        expected_sources = {
            'OnChainAgent': ['OnChain', 'ExchangeFlows'],
            'SocialSentimentAgent': ['Twitter', 'Reddit', 'GoogleTrends']
        }

        expected = expected_sources.get(agent_name, [])
        if expected and not metrics.data_sources_active:
            issues.append("No data sources active")
            recommendations.append(f"Configure API keys for: {', '.join(expected)}")
            passed = False
        elif expected:
            missing = set(expected) - set(metrics.data_sources_active)
            if missing:
                issues.append(f"Missing data sources: {', '.join(missing)}")
                recommendations.append(f"Enable {', '.join(missing)} for better signal quality")

        # Check confidence range
        if metrics.max_confidence < 0.50 and metrics.total_votes >= self.MIN_VOTES:
            issues.append(f"Low maximum confidence: {metrics.max_confidence:.2f}")
            recommendations.append("Agent may need threshold tuning or data quality is poor")

        # Check vote distribution (should not be 100% one direction)
        if metrics.total_votes >= self.MIN_VOTES:
            up_pct = metrics.votes_up / metrics.total_votes
            if up_pct > 0.90 or up_pct < 0.10:
                issues.append(f"Unbalanced vote distribution: {up_pct:.1%} UP")
                recommendations.append("Check for directional bias in signal logic")

        return ValidationResult(
            passed=passed,
            agent=agent_name,
            metrics=metrics,
            issues=issues,
            recommendations=recommendations
        )

    def validate_all(self) -> Dict[str, ValidationResult]:
        """
        Validate all Week 3 agents.

        Returns:
            Dict mapping agent name to ValidationResult
        """
        results = {}
        for agent_name in self.WEEK3_AGENTS:
            results[agent_name] = self.validate_agent(agent_name)
        return results

    def generate_report(self) -> str:
        """
        Generate a comprehensive validation report.

        Returns:
            Formatted report string
        """
        results = self.validate_all()

        lines = []
        lines.append("=" * 80)
        lines.append("Week 3 Agent Signal Quality Validation Report")
        lines.append("=" * 80)
        lines.append("")

        # Overall summary
        all_passed = all(r.passed for r in results.values())
        status = "✅ ALL PASSED" if all_passed else "⚠️  ISSUES FOUND"
        lines.append(f"Overall Status: {status}")
        lines.append("")

        # Per-agent reports
        for agent_name, result in results.items():
            lines.append("-" * 80)
            lines.append(f"Agent: {agent_name}")
            lines.append("-" * 80)

            m = result.metrics

            # Status indicator
            status_icon = "✅" if result.passed else "❌"
            lines.append(f"Status: {status_icon} {'PASSED' if result.passed else 'FAILED'}")
            lines.append("")

            # Metrics
            lines.append("Signal Quality Metrics:")
            lines.append(f"  Total Votes:        {m.total_votes}")
            lines.append(f"  Avg Confidence:     {m.avg_confidence:.2f} (min: {m.min_confidence:.2f}, max: {m.max_confidence:.2f})")
            lines.append(f"  Avg Quality:        {m.avg_quality:.2f}")
            lines.append(f"  Vote Distribution:  {m.votes_up} UP / {m.votes_down} DOWN")

            if m.total_votes > 0:
                lines.append(f"  Low Quality Votes:  {m.low_quality_votes} ({m.low_quality_votes/m.total_votes:.1%})")
                lines.append(f"  Stale Data Votes:   {m.stale_votes} ({m.stale_votes/m.total_votes:.1%})")
                lines.append(f"  API Errors:         {m.api_errors} ({m.api_errors/m.total_votes:.1%})")

            lines.append(f"  Data Sources:       {', '.join(m.data_sources_active) if m.data_sources_active else 'None detected'}")
            lines.append("")

            # Issues
            if result.issues:
                lines.append("Issues:")
                for issue in result.issues:
                    lines.append(f"  ⚠️  {issue}")
                lines.append("")

            # Recommendations
            if result.recommendations:
                lines.append("Recommendations:")
                for rec in result.recommendations:
                    lines.append(f"  💡 {rec}")
                lines.append("")

        lines.append("=" * 80)
        lines.append("Validation Criteria:")
        lines.append(f"  - Minimum votes: {self.MIN_VOTES}")
        lines.append(f"  - Minimum average quality: {self.MIN_AVG_QUALITY}")
        lines.append(f"  - Max low-quality percentage: {self.MAX_LOW_QUALITY_PCT:.0%}")
        lines.append(f"  - Max stale data percentage: {self.MAX_STALE_PCT:.0%}")
        lines.append(f"  - Max API error rate: 10%")
        lines.append("=" * 80)

        return "\n".join(lines)

    def check_api_health(self) -> Dict[str, Dict[str, any]]:
        """
        Check health of APIs used by Week 3 agents.

        Returns:
            Dict mapping agent to API health status
        """
        health = {}

        # OnChainAgent health check
        onchain_health = {
            'agent': 'OnChainAgent',
            'apis': {},
            'overall_status': 'unknown'
        }

        # Check if Whale Alert API key is configured
        whale_alert_key = os.environ.get('WHALE_ALERT_API_KEY')
        onchain_health['apis']['WhaleAlert'] = {
            'configured': bool(whale_alert_key),
            'status': 'ready' if whale_alert_key else 'missing_key'
        }

        # Check if Etherscan API key is configured (fallback)
        etherscan_key = os.environ.get('ETHERSCAN_API_KEY')
        onchain_health['apis']['Etherscan'] = {
            'configured': bool(etherscan_key),
            'status': 'ready' if etherscan_key else 'missing_key'
        }

        onchain_health['overall_status'] = 'healthy' if (whale_alert_key or etherscan_key) else 'degraded'
        health['OnChainAgent'] = onchain_health

        # SocialSentimentAgent health check
        social_health = {
            'agent': 'SocialSentimentAgent',
            'apis': {},
            'overall_status': 'unknown'
        }

        # Check Twitter API v2
        twitter_bearer = os.environ.get('TWITTER_BEARER_TOKEN')
        social_health['apis']['Twitter'] = {
            'configured': bool(twitter_bearer),
            'status': 'ready' if twitter_bearer else 'missing_key'
        }

        # Check Reddit API
        reddit_id = os.environ.get('REDDIT_CLIENT_ID')
        reddit_secret = os.environ.get('REDDIT_CLIENT_SECRET')
        social_health['apis']['Reddit'] = {
            'configured': bool(reddit_id and reddit_secret),
            'status': 'ready' if (reddit_id and reddit_secret) else 'missing_key'
        }

        # Google Trends (no key required)
        social_health['apis']['GoogleTrends'] = {
            'configured': True,
            'status': 'ready'
        }

        active_sources = sum(1 for api in social_health['apis'].values() if api['status'] == 'ready')
        if active_sources >= 2:
            social_health['overall_status'] = 'healthy'
        elif active_sources == 1:
            social_health['overall_status'] = 'degraded'
        else:
            social_health['overall_status'] = 'critical'

        health['SocialSentimentAgent'] = social_health

        return health

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Week 3 agent signal quality')
    parser.add_argument('--db', default='simulation/trade_journal.db', help='Path to trade journal database')
    parser.add_argument('--api-health', action='store_true', help='Check API health status')

    args = parser.parse_args()

    validator = Week3Validator(args.db)

    try:
        if args.api_health:
            # API health check
            import os
            health = validator.check_api_health()

            print("=" * 80)
            print("API Health Check")
            print("=" * 80)
            print()

            for agent_name, status in health.items():
                print(f"{agent_name}: {status['overall_status'].upper()}")
                for api_name, api_status in status['apis'].items():
                    icon = "✅" if api_status['status'] == 'ready' else "❌"
                    print(f"  {icon} {api_name}: {api_status['status']}")
                print()
        else:
            # Signal quality validation
            report = validator.generate_report()
            print(report)

    finally:
        validator.close()


if __name__ == '__main__':
    main()
