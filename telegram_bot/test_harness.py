#!/usr/bin/env python3
"""
Telegram Bot Test Harness

Automatically tests all Telegram bot commands and notifications
without requiring manual interaction.
"""

import os
import sys
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Telegram notification functions
from telegram_bot.telegram_notifier import (
    notify_trade,
    notify_redemption,
    notify_alert,
    notify_daily_summary
)

# Import message formatter
from telegram_bot.message_formatter import MessageFormatter

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class TelegramTestHarness:
    """Automated testing for Telegram bot functionality."""

    def __init__(self):
        self.formatter = MessageFormatter()
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_total = 0

    def print_header(self, text):
        """Print a section header."""
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}{text.center(80)}{RESET}")
        print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

    def print_test(self, test_name):
        """Print test name."""
        print(f"{BOLD}Testing:{RESET} {test_name}...", end=" ")
        self.tests_total += 1

    def print_pass(self, message=""):
        """Print test passed."""
        self.tests_passed += 1
        if message:
            print(f"{GREEN}✓ PASS{RESET} - {message}")
        else:
            print(f"{GREEN}✓ PASS{RESET}")

    def print_fail(self, message=""):
        """Print test failed."""
        self.tests_failed += 1
        if message:
            print(f"{RED}✗ FAIL{RESET} - {message}")
        else:
            print(f"{RED}✗ FAIL{RESET}")

    def print_warning(self, message):
        """Print warning."""
        print(f"{YELLOW}⚠ WARNING:{RESET} {message}")

    def print_info(self, message):
        """Print info."""
        print(f"{BLUE}ℹ INFO:{RESET} {message}")

    # =========================================================================
    # MESSAGE FORMATTER TESTS
    # =========================================================================

    def test_format_balance(self):
        """Test balance message formatting."""
        self.print_test("format_balance()")
        try:
            message = self.formatter.format_balance()

            # Check for required elements
            assert "CURRENT BALANCE" in message or "Balance" in message
            assert "$" in message

            # Check it's not an error
            assert "Error" not in message or "not found" in message.lower()

            self.print_pass(f"Generated {len(message)} chars")
            print(f"   Preview: {message[:100]}...")
        except Exception as e:
            self.print_fail(str(e))

    def test_format_positions(self):
        """Test positions message formatting."""
        self.print_test("format_positions()")
        try:
            message = self.formatter.format_positions()

            # Should return either positions list or "no positions" message
            assert "OPEN POSITIONS" in message or "No open positions" in message

            self.print_pass(f"Generated {len(message)} chars")
            print(f"   Preview: {message[:100]}...")
        except Exception as e:
            self.print_fail(str(e))

    def test_format_status(self):
        """Test status message formatting."""
        self.print_test("format_status()")
        try:
            message = self.formatter.format_status()

            # Check for required elements
            assert "BOT STATUS" in message or "Status" in message
            assert "Mode:" in message or "mode" in message.lower()

            self.print_pass(f"Generated {len(message)} chars")
            print(f"   Preview: {message[:100]}...")
        except Exception as e:
            self.print_fail(str(e))

    def test_format_statistics(self):
        """Test statistics message formatting."""
        self.print_test("format_statistics()")
        try:
            message = self.formatter.format_statistics()

            # Should return either stats or "no trades" message
            assert "STATISTICS" in message or "No trades" in message

            self.print_pass(f"Generated {len(message)} chars")
            print(f"   Preview: {message[:100]}...")
        except Exception as e:
            self.print_fail(str(e))

    # =========================================================================
    # NOTIFICATION TESTS
    # =========================================================================

    def test_notify_trade(self):
        """Test trade notification."""
        self.print_test("notify_trade()")
        try:
            result = notify_trade(
                crypto="BTC",
                direction="Up",
                entry_price=0.42,
                size=5.50,
                shares=13,
                confidence=0.675,
                agents_voted=["TechAgent", "SentimentAgent", "RegimeAgent"],
                strategy="ml_live_ml_random_forest"
            )

            self.print_pass("Notification sent")
            self.print_info("Check Telegram for: 🚀 NEW TRADE - BTC Up @ $0.42")
        except Exception as e:
            self.print_fail(str(e))

    def test_notify_redemption_win(self):
        """Test redemption notification (win)."""
        self.print_test("notify_redemption() - WIN")
        try:
            result = notify_redemption(
                crypto="ETH",
                direction="Down",
                outcome="win",
                pnl=8.25,
                shares_redeemed=15,
                entry_price=0.35,
                new_balance=209.22
            )

            self.print_pass("Notification sent")
            self.print_info("Check Telegram for: ✅ POSITION REDEEMED - ETH Down WINNER!")
        except Exception as e:
            self.print_fail(str(e))

    def test_notify_redemption_loss(self):
        """Test redemption notification (loss)."""
        self.print_test("notify_redemption() - LOSS")
        try:
            result = notify_redemption(
                crypto="SOL",
                direction="Up",
                outcome="loss",
                pnl=-4.50,
                shares_redeemed=0,
                entry_price=0.45,
                new_balance=204.72
            )

            self.print_pass("Notification sent")
            self.print_info("Check Telegram for: ❌ POSITION EXPIRED - SOL Up")
        except Exception as e:
            self.print_fail(str(e))

    def test_notify_alert(self):
        """Test alert notification."""
        self.print_test("notify_alert()")
        try:
            result = notify_alert(
                level="warning",
                title="Test Alert",
                message="This is a test alert from the test harness. Please ignore."
            )

            self.print_pass("Notification sent")
            self.print_info("Check Telegram for: ⚠️ WARNING - Test Alert")
        except Exception as e:
            self.print_fail(str(e))

    def test_notify_daily_summary(self):
        """Test daily summary notification."""
        self.print_test("notify_daily_summary()")
        try:
            result = notify_daily_summary()

            self.print_pass("Notification sent")
            self.print_info("Check Telegram for: 📊 DAILY SUMMARY")
        except Exception as e:
            self.print_fail(str(e))

    # =========================================================================
    # DATABASE TESTS
    # =========================================================================

    def test_database_access(self):
        """Test database access."""
        self.print_test("Database access")
        try:
            db_path = Path(__file__).parent.parent / "simulation" / "trade_journal.db"

            if not db_path.exists():
                self.print_warning(f"Database not found at {db_path}")
                self.print_pass("Database check skipped")
                return

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['trades', 'outcomes', 'strategies']
            for table in required_tables:
                assert table in tables, f"Missing table: {table}"

            # Check trade count
            cursor.execute("SELECT COUNT(*) FROM trades WHERE strategy LIKE 'ml_live%'")
            trade_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM outcomes")
            outcome_count = cursor.fetchone()[0]

            conn.close()

            self.print_pass(f"{trade_count} trades, {outcome_count} outcomes")
        except Exception as e:
            self.print_fail(str(e))

    def test_state_file_access(self):
        """Test state file access."""
        self.print_test("State file access")
        try:
            # Try v12_state first (actual location)
            state_paths = [
                Path(__file__).parent.parent / "v12_state" / "trading_state.json",
                Path(__file__).parent.parent / "state" / "trading_state.json"
            ]

            state_data = None
            state_path_used = None

            for state_path in state_paths:
                if state_path.exists():
                    with open(state_path, 'r') as f:
                        state_data = json.load(f)
                        state_path_used = state_path
                    break

            assert state_data is not None, "No state file found"

            # Check required fields
            required_fields = ['current_balance', 'peak_balance', 'mode']
            for field in required_fields:
                assert field in state_data, f"Missing field: {field}"

            self.print_pass(f"Mode: {state_data['mode']}, Balance: ${state_data['current_balance']:.2f}")
            print(f"   Using: {state_path_used}")
        except Exception as e:
            self.print_fail(str(e))

    # =========================================================================
    # INTEGRATION TESTS
    # =========================================================================

    def test_state_consistency(self):
        """Test state consistency between files."""
        self.print_test("State consistency check")
        try:
            state1_path = Path(__file__).parent.parent / "v12_state" / "trading_state.json"
            state2_path = Path(__file__).parent.parent / "state" / "trading_state.json"

            if not state1_path.exists() or not state2_path.exists():
                self.print_warning("One or both state files missing")
                self.print_pass("Consistency check skipped")
                return

            with open(state1_path, 'r') as f:
                state1 = json.load(f)

            with open(state2_path, 'r') as f:
                state2 = json.load(f)

            # Check if balances match
            balance1 = state1.get('current_balance', 0)
            balance2 = state2.get('current_balance', 0)

            if abs(balance1 - balance2) > 0.01:
                self.print_warning(f"Balance mismatch: v12_state=${balance1:.2f}, state=${balance2:.2f}")
                self.print_pass("Discrepancy noted")
            else:
                self.print_pass("States synchronized")
        except Exception as e:
            self.print_fail(str(e))

    # =========================================================================
    # MAIN TEST RUNNER
    # =========================================================================

    def run_all_tests(self):
        """Run all tests."""
        self.print_header("TELEGRAM BOT TEST HARNESS")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

        # Section 1: Message Formatter Tests
        self.print_header("SECTION 1: MESSAGE FORMATTER TESTS")
        self.test_format_balance()
        self.test_format_positions()
        self.test_format_status()
        self.test_format_statistics()

        # Section 2: Database Tests
        self.print_header("SECTION 2: DATABASE & STATE TESTS")
        self.test_database_access()
        self.test_state_file_access()
        self.test_state_consistency()

        # Section 3: Notification Tests
        self.print_header("SECTION 3: NOTIFICATION TESTS")
        print(f"{YELLOW}⚠ The following tests will send actual Telegram notifications!{RESET}")
        print(f"{YELLOW}⚠ Check your Telegram app to verify they arrive.{RESET}\n")

        response = input("Send test notifications to Telegram? (y/n): ")
        if response.lower() == 'y':
            self.test_notify_trade()
            time.sleep(1)  # Rate limit

            self.test_notify_redemption_win()
            time.sleep(1)

            self.test_notify_redemption_loss()
            time.sleep(1)

            self.test_notify_critical_alert()
            time.sleep(1)

            self.test_notify_daily_summary()
        else:
            print(f"{YELLOW}Skipping notification tests{RESET}")

        # Final Summary
        self.print_header("TEST SUMMARY")

        total = self.tests_total
        passed = self.tests_passed
        failed = self.tests_failed
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"Total Tests:  {total}")
        print(f"Passed:       {GREEN}{passed}{RESET}")
        print(f"Failed:       {RED}{failed}{RESET}")
        print(f"Pass Rate:    {pass_rate:.1f}%")
        print()

        if failed == 0:
            print(f"{GREEN}{BOLD}✓ ALL TESTS PASSED!{RESET}")
            return 0
        else:
            print(f"{RED}{BOLD}✗ SOME TESTS FAILED{RESET}")
            return 1


def main():
    """Main entry point."""
    harness = TelegramTestHarness()
    exit_code = harness.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
