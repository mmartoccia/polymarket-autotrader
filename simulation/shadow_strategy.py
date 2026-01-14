#!/usr/bin/env python3
"""
Shadow Strategy - Virtual Trading Engine

Runs hypothetical trading strategies alongside the live bot without placing real orders.
Tracks virtual positions, balance, and performance for strategy comparison.
"""

import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Add parent directory to path to import bot modules
sys.path.append(str(Path(__file__).parent.parent))

from bot.agent_wrapper import AgentSystemWrapper
from .strategy_configs import StrategyConfig


@dataclass
class Position:
    """Virtual position held by shadow strategy."""
    crypto: str
    epoch: int
    direction: str  # "Up" or "Down"
    entry_price: float  # Entry probability (0-1)
    size: float  # USD amount
    shares: float  # Number of shares
    confidence: float  # Agent confidence (0-1)
    weighted_score: float  # Consensus score (0-1)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Trade:
    """Completed trade record."""
    crypto: str
    epoch: int
    direction: str
    entry_price: float
    size: float
    shares: float
    confidence: float
    weighted_score: float
    timestamp: float
    
    # Outcome (filled after resolution)
    outcome: Optional[str] = None  # "Up" or "Down"
    payout: Optional[float] = None
    pnl: Optional[float] = None
    
    @classmethod
    def from_position(cls, pos: Position) -> 'Trade':
        """Create trade from position."""
        return cls(
            crypto=pos.crypto,
            epoch=pos.epoch,
            direction=pos.direction,
            entry_price=pos.entry_price,
            size=pos.size,
            shares=pos.shares,
            confidence=pos.confidence,
            weighted_score=pos.weighted_score,
            timestamp=pos.timestamp
        )


@dataclass
class PerformanceMetrics:
    """Performance metrics for strategy."""
    strategy: str
    starting_balance: float
    current_balance: float
    total_pnl: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    roi: float  # Return on investment (0-1)


