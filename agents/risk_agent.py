#!/usr/bin/env python3
"""
Risk Management Expert Agent

Validates trade safety using portfolio limits, position sizing,
correlation protection, and drawdown monitoring. Can VETO trades.
"""

import os
import logging
import requests
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from web3 import Web3

from .base_agent import VetoAgent, Vote

log = logging.getLogger(__name__)


# Risk management constants
MAX_POSITION_USD = 15.0
MIN_BET_USD = 1.10
MAX_DRAWDOWN_PCT = 0.30
MAX_TOTAL_POSITIONS = 4
MAX_SAME_DIRECTION_POSITIONS = 3
MAX_DIRECTIONAL_EXPOSURE_PCT = 0.08  # Max 8% of balance in one direction

# Position sizing tiers (balance_threshold, max_pct)
POSITION_TIERS = [
    (30, 0.15),     # Balance < $30: max 15% per trade
    (75, 0.10),     # Balance $30-75: max 10%
    (150, 0.07),    # Balance $75-150: max 7%
    (float('inf'), 0.05),  # Balance > $150: max 5%
]

# Mode multipliers
MODE_MULTIPLIERS = {
    "aggressive": 1.0,
    "normal": 0.75,
    "conservative": 0.80,
    "defensive": 0.65,
    "recovery": 0.50,
    "halted": 0.0
}

# Daily loss limits
DAILY_LOSS_LIMIT_USD = 30.0
DAILY_LOSS_LIMIT_PCT = 0.20  # 20%


@dataclass
class Position:
    """Represents an open trading position."""
    crypto: str
    direction: str  # "Up" or "Down"
    epoch: int
    token_id: str
    cost: float
    shares: float
    entry_price: float
    open_time: float


