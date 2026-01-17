#!/usr/bin/env python3
"""
Streak Agent - Mean Reversion After Consecutive Same-Direction Epochs

Based on pattern discovery analysis (scripts/pattern_discovery.py):
- After 3+ consecutive UPs: Only 40.9% chance of another UP (predict DOWN)
- After 5+ consecutive DOWNs: Only 43.4% chance of another DOWN (predict UP)

This agent tracks recent epoch outcomes and votes for mean reversion
when streaks exceed thresholds.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Configuration
STREAK_THRESHOLD_UP = 3    # After 3+ consecutive UPs, vote DOWN
STREAK_THRESHOLD_DOWN = 5  # After 5+ consecutive DOWNs, vote UP
MAX_LOOKBACK_EPOCHS = 20   # How many epochs to track

# Mean reversion probabilities (from pattern discovery)
MEAN_REVERSION_PROB_AFTER_UP = 0.591  # 59.1% chance of DOWN after 3+ UPs
MEAN_REVERSION_PROB_AFTER_DOWN = 0.566  # 56.6% chance of UP after 5+ DOWNs


@dataclass
class Vote:
    direction: str          # "Up", "Down", or "Neutral"
    confidence: float       # 0.0 to 1.0
    quality: float          # Signal quality 0.0 to 1.0
    agent_name: str
    reasoning: str
    details: Dict

    def weighted_score(self, weight: float = 1.0) -> float:
        return self.confidence * self.quality * weight


class StreakAgent:
    """
    Tracks consecutive epoch outcomes and votes for mean reversion.

    Strategy:
    - After 3+ consecutive UP epochs, vote DOWN (mean reversion)
    - After 5+ consecutive DOWN epochs, vote UP (mean reversion)
    - Otherwise, abstain (no edge)
    """

    def __init__(self):
        self.name = "StreakAgent"
        self.state_file = "state/streak_history.json"
        self.streak_history: Dict[str, List[Dict]] = {}  # crypto -> list of epoch outcomes
        self._load_state()

    def _load_state(self):
        """Load historical streak data from state file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    self.streak_history = json.load(f)
                logger.info(f"[StreakAgent] Loaded {sum(len(v) for v in self.streak_history.values())} historical outcomes")
        except Exception as e:
            logger.warning(f"[StreakAgent] Could not load state: {e}")
            self.streak_history = {}

    def _save_state(self):
        """Save streak history to state file."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.streak_history, f, indent=2)
        except Exception as e:
            logger.warning(f"[StreakAgent] Could not save state: {e}")

    def record_outcome(self, crypto: str, epoch_start: int, outcome: str):
        """
        Record an epoch outcome for streak tracking.

        Args:
            crypto: e.g., "BTC", "ETH"
            epoch_start: Unix timestamp of epoch start
            outcome: "Up" or "Down"
        """
        if crypto not in self.streak_history:
            self.streak_history[crypto] = []

        # Add new outcome
        self.streak_history[crypto].append({
            'epoch_start': epoch_start,
            'outcome': outcome,
            'recorded_at': int(time.time())
        })

        # Keep only recent epochs
        self.streak_history[crypto] = self.streak_history[crypto][-MAX_LOOKBACK_EPOCHS:]

        self._save_state()
        logger.info(f"[StreakAgent] Recorded {crypto} epoch {epoch_start}: {outcome}")

    def get_current_streak(self, crypto: str) -> Tuple[str, int]:
        """
        Get the current streak direction and length for a crypto.

        Returns:
            Tuple of (direction, length) e.g., ("Up", 3) or ("Down", 5)
        """
        if crypto not in self.streak_history or not self.streak_history[crypto]:
            return ("None", 0)

        # Get outcomes in chronological order
        outcomes = [o['outcome'] for o in self.streak_history[crypto]]

        if not outcomes:
            return ("None", 0)

        # Count consecutive outcomes from the end
        last_outcome = outcomes[-1]
        streak_length = 0

        for outcome in reversed(outcomes):
            if outcome == last_outcome:
                streak_length += 1
            else:
                break

        return (last_outcome, streak_length)

    def get_streak_from_binance(self, crypto: str, lookback_epochs: int = 10) -> Tuple[str, int]:
        """
        Fetch recent epoch outcomes from Binance to calculate current streak.

        This is used for live trading when we don't have enough local history.
        """
        try:
            symbol = f"{crypto}USDT"
            url = f"https://api.binance.com/api/v3/klines"

            # Fetch 15-minute candles
            params = {
                'symbol': symbol,
                'interval': '15m',
                'limit': lookback_epochs + 1  # +1 for current incomplete epoch
            }

            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                return ("None", 0)

            klines = resp.json()

            # Determine outcomes (skip current incomplete candle)
            outcomes = []
            for k in klines[:-1]:  # Skip last (incomplete)
                open_price = float(k[1])
                close_price = float(k[4])
                outcomes.append("Up" if close_price > open_price else "Down")

            if not outcomes:
                return ("None", 0)

            # Count streak from the end
            last_outcome = outcomes[-1]
            streak_length = 0

            for outcome in reversed(outcomes):
                if outcome == last_outcome:
                    streak_length += 1
                else:
                    break

            return (last_outcome, streak_length)

        except Exception as e:
            logger.warning(f"[StreakAgent] Binance fetch error: {e}")
            return ("None", 0)

    def vote(self, market_context: Dict) -> Vote:
        """
        Generate a vote based on current streak status.

        Args:
            market_context: Dict containing:
                - crypto: str (e.g., "BTC")
                - current_price: float
                - epoch_start: int (unix timestamp)
        """
        crypto = market_context.get('crypto', '')

        if not crypto:
            return Vote(
                direction="Neutral",
                confidence=0.0,
                quality=0.0,
                agent_name=self.name,
                reasoning="No crypto specified",
                details={}
            )

        # Get current streak (try Binance first for most accurate data)
        streak_dir, streak_len = self.get_streak_from_binance(crypto)

        # Fallback to local state if Binance fails
        if streak_dir == "None":
            streak_dir, streak_len = self.get_current_streak(crypto)

        details = {
            'crypto': crypto,
            'streak_direction': streak_dir,
            'streak_length': streak_len,
            'up_threshold': STREAK_THRESHOLD_UP,
            'down_threshold': STREAK_THRESHOLD_DOWN
        }

        # Mean reversion logic
        if streak_dir == "Up" and streak_len >= STREAK_THRESHOLD_UP:
            # After consecutive UPs, expect DOWN
            confidence = min(0.3 + (streak_len - STREAK_THRESHOLD_UP) * 0.05, 0.60)
            quality = MEAN_REVERSION_PROB_AFTER_UP

            return Vote(
                direction="Down",
                confidence=confidence,
                quality=quality,
                agent_name=self.name,
                reasoning=f"Mean reversion: {streak_len} consecutive UPs, expect DOWN (59.1% historical)",
                details=details
            )

        elif streak_dir == "Down" and streak_len >= STREAK_THRESHOLD_DOWN:
            # After consecutive DOWNs, expect UP
            confidence = min(0.3 + (streak_len - STREAK_THRESHOLD_DOWN) * 0.05, 0.60)
            quality = MEAN_REVERSION_PROB_AFTER_DOWN

            return Vote(
                direction="Up",
                confidence=confidence,
                quality=quality,
                agent_name=self.name,
                reasoning=f"Mean reversion: {streak_len} consecutive DOWNs, expect UP (56.6% historical)",
                details=details
            )

        else:
            # No streak signal
            return Vote(
                direction="Neutral",
                confidence=0.0,
                quality=0.0,
                agent_name=self.name,
                reasoning=f"No streak signal ({streak_len} {streak_dir}s, threshold not met)",
                details=details
            )


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    agent = StreakAgent()

    # Test with each crypto
    for crypto in ['BTC', 'ETH', 'SOL', 'XRP']:
        print(f"\n{'='*60}")
        print(f"Testing {crypto}")
        print('='*60)

        # Get streak from Binance
        streak_dir, streak_len = agent.get_streak_from_binance(crypto)
        print(f"Current streak: {streak_len} consecutive {streak_dir}s")

        # Get vote
        vote = agent.vote({'crypto': crypto})
        print(f"Vote: {vote.direction}")
        print(f"Confidence: {vote.confidence:.2f}")
        print(f"Quality: {vote.quality:.2f}")
        print(f"Reasoning: {vote.reasoning}")
