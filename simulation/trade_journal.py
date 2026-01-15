#!/usr/bin/env python3
"""
Trade Journal Database

SQLite database for storing all shadow trading decisions, trades, and outcomes.
Provides queryable history for performance analysis and strategy comparison.
"""

import sqlite3
import json
import time
import logging
from typing import List, Dict, Optional, Any
from dataclasses import asdict

from .strategy_configs import StrategyConfig

log = logging.getLogger(__name__)


class TradeJournalDB:
    """
    SQLite database wrapper for trade journaling.
    
    Tables:
        - strategies: Strategy configurations and metadata
        - decisions: Every decision made (trade or skip)
        - trades: Executed trades (real + shadow)
        - outcomes: Resolved outcomes (win/loss)
        - agent_votes: Individual agent votes per decision
        - performance: Aggregated metrics snapshots per strategy
    """
    
    def __init__(self, db_path: str = 'simulation/trade_journal.db'):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access

        # Enable Write-Ahead Logging for better concurrent access
        # Try to enable WAL mode, but don't fail if database is locked
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed
            log.info("[TradeJournal] Enabled WAL mode")
        except sqlite3.OperationalError as e:
            # Database might be locked by another process
            # WAL mode is persistent, so if it was enabled before, we're good
            log.warning(f"[TradeJournal] Could not set WAL mode (database may be locked): {e}")
            log.warning(f"[TradeJournal] Continuing anyway - WAL mode may already be enabled")

        self._create_tables()
    
    def _create_tables(self):
        """Create database schema if not exists."""
        
        # Strategies table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                name TEXT PRIMARY KEY,
                description TEXT,
                config JSON,
                is_live BOOLEAN,
                created TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Decisions table (all trading decisions)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                crypto TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                should_trade BOOLEAN NOT NULL,
                direction TEXT,
                confidence REAL,
                weighted_score REAL,
                reason TEXT,
                balance_before REAL,
                FOREIGN KEY (strategy) REFERENCES strategies(name),
                UNIQUE(strategy, crypto, epoch)
            )
        ''')
        
        # Trades table (executed trades only)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER,
                strategy TEXT NOT NULL,
                crypto TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                shares REAL NOT NULL,
                confidence REAL,
                weighted_score REAL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (strategy) REFERENCES strategies(name),
                FOREIGN KEY (decision_id) REFERENCES decisions(id),
                UNIQUE(strategy, crypto, epoch)
            )
        ''')
        
        # Outcomes table (resolved trades)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                strategy TEXT NOT NULL,
                crypto TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                predicted_direction TEXT NOT NULL,
                actual_direction TEXT NOT NULL,
                payout REAL NOT NULL,
                pnl REAL NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (strategy) REFERENCES strategies(name),
                FOREIGN KEY (trade_id) REFERENCES trades(id),
                UNIQUE(strategy, crypto, epoch)
            )
        ''')
        
        # Agent votes table (individual agent predictions)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS agent_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence REAL NOT NULL,
                quality REAL NOT NULL,
                reasoning TEXT,
                details JSON,
                FOREIGN KEY (decision_id) REFERENCES decisions(id)
            )
        ''')
        
        # Performance snapshots (periodic metrics)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                timestamp REAL NOT NULL,
                balance REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                total_pnl REAL NOT NULL,
                roi REAL NOT NULL,
                FOREIGN KEY (strategy) REFERENCES strategies(name)
            )
        ''')
        
        # Create indexes for common queries
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_decisions_strategy_epoch ON decisions(strategy, epoch)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_trades_strategy_epoch ON trades(strategy, epoch)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_outcomes_strategy ON outcomes(strategy)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_agent_votes_decision ON agent_votes(decision_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_performance_strategy_time ON performance(strategy, timestamp)')
        
        self.conn.commit()
    
    def register_strategy(self, config: StrategyConfig):
        """
        Register new strategy or update existing.

        Args:
            config: StrategyConfig to register
        """
        # Retry with timeout if database is locked
        max_retries = 5
        retry_delay = 0.5  # seconds

        for attempt in range(max_retries):
            try:
                self.conn.execute('''
                    INSERT OR REPLACE INTO strategies (name, description, config, is_live, created, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    config.name,
                    config.description,
                    json.dumps(asdict(config), default=str),
                    config.is_live,
                    config.created.isoformat(),
                    time.time()
                ))
                self.conn.commit()
                return  # Success
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    log.warning(f"[TradeJournal] Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    # Last attempt or different error - just log warning and continue
                    log.warning(f"[TradeJournal] Could not register strategy {config.name}: {e}")
                    log.warning(f"[TradeJournal] Continuing anyway - strategy may already be registered")
                    return
    
    def log_decision(self, strategy: str, crypto: str, epoch: int, 
                    should_trade: bool, direction: Optional[str],
                    confidence: float, weighted_score: float,
                    reason: str, balance_before: float) -> int:
        """
        Log trading decision.
        
        Args:
            strategy: Strategy name
            crypto: Cryptocurrency (btc, eth, sol, xrp)
            epoch: Epoch timestamp
            should_trade: Whether to execute trade
            direction: "Up" or "Down" (None if skip)
            confidence: Average agent confidence (0-1)
            weighted_score: Consensus weighted score (0-1)
            reason: Decision reasoning
            balance_before: Balance before trade
            
        Returns:
            decision_id: ID of inserted decision
        """
        try:
            cursor = self.conn.execute('''
                INSERT INTO decisions 
                (strategy, crypto, epoch, timestamp, should_trade, direction, 
                 confidence, weighted_score, reason, balance_before)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                strategy, crypto, epoch, time.time(), should_trade, direction,
                confidence, weighted_score, reason, balance_before
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Decision already logged (duplicate epoch/crypto/strategy)
            row = self.conn.execute('''
                SELECT id FROM decisions 
                WHERE strategy=? AND crypto=? AND epoch=?
            ''', (strategy, crypto, epoch)).fetchone()
            return row['id'] if row else -1
    
    def log_trade(self, decision_id: int, strategy: str, crypto: str, epoch: int,
                 direction: str, entry_price: float, size: float, shares: float,
                 confidence: float, weighted_score: float) -> int:
        """
        Log executed trade.
        
        Args:
            decision_id: ID of decision that led to trade
            strategy: Strategy name
            crypto: Cryptocurrency
            epoch: Epoch timestamp
            direction: "Up" or "Down"
            entry_price: Entry probability (0-1)
            size: Position size in USD
            shares: Number of shares purchased
            confidence: Average agent confidence
            weighted_score: Consensus score
            
        Returns:
            trade_id: ID of inserted trade
        """
        try:
            cursor = self.conn.execute('''
                INSERT INTO trades 
                (decision_id, strategy, crypto, epoch, direction, entry_price, 
                 size, shares, confidence, weighted_score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                decision_id, strategy, crypto, epoch, direction, entry_price,
                size, shares, confidence, weighted_score, time.time()
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Trade already logged
            row = self.conn.execute('''
                SELECT id FROM trades 
                WHERE strategy=? AND crypto=? AND epoch=?
            ''', (strategy, crypto, epoch)).fetchone()
            return row['id'] if row else -1
    
    def log_outcome(self, trade_id: int, strategy: str, crypto: str, epoch: int,
                   predicted_direction: str, actual_direction: str,
                   payout: float, pnl: float) -> int:
        """
        Log trade outcome after resolution.

        Args:
            trade_id: ID of trade
            strategy: Strategy name
            crypto: Cryptocurrency
            epoch: Epoch timestamp
            predicted_direction: Predicted direction ("Up" or "Down")
            actual_direction: Actual market direction
            payout: Payout amount in USD
            pnl: Profit/loss in USD

        Returns:
            outcome_id: ID of inserted outcome
        """
        try:
            cursor = self.conn.execute('''
                INSERT INTO outcomes
                (trade_id, strategy, crypto, epoch, predicted_direction,
                 actual_direction, payout, pnl, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_id, strategy, crypto, epoch, predicted_direction,
                actual_direction, payout, pnl, time.time()
            ))
            self.conn.commit()

            # EXPLICIT SYNC: Force write to disk (WAL mode already enabled)
            # This ensures outcomes are persisted even if process terminates
            self.conn.execute("SELECT 1")  # Simple query to flush WAL

            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            # Outcome already logged
            log.warning(f"Duplicate outcome for {strategy} {crypto} epoch {epoch}: {e}")
            row = self.conn.execute('''
                SELECT id FROM outcomes
                WHERE strategy=? AND crypto=? AND epoch=?
            ''', (strategy, crypto, epoch)).fetchone()
            return row['id'] if row else -1
        except Exception as e:
            log.error(f"Error logging outcome for {strategy} {crypto} epoch {epoch}: {e}")
            import traceback
            traceback.print_exc()
            return -1
    
    def log_agent_votes(self, decision_id: int, votes: List[Dict[str, Any]]):
        """
        Log individual agent votes for a decision.
        
        Args:
            decision_id: ID of decision
            votes: List of vote dicts with keys: agent_name, direction, confidence, quality, reasoning, details
        """
        for vote in votes:
            self.conn.execute('''
                INSERT INTO agent_votes 
                (decision_id, agent_name, direction, confidence, quality, reasoning, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                decision_id,
                vote.get('agent_name'),
                vote.get('direction'),
                vote.get('confidence'),
                vote.get('quality'),
                vote.get('reasoning', ''),
                json.dumps(vote.get('details', {}))
            ))
        self.conn.commit()
    
    def log_performance_snapshot(self, strategy: str, balance: float, total_trades: int,
                                wins: int, losses: int, win_rate: float,
                                total_pnl: float, roi: float):
        """
        Log performance snapshot for strategy.
        
        Args:
            strategy: Strategy name
            balance: Current balance
            total_trades: Total trades executed
            wins: Number of wins
            losses: Number of losses
            win_rate: Win rate (0-1)
            total_pnl: Total profit/loss
            roi: Return on investment (0-1)
        """
        self.conn.execute('''
            INSERT INTO performance 
            (strategy, timestamp, balance, total_trades, wins, losses, win_rate, total_pnl, roi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (strategy, time.time(), balance, total_trades, wins, losses, win_rate, total_pnl, roi))
        self.conn.commit()
    
    def query_decisions(self, strategy: Optional[str] = None, 
                       start_time: Optional[float] = None,
                       limit: int = 100) -> List[Dict]:
        """
        Query trading decisions.
        
        Args:
            strategy: Filter by strategy name (None = all)
            start_time: Filter by timestamp >= start_time (None = all)
            limit: Maximum results
            
        Returns:
            List of decision dicts
        """
        query = "SELECT * FROM decisions WHERE 1=1"
        params = []
        
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def query_trades(self, strategy: Optional[str] = None,
                    start_time: Optional[float] = None,
                    limit: int = 100) -> List[Dict]:
        """
        Query executed trades.
        
        Args:
            strategy: Filter by strategy (None = all)
            start_time: Filter by timestamp >= start_time
            limit: Maximum results
            
        Returns:
            List of trade dicts
        """
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def query_outcomes(self, strategy: Optional[str] = None,
                      start_time: Optional[float] = None,
                      limit: int = 100) -> List[Dict]:
        """
        Query trade outcomes.
        
        Args:
            strategy: Filter by strategy
            start_time: Filter by timestamp
            limit: Maximum results
            
        Returns:
            List of outcome dicts
        """
        query = "SELECT * FROM outcomes WHERE 1=1"
        params = []
        
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_strategy_performance(self, strategy: str) -> Dict[str, Any]:
        """
        Get aggregated performance metrics for strategy.
        
        Args:
            strategy: Strategy name
            
        Returns:
            Dict with keys: total_trades, wins, losses, win_rate, total_pnl, avg_pnl
        """
        # Get trade count
        trade_count = self.conn.execute('''
            SELECT COUNT(*) as count FROM trades WHERE strategy = ?
        ''', (strategy,)).fetchone()['count']
        
        # Get outcome stats
        outcome_stats = self.conn.execute('''
            SELECT 
                COUNT(*) as resolved,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl
            FROM outcomes 
            WHERE strategy = ?
        ''', (strategy,)).fetchone()
        
        resolved = outcome_stats['resolved'] or 0
        wins = outcome_stats['wins'] or 0
        losses = outcome_stats['losses'] or 0
        total_pnl = outcome_stats['total_pnl'] or 0.0
        avg_pnl = outcome_stats['avg_pnl'] or 0.0
        win_rate = wins / resolved if resolved > 0 else 0.0
        
        return {
            'strategy': strategy,
            'total_trades': trade_count,
            'resolved': resolved,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl
        }
    
    def get_all_strategies_performance(self) -> List[Dict[str, Any]]:
        """
        Get performance metrics for all strategies.
        
        Returns:
            List of performance dicts
        """
        strategies = self.conn.execute('SELECT name FROM strategies').fetchall()
        return [self.get_strategy_performance(row['name']) for row in strategies]
    
    def close(self):
        """Close database connection."""
        self.conn.close()