class RiskAgent(VetoAgent):
    """
    Risk Management Expert Agent.

    Validates:
    - Portfolio drawdown limits
    - Position sizing constraints
    - Correlation/directional exposure
    - Daily loss limits
    - Balance requirements

    Can VETO any trade that violates risk rules.
    Also provides position sizing recommendations.
    """

    def __init__(self,
                 name: str = "RiskAgent",
                 weight: float = 1.0,
                 usdc_address: str = "",
                 wallet_address: str = "",
                 rpc_url: str = "https://polygon-rpc.com"):
        super().__init__(name, weight)

        self.usdc_address = usdc_address
        self.wallet_address = wallet_address
        self.rpc_url = rpc_url

        self.open_positions: List[Position] = []
        self.peak_balance: float = 0.0
        self.day_start_balance: float = 0.0
        self.current_mode: str = "normal"

        # Initialize Web3 for balance checks
        if usdc_address and wallet_address:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        else:
            self.w3 = None

    def analyze(self, crypto: str, epoch: int, data: dict) -> Vote:
        """
        Analyze risk profile and return vote.

        This agent doesn't predict direction - it evaluates risk/reward.
        Returns Neutral vote with risk assessment.

        Args:
            crypto: Crypto symbol
            epoch: Current epoch
            data: Trading context

        Returns:
            Vote with risk assessment (always Neutral direction)
        """
        balance = data.get('balance', 0)
        positions = data.get('positions', [])

        # Update internal state
        self.open_positions = [self._position_from_dict(p) for p in positions]
        self.current_mode = data.get('mode', 'normal')

        # Calculate risk metrics
        risk_metrics = self._calculate_risk_metrics(balance)

        # Calculate confidence based on risk level
        # Lower risk = higher confidence
        risk_score = risk_metrics['overall_risk']  # 0.0 = safe, 1.0 = dangerous

        confidence = 1.0 - risk_score  # Invert: safe = high confidence

        reasoning = (
            f"Risk Assessment: Portfolio health {(1-risk_score)*100:.0f}%, "
            f"{len(self.open_positions)}/{MAX_TOTAL_POSITIONS} positions, "
            f"drawdown {risk_metrics['drawdown_pct']:.1f}%, "
            f"exposure {risk_metrics['max_exposure_pct']:.0f}%"
        )

        return Vote(
            direction="Neutral",  # Risk agent doesn't predict direction
            confidence=confidence,
            quality=1.0,  # Risk assessment is always high quality
            agent_name=self.name,
            reasoning=reasoning,
            details=risk_metrics
        )

    def can_veto(self, crypto: str, data: dict) -> Tuple[bool, str]:
        """
        Check if this trade should be vetoed for risk reasons.

        Args:
            crypto: Crypto symbol
            data: Trading context with:
                - direction: Proposed trade direction
                - size: Proposed position size
                - balance: Current balance
                - positions: Open positions
                - epoch: Current epoch

        Returns:
            (should_veto, reason): (True, reason) to block, (False, "") to allow
        """
        direction = data.get('direction', '')
        epoch = data.get('epoch', 0)
        balance = data.get('balance', 0)
        positions = data.get('positions', [])

        # Update internal state
        self.open_positions = [self._position_from_dict(p) for p in positions]

        # Check 1: Drawdown limit
        should_veto, reason = self._check_drawdown(balance)
        if should_veto:
            return True, f"Drawdown limit: {reason}"

        # Check 2: Daily loss limit
        should_veto, reason = self._check_daily_limit(balance)
        if should_veto:
            return True, f"Daily loss limit: {reason}"

        # Check 3: Position limits (per crypto)
        should_veto, reason = self._check_position_limits(crypto, epoch)
        if should_veto:
            return True, f"Position limit: {reason}"

        # Check 4: Correlation/directional limits
        should_veto, reason = self._check_correlation_limits(direction, balance)
        if should_veto:
            return True, f"Correlation limit: {reason}"

        # Check 5: Consecutive losses (halted mode)
        if self.current_mode == "halted":
            return True, "Bot is in HALTED mode"

        # Check 6: Regime filter - prevent counter-trend trades
        should_veto, reason = self._check_regime_filter(crypto, direction, data)
        if should_veto:
            return True, f"Regime filter: {reason}"

        # Check 7: Extreme contrarian filter - prevent low-probability gambles
        should_veto, reason = self._check_extreme_contrarian(direction, data)
        if should_veto:
            return True, f"Contrarian filter: {reason}"

        # All checks passed
        return False, ""

    def calculate_position_size(self, signal_strength: float, balance: float,
                               consecutive_losses: int = 0) -> float:
        """
        Calculate optimal position size using Kelly-inspired tiered sizing.

        Args:
            signal_strength: Signal quality (0.0 to 1.0)
            balance: Current account balance
            consecutive_losses: Number of consecutive losses

        Returns:
            Recommended position size in USD
        """
        if balance <= 0:
            return 0.0

        # Get tier-appropriate max percentage
        max_pct = 0.05  # Default fallback
        for threshold, pct in POSITION_TIERS:
            if balance < threshold:
                max_pct = pct
                break

        # Calculate base size from balance
        max_from_balance = balance * max_pct

        # Apply mode multiplier
        mode_multiplier = MODE_MULTIPLIERS.get(self.current_mode, 0.75)
        base_size = max_from_balance * mode_multiplier

        # Adjust for consecutive losses (risk reduction)
        if consecutive_losses >= 4:
            base_size *= 0.50  # 50% after 4 losses
        elif consecutive_losses >= 3:
            base_size *= 0.65  # 65% after 3 losses
        elif consecutive_losses >= 2:
            base_size *= 0.80  # 80% after 2 losses

        # Adjust for signal strength
        size = base_size * (0.7 + 0.3 * signal_strength)

        # Apply absolute maximum
        size = min(size, MAX_POSITION_USD)

        # Check minimum bet
        if size < MIN_BET_USD:
            # Allow minimum bet if within tier limit
            if MIN_BET_USD <= (balance * max_pct):
                return MIN_BET_USD
            return 0.0  # Can't afford minimum

        return size

    def _calculate_risk_metrics(self, balance: float) -> dict:
        """Calculate comprehensive risk metrics."""
        # Drawdown calculation
        drawdown_pct = 0.0
        if self.peak_balance > 0:
            drawdown_pct = (self.peak_balance - balance) / self.peak_balance

        # Position concentration
        up_positions = [p for p in self.open_positions if p.direction == "Up"]
        down_positions = [p for p in self.open_positions if p.direction == "Down"]

        up_exposure = sum(p.cost for p in up_positions)
        down_exposure = sum(p.cost for p in down_positions)

        max_exposure_pct = 0.0
        if balance > 0:
            max_exposure_pct = max(up_exposure, down_exposure) / balance

        # Overall risk score (0.0 = safe, 1.0 = dangerous)
        risk_factors = []

        # Drawdown risk
        if drawdown_pct > MAX_DRAWDOWN_PCT * 0.8:
            risk_factors.append(0.8)  # Near limit
        elif drawdown_pct > MAX_DRAWDOWN_PCT * 0.5:
            risk_factors.append(0.4)  # Half way
        else:
            risk_factors.append(0.1)  # Safe

        # Position count risk
        position_ratio = len(self.open_positions) / MAX_TOTAL_POSITIONS
        risk_factors.append(position_ratio * 0.5)

        # Exposure risk
        if max_exposure_pct > MAX_DIRECTIONAL_EXPOSURE_PCT * 0.8:
            risk_factors.append(0.7)
        else:
            risk_factors.append(max_exposure_pct / MAX_DIRECTIONAL_EXPOSURE_PCT * 0.3)

        overall_risk = sum(risk_factors) / len(risk_factors)

        return {
            'drawdown_pct': drawdown_pct * 100,
            'position_count': len(self.open_positions),
            'up_exposure': up_exposure,
            'down_exposure': down_exposure,
            'max_exposure_pct': max_exposure_pct * 100,
            'overall_risk': overall_risk
        }

    def _check_drawdown(self, balance: float) -> Tuple[bool, str]:
        """Check if drawdown limit exceeded."""
        if self.peak_balance <= 0:
            return False, ""

        drawdown = (self.peak_balance - balance) / self.peak_balance

        if drawdown > MAX_DRAWDOWN_PCT:
            return True, (
                f"{drawdown*100:.1f}% exceeds {MAX_DRAWDOWN_PCT*100}% "
                f"(peak ${self.peak_balance:.2f} → ${balance:.2f})"
            )

        return False, ""

    def _check_daily_limit(self, balance: float) -> Tuple[bool, str]:
        """Check if daily loss limit reached."""
        if self.day_start_balance <= 0:
            return False, ""

        daily_pnl = balance - self.day_start_balance
        loss_usd = -daily_pnl if daily_pnl < 0 else 0

        # Check absolute loss
        if loss_usd > DAILY_LOSS_LIMIT_USD:
            return True, f"${loss_usd:.2f} loss exceeds ${DAILY_LOSS_LIMIT_USD}"

        # Check percentage loss
        if self.day_start_balance > 0:
            pct_loss = loss_usd / self.day_start_balance
            if pct_loss > DAILY_LOSS_LIMIT_PCT:
                return True, f"{pct_loss*100:.1f}% loss exceeds {DAILY_LOSS_LIMIT_PCT*100}%"

        return False, ""

    def _check_position_limits(self, crypto: str, epoch: int) -> Tuple[bool, str]:
        """Check per-crypto and per-epoch position limits."""
        # Check per crypto (only 1 per crypto)
        crypto_positions = [p for p in self.open_positions if p.crypto == crypto]
        if len(crypto_positions) >= 1:
            return True, f"Already have position in {crypto}"

        # Check total positions
        if len(self.open_positions) >= MAX_TOTAL_POSITIONS:
            return True, f"Already have {len(self.open_positions)}/{MAX_TOTAL_POSITIONS} positions"

        return False, ""

    def _check_correlation_limits(self, direction: str, balance: float) -> Tuple[bool, str]:
        """Check correlation and directional exposure limits."""
        # Count positions by direction
        up_positions = [p for p in self.open_positions if p.direction == "Up"]
        down_positions = [p for p in self.open_positions if p.direction == "Down"]

        same_direction = up_positions if direction == "Up" else down_positions

        # Check max same direction
        if len(same_direction) >= MAX_SAME_DIRECTION_POSITIONS:
            return True, f"Already have {len(same_direction)}/{MAX_SAME_DIRECTION_POSITIONS} {direction} positions"

        # Check directional exposure
        direction_exposure = sum(p.cost for p in same_direction)

        if balance > 0:
            exposure_pct = direction_exposure / balance
            if exposure_pct >= MAX_DIRECTIONAL_EXPOSURE_PCT:
                return True, (
                    f"{direction} exposure {exposure_pct*100:.1f}% "
                    f"exceeds {MAX_DIRECTIONAL_EXPOSURE_PCT*100}%"
                )

        return False, ""

    def _check_regime_filter(self, crypto: str, direction: str, data: dict) -> Tuple[bool, str]:
        """
        Check if trade conflicts with strong market regime.

        Prevents counter-trend trades in strong trends:
        - In strong bull trend (>0.5): Don't allow Down bets
        - In strong bear trend (<-0.5): Don't allow Up bets

        This prevents contrarian strategies from fighting strong trends.
        """
        regime = data.get('regime', 0.0)

        # Convert regime to numeric if it's a string
        if isinstance(regime, str):
            regime_lower = regime.lower()
            if 'bull' in regime_lower:
                regime = 0.7  # Strong bull
            elif 'bear' in regime_lower:
                regime = -0.7  # Strong bear
            else:
                regime = 0.0  # Neutral

        # Strong bull trend - veto Down bets
        if regime > 0.5 and direction == "Down":
            return True, f"Strong bull trend ({regime:.2f}) - blocking Down bet"

        # Strong bear trend - veto Up bets
        if regime < -0.5 and direction == "Up":
            return True, f"Strong bear trend ({regime:.2f}) - blocking Up bet"

        return False, ""

    def _check_extreme_contrarian(self, direction: str, data: dict) -> Tuple[bool, str]:
        """
        Prevent extreme contrarian bets without strong consensus.

        Contrarian trading (betting against the crowd) works when:
        1. Market has overreacted emotionally
        2. Technical indicators show reversal brewing
        3. We have information edge the market doesn't

        When entry price is <$0.15 (>85% market consensus against us),
        we need VERY strong confirmation from our agents (>60% weighted consensus).

        Without strong confirmation, this is just gambling on low-probability outcomes.
        """
        orderbook = data.get('orderbook', {})

        # Get entry price for proposed direction
        direction_data = orderbook.get(direction, {})
        entry_price = float(direction_data.get('price', direction_data.get('ask', 0.50)))

        # If entry price is <$0.15, this is extreme contrarian
        # (market thinks this outcome has <15% probability)
        if entry_price < 0.15:
            # Get weighted consensus score
            weighted_score = data.get('weighted_score', 0.0)

            # Require >60% weighted consensus for extreme contrarian bets
            if weighted_score < 0.60:
                return True, (
                    f"Extreme contrarian entry (${entry_price:.2f}, {entry_price*100:.0f}% probability) "
                    f"needs >60% agent consensus (have {weighted_score:.1%})"
                )

        return False, ""

    def _position_from_dict(self, pos_dict: dict) -> Position:
        """Convert position dictionary to Position object."""
        return Position(
            crypto=pos_dict.get('crypto', ''),
            direction=pos_dict.get('direction', ''),
            epoch=pos_dict.get('epoch', 0),
            token_id=pos_dict.get('token_id', ''),
            cost=pos_dict.get('cost', 0.0),
            shares=pos_dict.get('shares', 0.0),
            entry_price=pos_dict.get('entry_price', 0.0),
            open_time=pos_dict.get('open_time', 0.0)
        )

    def record_position(self, position: Position):
        """Add a new position to tracking."""
        self.open_positions.append(position)

    def clear_position(self, crypto: str, epoch: int):
        """Remove resolved position from tracking."""
        self.open_positions = [
            p for p in self.open_positions
            if not (p.crypto == crypto and p.epoch == epoch)
        ]

    def update_peak_balance(self, balance: float):
        """Update peak balance for drawdown tracking."""
        if balance > self.peak_balance:
            self.peak_balance = balance
            self.log.info(f"New peak balance: ${balance:.2f}")

    def reset_daily_tracking(self, balance: float):
        """Reset daily tracking (call at start of day)."""
        self.day_start_balance = balance
        self.log.info(f"Day start balance set to ${balance:.2f}")

    def get_usdc_balance(self) -> Optional[float]:
        """Get current USDC balance from blockchain."""
        if not self.w3 or not self.usdc_address or not self.wallet_address:
            return None

        try:
            # USDC contract balanceOf call
            data = f"0x70a08231000000000000000000000000{self.wallet_address[2:]}"

            result = self.w3.eth.call({
                'to': self.usdc_address,
                'data': data
            })

            balance_wei = int(result.hex(), 16)
            balance_usdc = balance_wei / 1e6  # USDC has 6 decimals

            return balance_usdc

        except Exception as e:
            self.log.error(f"Error fetching USDC balance: {e}")
            return None
