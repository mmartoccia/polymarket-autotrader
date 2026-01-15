#!/usr/bin/env python3
"""
TimePatternAgent - Votes based purely on historical time-dependent patterns.

Uses PatternQueryService to query win rates for current hour/crypto/direction.
Only votes if pattern has sufficient statistical confidence.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from dataclasses import dataclass

from analysis.pattern_query_service import get_pattern_service, PatternSignal
from agents.base_agent import BaseAgent, Vote as BaseVote


@dataclass
class Vote:
    """Simple vote structure for TimePatternAgent.vote() method."""
    direction: str
    confidence: float
    reasoning: str


class TimePatternAgent(BaseAgent):
    """
    Agent that votes based purely on historical time-dependent patterns.

    Uses PatternQueryService to query win rates for current hour/crypto/direction.
    Only votes if pattern has sufficient statistical confidence.

    Example:
        >>> agent = TimePatternAgent()
        >>> vote = agent.vote('xrp', 'Up', 9)  # 9am UTC
        >>> if vote:
        ...     print(f"{vote.direction} (confidence: {vote.confidence:.0%})")
        ...     print(f"Reasoning: {vote.reasoning}")
    """

    def __init__(self, name: str = "TimePatternAgent", weight: float = 1.0):
        """
        Initialize TimePatternAgent.

        Args:
            name: Agent name for identification
            weight: Agent weight (used by coordinator for vote weighting)
        """
        super().__init__(name, weight)
        self.pattern_service = get_pattern_service()

        # Configuration
        self.min_confidence = 'moderate'  # Require at least moderate confidence
        self.min_signal_strength = 0.55   # Only vote if signal > 55%
        self.min_edge = 0.05              # Minimum 5% edge over random

    def vote(self, crypto: str, direction: str, hour: int) -> Optional[Vote]:
        """
        Vote on whether to bet crypto in given direction at current hour.

        Args:
            crypto: 'btc', 'eth', 'sol', 'xrp' (case-insensitive)
            direction: 'Up' or 'Down'
            hour: Current UTC hour (0-23)

        Returns:
            Vote if pattern is significant, None if abstain

        Example:
            >>> agent = TimePatternAgent()
            >>> vote = agent.vote('xrp', 'Up', 9)  # Known strong pattern
            >>> print(vote.reasoning)
            📈 XRP Up @ 09:00 UTC: 68.8% historical win rate (+18.8% edge, n=32) ✓✓
        """
        # Query historical pattern
        pattern = self.pattern_service.query_pattern(crypto, hour, direction)

        # Check if pattern meets minimum requirements
        if not self._meets_requirements(pattern):
            return None  # Abstain

        # Format reasoning
        reasoning = self._format_reasoning(pattern)

        return Vote(
            direction=direction,
            confidence=pattern.signal_strength,
            reasoning=reasoning
        )

    def _meets_requirements(self, pattern: PatternSignal) -> bool:
        """Check if pattern meets minimum voting requirements."""
        # Must have sufficient confidence level
        confidence_ok = pattern.confidence in ['high', 'moderate']

        # Must have sufficient signal strength
        strength_ok = pattern.signal_strength >= self.min_signal_strength

        # Must have sufficient edge over random
        edge_ok = abs(pattern.edge) >= self.min_edge

        return confidence_ok and strength_ok and edge_ok

    def _format_reasoning(self, pattern: PatternSignal) -> str:
        """Format human-readable reasoning for vote."""
        emoji = "📈" if pattern.direction == "Up" else "📉"
        confidence_emoji = {
            'high': '✓✓',
            'moderate': '✓',
            'low': '~',
            'insufficient': '✗'
        }.get(pattern.confidence, '?')

        return (
            f"{emoji} {pattern.crypto.upper()} {pattern.direction} @ {pattern.hour:02d}:00 UTC: "
            f"{pattern.win_rate:.1%} historical win rate "
            f"({pattern.edge:+.1%} edge, n={pattern.sample_size}) {confidence_emoji}"
        )

    def analyze(self, crypto: str, epoch: int, data: dict) -> Optional[BaseVote]:
        """
        Analyze market and return vote (coordinator interface).

        This is the standard interface that DecisionEngine expects.
        Extracts hour from data and checks both Up and Down patterns,
        voting for whichever direction has stronger historical signal.

        Args:
            crypto: Crypto symbol ('btc', 'eth', 'sol', 'xrp')
            epoch: Current epoch timestamp
            data: Trading context dict with keys:
                - 'time_in_epoch': seconds into epoch (optional)
                - 'hour': UTC hour 0-23 (optional, calculated from epoch if missing)

        Returns:
            BaseVote if pattern is strong enough, None if abstain

        Example:
            >>> agent = TimePatternAgent()
            >>> vote = agent.analyze('xrp', 1768440300, {'hour': 9})
            >>> if vote:
            ...     print(f"{vote.direction} (confidence: {vote.confidence:.2f})")
        """
        # Extract hour from data or calculate from epoch
        if 'hour' in data:
            hour = data['hour']
        else:
            # Calculate UTC hour from epoch timestamp
            from datetime import datetime
            dt = datetime.utcfromtimestamp(epoch)
            hour = dt.hour

        # Query both Up and Down patterns
        up_pattern = self.pattern_service.query_pattern(crypto, hour, 'Up')
        down_pattern = self.pattern_service.query_pattern(crypto, hour, 'Down')

        # Check which pattern is stronger and meets requirements
        up_valid = self._meets_requirements(up_pattern)
        down_valid = self._meets_requirements(down_pattern)

        # Choose strongest pattern
        if up_valid and down_valid:
            # Both valid - pick stronger one
            if up_pattern.signal_strength >= down_pattern.signal_strength:
                pattern = up_pattern
            else:
                pattern = down_pattern
        elif up_valid:
            pattern = up_pattern
        elif down_valid:
            pattern = down_pattern
        else:
            # Neither pattern meets requirements
            return None

        # Convert to BaseVote format expected by coordinator
        reasoning = self._format_reasoning(pattern)

        return BaseVote(
            direction=pattern.direction,
            confidence=pattern.signal_strength,
            quality=pattern.signal_strength,  # For time patterns, quality = strength
            agent_name=self.name,
            reasoning=reasoning,
            details={
                'win_rate': pattern.win_rate,
                'edge': pattern.edge,
                'sample_size': pattern.sample_size,
                'p_value': pattern.p_value,
                'statistical_confidence': pattern.confidence,
                'hour': hour
            }
        )

    def get_best_hour_for_crypto(self, crypto: str, direction: str) -> Optional[tuple]:
        """
        Get the best hour to bet crypto in given direction.

        Args:
            crypto: Crypto symbol ('btc', 'eth', 'sol', 'xrp')
            direction: 'Up' or 'Down'

        Returns:
            Tuple of (hour, signal_strength) with highest signal, or None if no good hours

        Example:
            >>> agent = TimePatternAgent()
            >>> result = agent.get_best_hour_for_crypto('xrp', 'Up')
            >>> if result:
            ...     hour, strength = result
            ...     print(f"Best hour: {hour:02d}:00 UTC (strength: {strength:.0%})")
        """
        best_hour = None
        best_strength = 0.0

        for hour in range(24):
            pattern = self.pattern_service.query_pattern(crypto, hour, direction)

            if self._meets_requirements(pattern):
                if pattern.signal_strength > best_strength:
                    best_hour = hour
                    best_strength = pattern.signal_strength

        return (best_hour, best_strength) if best_hour is not None else None

    def get_hourly_summary(self, crypto: str, direction: str) -> dict:
        """
        Get summary of all hours for a crypto/direction combination.

        Args:
            crypto: Crypto symbol
            direction: 'Up' or 'Down'

        Returns:
            Dict mapping hour -> PatternSignal

        Example:
            >>> agent = TimePatternAgent()
            >>> summary = agent.get_hourly_summary('xrp', 'Up')
            >>> for hour, signal in summary.items():
            ...     if signal.confidence in ['high', 'moderate']:
            ...         print(f"{hour:02d}:00 - {signal.win_rate:.1%} ({signal.confidence})")
        """
        summary = {}
        for hour in range(24):
            summary[hour] = self.pattern_service.query_pattern(crypto, hour, direction)
        return summary

    def get_all_opportunities(self, min_edge: float = 0.10) -> list:
        """
        Get all crypto/hour/direction combinations with strong patterns.

        Args:
            min_edge: Minimum edge required (default 10pp = 10% above 50%)

        Returns:
            List of PatternSignals sorted by edge (descending)

        Example:
            >>> agent = TimePatternAgent()
            >>> opportunities = agent.get_all_opportunities(min_edge=0.10)
            >>> for sig in opportunities[:5]:
            ...     print(f"{sig.crypto.upper()} {sig.direction} @ {sig.hour:02d}:00: {sig.win_rate:.1%}")
        """
        return self.pattern_service.get_best_opportunities(
            min_edge=min_edge,
            min_confidence=self.min_confidence
        )


# CLI interface for testing
if __name__ == '__main__':
    print("=" * 80)
    print(" " * 25 + "TIME PATTERN AGENT TEST")
    print("=" * 80)
    print()

    agent = TimePatternAgent()

    # Test 1: Vote on known strong pattern (XRP 9am Up)
    print("Test 1: XRP Up at 9am (expected: strong vote)")
    print("-" * 80)
    vote = agent.vote('xrp', 'Up', 9)
    if vote:
        print(f"✓ VOTE: {vote.direction}")
        print(f"  Confidence: {vote.confidence:.1%}")
        print(f"  Reasoning: {vote.reasoning}")
    else:
        print("✗ ABSTAIN (no strong pattern)")
    print()

    # Test 2: Vote on weak pattern (BTC 3am Up)
    print("Test 2: BTC Up at 3am (expected: abstain)")
    print("-" * 80)
    vote = agent.vote('btc', 'Up', 3)
    if vote:
        print(f"✓ VOTE: {vote.direction}")
        print(f"  Confidence: {vote.confidence:.1%}")
        print(f"  Reasoning: {vote.reasoning}")
    else:
        print("✗ ABSTAIN (no strong pattern)")
    print()

    # Test 3: Get best hour for each crypto (Up direction)
    print("Test 3: Best hour for UP direction per crypto")
    print("-" * 80)
    for crypto in ['btc', 'eth', 'sol', 'xrp']:
        result = agent.get_best_hour_for_crypto(crypto, 'Up')
        if result:
            hour, strength = result
            print(f"{crypto.upper()}: {hour:02d}:00 UTC (strength: {strength:.1%})")
        else:
            print(f"{crypto.upper()}: No strong patterns found")
    print()

    # Test 4: Get all opportunities
    print("Test 4: All opportunities with >10% edge")
    print("-" * 80)
    opportunities = agent.get_all_opportunities(min_edge=0.10)
    if opportunities:
        print(f"Found {len(opportunities)} strong patterns:\n")
        for i, sig in enumerate(opportunities[:10], 1):
            emoji = "📈" if sig.direction == "Up" else "📉"
            conf_emoji = "✓✓" if sig.confidence == 'high' else "✓"
            print(f"{i}. {emoji} {sig.crypto.upper()} {sig.direction} @ {sig.hour:02d}:00 UTC: "
                  f"{sig.win_rate:.1%} ({sig.edge:+.1%} edge, n={sig.sample_size}) {conf_emoji}")
    else:
        print("No strong patterns found")
    print()

    # Test 5: Hourly summary for XRP Up
    print("Test 5: Hourly summary for XRP Up (showing only significant hours)")
    print("-" * 80)
    summary = agent.get_hourly_summary('xrp', 'Up')
    print(f"{'Hour':<6} {'Win Rate':<10} {'Edge':<10} {'Confidence':<15} {'Sample':<8}")
    print("-" * 80)
    for hour in range(24):
        sig = summary[hour]
        if sig.confidence in ['high', 'moderate']:
            print(f"{hour:02d}:00  {sig.win_rate:<10.1%} {sig.edge:+10.1%} "
                  f"{sig.confidence:<15} {sig.sample_size:<8}")
    print()

    print("=" * 80)
    print("Time Pattern Agent test complete!")
    print("=" * 80)
