#!/usr/bin/env python3
"""
Simulation Orchestrator

Coordinates multiple shadow strategies running in parallel.
Broadcasts market data to all strategies, tracks outcomes, generates comparison reports.
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional

sys.path.append(str(Path(__file__).parent.parent))

from .shadow_strategy import ShadowStrategy
from .strategy_configs import StrategyConfig
from .trade_journal import TradeJournalDB

log = logging.getLogger(__name__)


class SimulationOrchestrator:
    """
    Coordinates multiple shadow trading strategies.
    
    Responsibilities:
    - Initialize shadow strategies from configs
    - Broadcast market data to all strategies
    - Log decisions and trades to database
    - Handle outcome resolution
    - Generate performance comparisons
    """
    
    def __init__(self, strategies: List[StrategyConfig], 
                 db_path: str = 'simulation/trade_journal.db',
                 starting_balance: float = 100.0):
        """
        Initialize orchestrator with shadow strategies.
        
        Args:
            strategies: List of StrategyConfig to run
            db_path: Path to SQLite trade journal database
            starting_balance: Starting balance for each shadow strategy
        """
        self.strategies: Dict[str, ShadowStrategy] = {}
        self.db = TradeJournalDB(db_path)
        self.starting_balance = starting_balance
        
        # Initialize shadow strategies (skip live bot config)
        for config in strategies:
            if not config.is_live:
                strategy = ShadowStrategy(config, starting_balance=starting_balance)
                self.strategies[strategy.name] = strategy
                self.db.register_strategy(config)
        
        if self.strategies:
            print("="*80)
            print(f"SHADOW TRADING INITIALIZED - {len(self.strategies)} strategies")
            print("-"*80)
            for name in self.strategies.keys():
                print(f"  • {name}")
            print("="*80)

            # Restore unresolved positions from database
            self._restore_open_positions()
        else:
            print("[Shadow Trading] No shadow strategies configured")
    
    def on_market_data(self, crypto: str, epoch: int, market_data: dict) -> List[dict]:
        """
        Called when new market data arrives (every scan cycle).
        Broadcasts to all shadow strategies.
        
        Args:
            crypto: Cryptocurrency (btc, eth, sol, xrp)
            epoch: Current epoch timestamp
            market_data: Market data dict with keys:
                - prices: Multi-exchange prices
                - orderbook: Current orderbook
                - positions: Open positions
                - balance: Current balance
                - time_in_epoch: Seconds into epoch
                - rsi: Current RSI
                - regime: Market regime
                - mode: Trading mode
        
        Returns:
            List of decision dicts from all strategies
        """
        decisions = []
        
        for name, strategy in self.strategies.items():
            # Get decision from strategy
            decision = strategy.make_decision(crypto, epoch, market_data)
            decisions.append(decision)
            
            # Log decision to database
            decision_id = self.db.log_decision(
                strategy=decision['strategy'],
                crypto=decision['crypto'],
                epoch=decision['epoch'],
                should_trade=decision['should_trade'],
                direction=decision['direction'],
                confidence=decision['confidence'],
                weighted_score=decision['weighted_score'],
                reason=decision['reason'],
                balance_before=decision['balance_before']
            )
            
            # Execute trade if decision is positive
            if decision['should_trade']:
                strategy.execute_trade(decision, market_data)

                # Log trade to database (use tuple key)
                position_key = (crypto, epoch)
                if position_key in strategy.positions:
                    pos = strategy.positions[position_key]
                    self.db.log_trade(
                        decision_id=decision_id,
                        strategy=name,
                        crypto=crypto,
                        epoch=epoch,
                        direction=pos.direction,
                        entry_price=pos.entry_price,
                        size=pos.size,
                        shares=pos.shares,
                        confidence=pos.confidence,
                        weighted_score=pos.weighted_score
                    )
        
        return decisions
    
    def on_epoch_resolution(self, crypto: str, epoch: int, outcome: str):
        """
        Called when epoch resolves (win/loss determined).
        Updates all strategies with outcome.
        
        Args:
            crypto: Cryptocurrency
            epoch: Epoch timestamp
            outcome: Actual market direction ("Up" or "Down")
        """
        for name, strategy in self.strategies.items():
            pnl = strategy.resolve_position(crypto, epoch, outcome)
            
            # Log outcome to database if position existed
            if pnl is not None:
                # Find the trade to get predicted direction
                for trade in strategy.trade_history:
                    if trade.crypto == crypto and trade.epoch == epoch:
                        self.db.log_outcome(
                            trade_id=-1,  # Will be linked by strategy/crypto/epoch
                            strategy=name,
                            crypto=crypto,
                            epoch=epoch,
                            predicted_direction=trade.direction,
                            actual_direction=outcome,
                            payout=trade.payout or 0.0,
                            pnl=pnl
                        )
                        
                        # Log performance snapshot after each resolved trade
                        metrics = strategy.get_performance()
                        self.db.log_performance_snapshot(
                            strategy=name,
                            balance=metrics.current_balance,
                            total_trades=metrics.total_trades,
                            wins=metrics.wins,
                            losses=metrics.losses,
                            win_rate=metrics.win_rate,
                            total_pnl=metrics.total_pnl,
                            roi=metrics.roi
                        )
                        break
    
    def get_comparison_report(self) -> Dict[str, any]:
        """
        Generate performance comparison across all strategies.
        
        Returns:
            Dict with keys:
                - strategies: Dict[strategy_name -> PerformanceMetrics]
                - best_strategy: Name of top performer by ROI
                - best_roi: Best ROI value
                - best_win_rate: Best win rate
        """
        metrics = {}
        best_roi = -float('inf')
        best_roi_strategy = None
        best_win_rate = 0.0
        best_win_rate_strategy = None
        
        for name, strategy in self.strategies.items():
            perf = strategy.get_performance()
            metrics[name] = perf
            
            if perf.roi > best_roi:
                best_roi = perf.roi
                best_roi_strategy = name
            
            if perf.win_rate > best_win_rate:
                best_win_rate = perf.win_rate
                best_win_rate_strategy = name
        
        return {
            'strategies': metrics,
            'best_strategy': best_roi_strategy,
            'best_roi': best_roi,
            'best_win_rate_strategy': best_win_rate_strategy,
            'best_win_rate': best_win_rate
        }
    
    def print_comparison_table(self):
        """
        Print terminal table showing all strategies side-by-side.
        """
        report = self.get_comparison_report()
        metrics = report['strategies']
        
        if not metrics:
            print("No shadow strategies running")
            return
        
        print()
        print("="*100)
        print(" "*30 + "SHADOW STRATEGY COMPARISON")
        print("="*100)
        print()
        
        # Table header
        print(f"{'Strategy':<25} {'Balance':<12} {'P&L':<12} {'Trades':<8} {'Win Rate':<10} {'ROI':<10}")
        print("-"*100)
        
        # Sort by ROI (best first)
        sorted_strategies = sorted(metrics.items(), key=lambda x: x[1].roi, reverse=True)
        
        for name, m in sorted_strategies:
            status_emoji = "🟢" if m.total_pnl > 0 else "🔴" if m.total_pnl < 0 else "⚪"
            
            print(f"{status_emoji} {name:<23} "
                  f"${m.current_balance:<11.2f} "
                  f"${m.total_pnl:+11.2f} "
                  f"{m.total_trades:<8} "
                  f"{m.win_rate*100:<9.1f}% "
                  f"{m.roi*100:+9.1f}%")
        
        print()
        print("="*100)
        print(f"🏆 Best ROI: {report['best_strategy']} ({report['best_roi']*100:+.1f}%)")
        print(f"🎯 Best Win Rate: {report['best_win_rate_strategy']} ({report['best_win_rate']*100:.1f}%)")
        print("="*100)
    
    def get_status_summary(self) -> str:
        """
        Get one-line summary of all strategies.
        
        Returns:
            Comma-separated status string
        """
        summaries = [s.get_status_summary() for s in self.strategies.values()]
        return " | ".join(summaries)
    
    def _restore_open_positions(self):
        """
        Restore unresolved positions from database on startup.

        When the bot restarts, all in-memory positions are lost. This method
        queries the database for trades that haven't been resolved yet and
        restores them to the shadow strategies' position dictionaries.
        """
        try:
            import time
            from .shadow_strategy import Position

            current_time = int(time.time())

            # Query all unresolved trades (trades without matching outcomes)
            cursor = self.db.conn.execute("""
                SELECT t.strategy, t.crypto, t.epoch, t.entry_price, t.size,
                       t.shares, t.confidence, t.weighted_score, t.timestamp
                FROM trades t
                LEFT JOIN outcomes o ON t.strategy = o.strategy
                    AND t.crypto = o.crypto
                    AND t.epoch = o.epoch
                WHERE o.id IS NULL
                ORDER BY t.epoch DESC
            """)

            unresolved_trades = cursor.fetchall()
            restored_count = 0

            for row in unresolved_trades:
                strategy_name, crypto, epoch, entry_price, size, shares, confidence, weighted_score, timestamp = row

                # Only restore if strategy exists
                if strategy_name not in self.strategies:
                    continue

                # Skip VERY old positions (> 2 hours) - likely from old sessions
                if (current_time - epoch) > 7200:  # 2 hours
                    log.info(f"[Shadow Restore] Skipping very old position: {strategy_name} {crypto} epoch {epoch} ({(current_time - epoch)//60} min old)")
                    continue

                # Reconstruct position
                position = Position(
                    crypto=crypto,
                    epoch=epoch,
                    direction="Up",  # Will be overridden, direction stored in decision table
                    entry_price=entry_price,
                    size=size,
                    shares=shares,
                    confidence=confidence,
                    weighted_score=weighted_score,
                    timestamp=timestamp
                )

                # Get the actual direction from the decision table
                cursor2 = self.db.conn.execute("""
                    SELECT direction FROM decisions
                    WHERE strategy = ? AND crypto = ? AND epoch = ? AND should_trade = 1
                    LIMIT 1
                """, (strategy_name, crypto, epoch))
                direction_row = cursor2.fetchone()
                if direction_row:
                    position.direction = direction_row[0]

                # Restore position to strategy (use (crypto, epoch) tuple as key)
                strategy = self.strategies[strategy_name]
                strategy.positions[(crypto, epoch)] = position

                # Adjust balance (subtract position size)
                strategy.balance -= size

                restored_count += 1

            if restored_count > 0:
                log.info(f"[Shadow Restore] ✅ Restored {restored_count} unresolved positions from database")
                for name, strategy in self.strategies.items():
                    if strategy.positions:
                        log.info(f"[Shadow Restore]   • {name}: {len(strategy.positions)} open positions")
            else:
                log.info(f"[Shadow Restore] ✅ No unresolved positions to restore")

        except Exception as e:
            log.error(f"[Shadow Restore] Failed to restore positions from database: {e}")
            import traceback
            traceback.print_exc()

    def close(self):
        """Close database connection."""
        self.db.close()


def main():
    """
    Standalone test of orchestrator.
    """
    from .strategy_configs import STRATEGY_LIBRARY
    
    # Test with 3 strategies
    strategies = [
        STRATEGY_LIBRARY['conservative'],
        STRATEGY_LIBRARY['aggressive'],
        STRATEGY_LIBRARY['contrarian_focused']
    ]
    
    orchestrator = SimulationOrchestrator(strategies)
    
    # Simulate market data
    market_data = {
        'prices': {'btc': 94350, 'eth': 3215, 'sol': 144, 'xrp': 2.14},
        'orderbook': {
            'yes': {'price': 0.75},
            'no': {'price': 0.25}
        },
        'positions': [],
        'balance': 100.0,
        'time_in_epoch': 300,
        'rsi': 65.0,
        'regime': 'bull_momentum',
        'mode': 'normal'
    }
    
    # Simulate decisions
    print("\n--- Simulating Market Scan ---")
    decisions = orchestrator.on_market_data('btc', 1705276800, market_data)
    
    print(f"\n{len(decisions)} decisions made:")
    for dec in decisions:
        print(f"  {dec['strategy']}: {dec['should_trade']} ({dec['confidence']:.2f})")
    
    # Simulate outcome
    print("\n--- Simulating Epoch Resolution ---")
    orchestrator.on_epoch_resolution('btc', 1705276800, 'Up')
    
    # Print comparison
    orchestrator.print_comparison_table()
    
    orchestrator.close()


if __name__ == '__main__':
    main()
