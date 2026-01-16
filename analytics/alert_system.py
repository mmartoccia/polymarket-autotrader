#!/usr/bin/env python3
"""
Alert System Module
===================

Detects performance degradation and unusual patterns, sending alerts to prevent losses.

Alert conditions:
- Win rate drops below 50% in last 20 trades
- Balance drops 20% from peak
- Shadow strategy outperforms live by 10%+ (with 100+ trades)
- Daily loss limit exceeded ($30 or 20% of balance)
- Agent consensus failure (multiple low-confidence decisions)

Usage:
    # Run all checks
    python3 analytics/alert_system.py

    # Test mode - generates test alert
    python3 analytics/alert_system.py --test
"""

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Alert:
    """Alert message."""
    severity: str  # 'critical', 'warning', 'info'
    title: str
    message: str
    timestamp: float

    def __str__(self) -> str:
        emoji = {'critical': '🚨', 'warning': '⚠️', 'info': 'ℹ️'}.get(self.severity, '📢')
        dt = datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        return f"{emoji} [{self.severity.upper()}] {dt} - {self.title}\n{self.message}"


class AlertSystem:
    """Monitors bot performance and sends alerts on degradation."""

    def __init__(
        self,
        db_path: str = "simulation/trade_journal.db",
        state_path: str = "state/trading_state.json",
        alert_log_path: str = "logs/alerts.log"
    ):
        """
        Initialize AlertSystem.

        Args:
            db_path: Path to SQLite trade journal database
            state_path: Path to trading_state.json file
            alert_log_path: Path to alert log file
        """
        self.db_path = Path(db_path)
        self.state_path = Path(state_path)
        self.alert_log_path = Path(alert_log_path)
        self.alerts: List[Alert] = []

        # Ensure logs directory exists
        self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        if not self.state_path.exists():
            raise FileNotFoundError(f"State file not found: {self.state_path}")

    def _load_state(self) -> Dict:
        """Load current trading state from JSON file."""
        with open(self.state_path, 'r') as f:
            return json.load(f)

    def _add_alert(self, severity: str, title: str, message: str):
        """Add an alert to the queue."""
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.now().timestamp()
        )
        self.alerts.append(alert)

    def check_win_rate_drop(self, window: int = 20, threshold: float = 0.50) -> bool:
        """
        Check if win rate in recent trades has dropped below threshold.

        Args:
            window: Number of recent trades to analyze
            threshold: Minimum acceptable win rate (default 50%)

        Returns:
            True if alert triggered, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get recent outcomes for live strategy
        cursor.execute("""
            SELECT
                predicted_direction = actual_direction AS is_win
            FROM outcomes
            WHERE strategy = (SELECT name FROM strategies WHERE is_live = 1 LIMIT 1)
            ORDER BY timestamp DESC
            LIMIT ?
        """, (window,))

        results = cursor.fetchall()
        conn.close()

        if len(results) < window:
            # Not enough data yet
            return False

        wins = sum(1 for (is_win,) in results if is_win)
        win_rate = wins / len(results)

        if win_rate < threshold:
            self._add_alert(
                severity='critical',
                title='Win Rate Below Threshold',
                message=(
                    f"Win rate in last {window} trades: {win_rate:.1%}\n"
                    f"Threshold: {threshold:.1%}\n"
                    f"Wins: {wins}/{len(results)}\n"
                    f"ACTION REQUIRED: Review strategy performance and consider halting trading."
                )
            )
            return True

        return False

    def check_balance_drop(self, threshold_pct: float = 0.20) -> bool:
        """
        Check if balance has dropped significantly from peak.

        Args:
            threshold_pct: Maximum acceptable drawdown (default 20%)

        Returns:
            True if alert triggered, False otherwise
        """
        state = self._load_state()
        current_balance = state.get('current_balance', 0)
        peak_balance = state.get('peak_balance', current_balance)

        if peak_balance <= 0:
            return False

        drawdown = (peak_balance - current_balance) / peak_balance

        if drawdown >= threshold_pct:
            self._add_alert(
                severity='warning',
                title='Balance Drawdown Alert',
                message=(
                    f"Current balance: ${current_balance:.2f}\n"
                    f"Peak balance: ${peak_balance:.2f}\n"
                    f"Drawdown: {drawdown:.1%}\n"
                    f"Threshold: {threshold_pct:.1%}\n"
                    f"ACTION: Monitor closely. Consider reducing position sizes."
                )
            )
            return True

        return False

    def check_shadow_outperformance(self, threshold: float = 0.10, min_trades: int = 100) -> bool:
        """
        Check if any shadow strategy significantly outperforms live.

        Args:
            threshold: Minimum win rate improvement (default 10%)
            min_trades: Minimum trades for significance (default 100)

        Returns:
            True if alert triggered, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get live strategy performance
        cursor.execute("""
            SELECT
                s.name,
                COUNT(o.id) AS total_trades,
                SUM(CASE WHEN o.predicted_direction = o.actual_direction THEN 1 ELSE 0 END) AS wins
            FROM strategies s
            LEFT JOIN outcomes o ON s.name = o.strategy
            WHERE s.is_live = 1
            GROUP BY s.name
        """)

        live_result = cursor.fetchone()
        if not live_result:
            conn.close()
            return False

        live_name, live_trades, live_wins = live_result
        if live_trades < min_trades:
            conn.close()
            return False

        live_win_rate = live_wins / live_trades if live_trades > 0 else 0

        # Get all shadow strategies with sufficient trades
        cursor.execute("""
            SELECT
                s.name,
                COUNT(o.id) AS total_trades,
                SUM(CASE WHEN o.predicted_direction = o.actual_direction THEN 1 ELSE 0 END) AS wins
            FROM strategies s
            LEFT JOIN outcomes o ON s.name = o.strategy
            WHERE s.is_live = 0
            GROUP BY s.name
            HAVING total_trades >= ?
        """, (min_trades,))

        shadow_results = cursor.fetchall()
        conn.close()

        outperformers = []
        for shadow_name, shadow_trades, shadow_wins in shadow_results:
            shadow_win_rate = shadow_wins / shadow_trades if shadow_trades > 0 else 0
            improvement = shadow_win_rate - live_win_rate

            if improvement >= threshold:
                outperformers.append((shadow_name, shadow_win_rate, shadow_trades, improvement))

        if outperformers:
            # Sort by improvement (descending)
            outperformers.sort(key=lambda x: x[3], reverse=True)

            details = "\n".join([
                f"  - {name}: {wr:.1%} win rate ({trades} trades) | +{imp:.1%} improvement"
                for name, wr, trades, imp in outperformers
            ])

            self._add_alert(
                severity='info',
                title='Shadow Strategy Outperforming Live',
                message=(
                    f"Live strategy ({live_name}): {live_win_rate:.1%} win rate ({live_trades} trades)\n"
                    f"\nOutperforming shadow strategies:\n{details}\n\n"
                    f"ACTION: Consider running auto-promoter to evaluate promotion."
                )
            )
            return True

        return False

    def check_daily_loss_limit(self, loss_limit_usd: float = 30.0, loss_limit_pct: float = 0.20) -> bool:
        """
        Check if daily loss limit has been exceeded.

        Args:
            loss_limit_usd: Maximum loss in dollars (default $30)
            loss_limit_pct: Maximum loss percentage (default 20%)

        Returns:
            True if alert triggered, False otherwise
        """
        state = self._load_state()
        daily_pnl = state.get('daily_pnl', 0)
        day_start_balance = state.get('day_start_balance', 0)

        if daily_pnl >= 0:
            # No loss
            return False

        loss_usd = abs(daily_pnl)
        loss_pct = loss_usd / day_start_balance if day_start_balance > 0 else 0

        if loss_usd >= loss_limit_usd or loss_pct >= loss_limit_pct:
            self._add_alert(
                severity='critical',
                title='Daily Loss Limit Exceeded',
                message=(
                    f"Daily P&L: ${daily_pnl:+.2f}\n"
                    f"Loss: ${loss_usd:.2f} ({loss_pct:.1%} of starting balance)\n"
                    f"Limits: ${loss_limit_usd:.2f} or {loss_limit_pct:.1%}\n"
                    f"ACTION REQUIRED: Trading should be halted for the day."
                )
            )
            return True

        return False

    def check_agent_consensus_failure(self, min_confidence: float = 0.30, window: int = 10) -> bool:
        """
        Check if recent decisions have abnormally low confidence.

        Args:
            min_confidence: Minimum expected average confidence (default 30%)
            window: Number of recent decisions to analyze (default 10)

        Returns:
            True if alert triggered, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get recent decisions that resulted in trades
        cursor.execute("""
            SELECT confidence
            FROM decisions
            WHERE strategy = (SELECT name FROM strategies WHERE is_live = 1 LIMIT 1)
              AND should_trade = 1
              AND confidence IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (window,))

        results = cursor.fetchall()
        conn.close()

        if len(results) < window:
            # Not enough data yet
            return False

        confidences = [conf for (conf,) in results]
        avg_confidence = sum(confidences) / len(confidences)

        if avg_confidence < min_confidence:
            self._add_alert(
                severity='warning',
                title='Low Agent Consensus Detected',
                message=(
                    f"Average confidence in last {window} trades: {avg_confidence:.1%}\n"
                    f"Expected minimum: {min_confidence:.1%}\n"
                    f"Confidence range: {min(confidences):.1%} - {max(confidences):.1%}\n"
                    f"ACTION: Review agent performance. Low confidence may indicate poor market conditions."
                )
            )
            return True

        return False

    def run_all_checks(self) -> List[Alert]:
        """
        Run all alert checks.

        Returns:
            List of alerts triggered
        """
        self.alerts = []  # Reset alerts

        try:
            self.check_win_rate_drop(window=20, threshold=0.50)
        except Exception as e:
            print(f"Error checking win rate: {e}", file=sys.stderr)

        try:
            self.check_balance_drop(threshold_pct=0.20)
        except Exception as e:
            print(f"Error checking balance: {e}", file=sys.stderr)

        try:
            self.check_shadow_outperformance(threshold=0.10, min_trades=100)
        except Exception as e:
            print(f"Error checking shadow performance: {e}", file=sys.stderr)

        try:
            self.check_daily_loss_limit(loss_limit_usd=30.0, loss_limit_pct=0.20)
        except Exception as e:
            print(f"Error checking daily loss: {e}", file=sys.stderr)

        try:
            self.check_agent_consensus_failure(min_confidence=0.30, window=10)
        except Exception as e:
            print(f"Error checking agent consensus: {e}", file=sys.stderr)

        return self.alerts

    def send_alerts(self):
        """
        Send alerts by logging to file, printing to stdout, and sending to Telegram.
        """
        if not self.alerts:
            print("✅ No alerts - all systems operational")
            return

        # Log to file
        with open(self.alert_log_path, 'a') as f:
            for alert in self.alerts:
                f.write(str(alert) + "\n\n")

        # Print to stdout
        print(f"\n{'=' * 80}")
        print(f"⚠️  ALERT SYSTEM: {len(self.alerts)} alert(s) triggered")
        print(f"{'=' * 80}\n")

        for alert in self.alerts:
            print(str(alert))
            print()

        print(f"Alerts logged to: {self.alert_log_path}")

        # Send to Telegram
        try:
            # Import here to avoid circular dependencies and allow running without Telegram
            from telegram_bot.telegram_notifier import notify_alert
            TELEGRAM_ENABLED = os.getenv('TELEGRAM_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'

            if TELEGRAM_ENABLED:
                for alert in self.alerts:
                    # Extract recommended action from message if present
                    message_parts = alert.message.split('\n')
                    clean_message = '\n'.join(message_parts)

                    notify_alert(
                        level=alert.severity,
                        title=alert.title,
                        message=clean_message
                    )
                    print(f"  → Sent to Telegram: {alert.severity} - {alert.title}")
        except ImportError:
            # Telegram bot not installed - silently skip
            pass
        except Exception as e:
            # Log error but don't crash alert system
            print(f"⚠️  Warning: Could not send Telegram notifications: {e}", file=sys.stderr)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Alert System - Monitors bot performance and sends alerts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all checks
  python3 analytics/alert_system.py

  # Generate test alert
  python3 analytics/alert_system.py --test
        """
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Generate a test alert'
    )

    parser.add_argument(
        '--db',
        default='simulation/trade_journal.db',
        help='Path to trade journal database (default: simulation/trade_journal.db)'
    )

    parser.add_argument(
        '--state',
        default='state/trading_state.json',
        help='Path to trading state file (default: state/trading_state.json)'
    )

    parser.add_argument(
        '--log',
        default='logs/alerts.log',
        help='Path to alert log file (default: logs/alerts.log)'
    )

    args = parser.parse_args()

    if args.test:
        # Generate test alert
        alert = Alert(
            severity='info',
            title='Test Alert',
            message='This is a test alert. The alert system is working correctly.',
            timestamp=datetime.now().timestamp()
        )
        print(str(alert))

        # Log to file
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(str(alert) + "\n\n")

        print(f"\nTest alert logged to: {log_path}")
        return

    # Run all checks
    try:
        alert_system = AlertSystem(
            db_path=args.db,
            state_path=args.state,
            alert_log_path=args.log
        )

        alert_system.run_all_checks()
        alert_system.send_alerts()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