class ShadowStrategy:
    """
    Virtual trading strategy that runs alongside live bot.
    
    Makes hypothetical trading decisions using AgentSystemWrapper with
    custom configuration. Tracks virtual positions and performance without
    placing real orders.
    """
    
    def __init__(self, config: StrategyConfig, starting_balance: float = 100.0):
        """
        Initialize shadow strategy.
        
        Args:
            config: StrategyConfig defining strategy parameters
            starting_balance: Starting virtual balance in USD
        """
        self.config = config
        self.name = config.name
        
        # Virtual state
        self.balance = starting_balance
        self.starting_balance = starting_balance
        self.positions: Dict[tuple, Position] = {}  # (crypto, epoch) → Position
        self.trade_history: List[Trade] = []
        
        # Initialize agent system with strategy-specific config
        self.agent_system = AgentSystemWrapper(
            consensus_threshold=config.consensus_threshold,
            min_confidence=config.min_confidence,
            adaptive_weights=config.adaptive_weights,
            enabled=True  # Shadow strategies always "trade" (hypothetically)
        )
        
        # Performance tracking
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        
        print(f"[{self.name}] Initialized with ${starting_balance:.2f} virtual balance")
    
    def make_decision(self, crypto: str, epoch: int, market_data: dict) -> dict:
        """
        Make trading decision for this strategy.
        
        Args:
            crypto: Cryptocurrency (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            market_data: Market data dict with keys:
                - prices: Multi-exchange prices
                - orderbook: Current orderbook
                - positions: Open positions (ignored for shadow)
                - balance: Live bot balance (ignored for shadow)
                - time_in_epoch: Seconds into epoch
                - rsi: Current RSI
                - regime: Market regime
                - mode: Trading mode
        
        Returns:
            Decision dict with keys: should_trade, direction, confidence, 
            weighted_score, reason, balance_before
        """
        # Use strategy's virtual state instead of live bot state
        strategy_data = market_data.copy()
        strategy_data['balance'] = self.balance
        strategy_data['positions'] = []  # Shadow has no real positions
        
        # Get decision from agent system
        should_trade, direction, confidence, reason, weighted_score = \
            self.agent_system.make_decision(
                crypto=crypto,
                epoch=epoch,
                prices=strategy_data['prices'],
                orderbook=strategy_data['orderbook'],
                positions=[],  # Virtual positions don't block trades
                balance=self.balance,
                time_in_epoch=strategy_data.get('time_in_epoch', 0),
                rsi=strategy_data.get('rsi', 50.0),
                regime=strategy_data.get('regime', 'unknown'),
                mode='normal'  # Always use normal mode for shadows
            )
        
        return {
            'strategy': self.name,
            'crypto': crypto,
            'epoch': epoch,
            'timestamp': time.time(),
            'should_trade': should_trade,
            'direction': direction,
            'confidence': confidence,
            'weighted_score': weighted_score,
            'reason': reason,
            'balance_before': self.balance
        }
    
    def execute_trade(self, decision: dict, market_data: dict):
        """
        Execute hypothetical trade (update virtual positions & balance).
        
        Args:
            decision: Decision dict from make_decision()
            market_data: Market data dict with orderbook
        """
        if not decision['should_trade']:
            return
        
        crypto = decision['crypto']
        
        # Check if we already have position for this crypto
        if crypto in self.positions:
            print(f"[{self.name}] Already have {crypto} position, skipping")
            return
        
        # Calculate position size
        consecutive_losses = self._get_recent_loss_streak()
        size = self.agent_system.get_position_size(
            confidence=decision['confidence'],
            balance=self.balance,
            consecutive_losses=consecutive_losses,
            weighted_score=decision['weighted_score']
        )
        
        # Check if we have enough balance
        if size > self.balance:
            print(f"[{self.name}] Insufficient balance (${self.balance:.2f} < ${size:.2f})")
            return
        
        # Get entry price from orderbook
        orderbook = market_data['orderbook']
        if decision['direction'] == 'Up':
            entry_price = orderbook['yes']['price']
        else:
            entry_price = orderbook['no']['price']
        
        shares = size / entry_price
        
        # Create position
        position = Position(
            crypto=crypto,
            epoch=decision['epoch'],
            direction=decision['direction'],
            entry_price=entry_price,
            size=size,
            shares=shares,
            confidence=decision['confidence'],
            weighted_score=decision['weighted_score']
        )
        
        # Update state
        self.balance -= size
        self.positions[(crypto, decision['epoch'])] = position
        self.trade_history.append(Trade.from_position(position))
        self.total_trades += 1
        
        print(f"[{self.name}] TRADE {crypto} {decision['direction']} @ ${entry_price:.2f} | "
              f"${size:.2f} ({shares:.1f} shares) | Balance: ${self.balance:.2f}")
    
    def resolve_position(self, crypto: str, epoch: int, outcome: str) -> Optional[float]:
        """
        Resolve hypothetical position after epoch ends.

        Args:
            crypto: Cryptocurrency
            epoch: Epoch timestamp
            outcome: Actual market direction ("Up" or "Down")

        Returns:
            PnL for this trade (None if no position)
        """
        position_key = (crypto, epoch)
        if position_key not in self.positions:
            return None

        pos = self.positions[position_key]
        
        # Determine win/loss
        won = (pos.direction == outcome)
        
        if won:
            payout = pos.shares * 1.0  # $1.00 per share
            self.balance += payout
            pnl = payout - pos.size
            self.wins += 1
            result_emoji = "✅ WIN"
        else:
            payout = 0.0
            pnl = -pos.size
            self.losses += 1
            result_emoji = "❌ LOSS"
        
        self.total_pnl += pnl
        
        # Update trade history
        for trade in self.trade_history:
            if trade.crypto == crypto and trade.epoch == epoch:
                trade.outcome = outcome
                trade.payout = payout
                trade.pnl = pnl
                break
        
        # Remove position
        del self.positions[position_key]
        
        print(f"[{self.name}] {result_emoji} {crypto} {pos.direction} (actual: {outcome}) | "
              f"PnL: ${pnl:+.2f} | Balance: ${self.balance:.2f}")
        
        return pnl
    
    def _get_recent_loss_streak(self) -> int:
        """Count consecutive recent losses."""
        streak = 0
        for trade in reversed(self.trade_history):
            if trade.outcome is None:
                break  # Unresolved
            if trade.pnl and trade.pnl <= 0:
                streak += 1
            else:
                break
        return streak
    
    def _calculate_avg_win(self) -> float:
        """Calculate average winning trade PnL."""
        winning_trades = [t.pnl for t in self.trade_history if t.pnl and t.pnl > 0]
        if not winning_trades:
            return 0.0
        return sum(winning_trades) / len(winning_trades)
    
    def _calculate_avg_loss(self) -> float:
        """Calculate average losing trade PnL."""
        losing_trades = [t.pnl for t in self.trade_history if t.pnl and t.pnl <= 0]
        if not losing_trades:
            return 0.0
        return sum(losing_trades) / len(losing_trades)
    
    def get_performance(self) -> PerformanceMetrics:
        """
        Get current performance metrics.
        
        Returns:
            PerformanceMetrics dataclass
        """
        resolved = self.wins + self.losses
        win_rate = self.wins / resolved if resolved > 0 else 0.0
        roi = self.total_pnl / self.starting_balance if self.starting_balance > 0 else 0.0
        
        return PerformanceMetrics(
            strategy=self.name,
            starting_balance=self.starting_balance,
            current_balance=self.balance,
            total_pnl=self.total_pnl,
            total_trades=self.total_trades,
            wins=self.wins,
            losses=self.losses,
            win_rate=win_rate,
            avg_win=self._calculate_avg_win(),
            avg_loss=self._calculate_avg_loss(),
            roi=roi
        )
    
    def get_status_summary(self) -> str:
        """Get one-line status summary."""
        metrics = self.get_performance()
        return (f"{self.name}: ${metrics.current_balance:.2f} "
                f"({metrics.total_trades} trades, {metrics.win_rate*100:.0f}% WR, "
                f"{metrics.roi*100:+.1f}% ROI)")
