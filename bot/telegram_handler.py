"""
Telegram Handler for Polymarket AutoTrader

A unified, lightweight Telegram integration for the intra_epoch_bot.
Provides non-blocking notifications and command handling.

Usage:
    from telegram_handler import TelegramBot

    telegram = TelegramBot()
    telegram.notify_trade(crypto, direction, entry_price, size, accuracy, magnitude_pct, confluence_count)
    telegram.notify_win(crypto, direction, profit, balance, win_rate)
    telegram.notify_loss(crypto, direction, loss, balance, win_rate)
    telegram.start_polling()  # For command handling
"""

import logging
import os
import threading
from typing import Optional

import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

log = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram bot handler for trading notifications and commands.

    Design principles:
    - Non-blocking: All sends run in background threads
    - Fail-safe: Telegram failures never crash the trading bot
    - State reading only: Reads state, doesn't write (no race conditions from notifications)
    """

    def __init__(self):
        """Initialize Telegram bot with configuration from environment."""
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("TELEGRAM_AUTHORIZED_USER_ID", "")
        self.enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"

        # Also check legacy env var
        if not self.enabled:
            self.enabled = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower() == "true"

        # Validate configuration
        if self.enabled and (not self.token or not self.chat_id):
            log.warning("Telegram enabled but missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
            self.enabled = False

        # Log startup status
        if self.enabled:
            log.info("Telegram: ENABLED")
        else:
            log.info("Telegram: DISABLED")

        # Polling state
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None
        self._update_offset = 0

    def is_authorized(self, user_id: int) -> bool:
        """Check if user_id is authorized to send commands."""
        try:
            return str(user_id) == str(self.chat_id)
        except (ValueError, TypeError):
            return False

    def send_message(self, text: str, parse_mode: str = "HTML", silent: bool = False) -> bool:
        """
        Send a message to the configured Telegram chat.

        Args:
            text: Message text (supports HTML formatting)
            parse_mode: Parsing mode - "HTML" or "Markdown"
            silent: If True, send without notification sound

        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        def _send():
            try:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": silent,
                }
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code != 200:
                    log.warning(f"Telegram send failed: HTTP {resp.status_code}")
                    return False
                return True
            except requests.Timeout:
                log.warning("Telegram send timed out")
                return False
            except requests.RequestException as e:
                log.warning(f"Telegram send failed: {e}")
                return False
            except Exception as e:
                log.warning(f"Telegram send unexpected error: {e}")
                return False

        # Send in background thread (non-blocking)
        thread = threading.Thread(target=_send, daemon=True)
        thread.start()
        return True  # Return immediately, actual send is async

    def send_message_sync(self, text: str, parse_mode: str = "HTML", silent: bool = False) -> bool:
        """
        Send a message synchronously (blocking).

        Use this when you need to confirm the message was sent before continuing.
        """
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": silent,
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                log.warning(f"Telegram send failed: HTTP {resp.status_code}")
                return False
            return True
        except requests.Timeout:
            log.warning("Telegram send timed out")
            return False
        except requests.RequestException as e:
            log.warning(f"Telegram send failed: {e}")
            return False
        except Exception as e:
            log.warning(f"Telegram send unexpected error: {e}")
            return False

    # =========================================================================
    # TRADE NOTIFICATIONS
    # =========================================================================

    def notify_trade(
        self,
        crypto: str,
        direction: str,
        entry_price: float,
        size: float,
        accuracy: float,
        magnitude_pct: float = 0.0,
        confluence_count: int = 0,
        is_averaging: bool = False,
    ) -> bool:
        """
        Send notification when a new trade is placed.

        Args:
            crypto: Cryptocurrency symbol (BTC, ETH, SOL, XRP)
            direction: Trade direction (Up or Down)
            entry_price: Entry price paid per share
            size: Position size in USD
            accuracy: Base pattern accuracy (0-100)
            magnitude_pct: Magnitude boost percentage (0-100)
            confluence_count: Number of exchanges agreeing (0-3)
            is_averaging: True if this is an averaging trade into existing position

        Returns:
            True if notification was queued successfully
        """
        action = "AVERAGING" if is_averaging else "NEW TRADE"
        emoji = "\U0001F4C8" if is_averaging else "\U0001F3AF"  # 📈 or 🎯

        # Build accuracy breakdown
        if magnitude_pct > 0:
            base_accuracy = accuracy - magnitude_pct
            accuracy_text = f"{accuracy:.0f}% ({base_accuracy:.0f}% + {magnitude_pct:.0f}% magnitude)"
        else:
            accuracy_text = f"{accuracy:.0f}%"

        # Build confluence text
        if confluence_count > 0:
            confluence_text = f"{confluence_count}/3 exchanges agree"
        else:
            confluence_text = "No confluence data"

        message = (
            f"{emoji} {action}\n"
            f"<b>{crypto} {direction}</b>\n"
            f"Entry: ${entry_price:.2f} | Size: ${size:.2f}\n"
            f"Accuracy: {accuracy_text}\n"
            f"Confluence: {confluence_text}"
        )

        return self.send_message(message)

    def notify_win(
        self,
        crypto: str,
        direction: str,
        profit: float,
        balance: float,
        win_rate: float,
    ) -> bool:
        """
        Send notification when a trade wins.

        Args:
            crypto: Cryptocurrency symbol (BTC, ETH, SOL, XRP)
            direction: Trade direction (Up or Down)
            profit: Profit amount in USD
            balance: Current balance after win
            win_rate: Current win rate (0-100 or 0-1, auto-converted)

        Returns:
            True if notification was queued successfully
        """
        # Auto-convert decimal win rate to percentage
        if win_rate <= 1:
            win_rate = win_rate * 100

        message = (
            "\u2705 WIN\n"  # ✅
            f"<b>{crypto} {direction}</b>\n"
            f"Profit: +${profit:.2f}\n"
            f"Balance: ${balance:.2f} | Win Rate: {win_rate:.0f}%"
        )

        return self.send_message(message)

    def notify_loss(
        self,
        crypto: str,
        direction: str,
        loss: float,
        balance: float,
        win_rate: float,
    ) -> bool:
        """
        Send notification when a trade loses.

        Args:
            crypto: Cryptocurrency symbol (BTC, ETH, SOL, XRP)
            direction: Trade direction (Up or Down)
            loss: Loss amount in USD (positive number, will be displayed as negative)
            balance: Current balance after loss
            win_rate: Current win rate (0-100 or 0-1, auto-converted)

        Returns:
            True if notification was queued successfully
        """
        # Auto-convert decimal win rate to percentage
        if win_rate <= 1:
            win_rate = win_rate * 100

        # Ensure loss is displayed as negative
        loss_display = abs(loss)

        message = (
            "\u274c LOSS\n"  # ❌
            f"<b>{crypto} {direction}</b>\n"
            f"Loss: -${loss_display:.2f}\n"
            f"Balance: ${balance:.2f} | Win Rate: {win_rate:.0f}%"
        )

        return self.send_message(message)

    # =========================================================================
    # HALT AND ALERT NOTIFICATIONS
    # =========================================================================

    def notify_halt(
        self,
        reason: str,
        balance: float,
        drawdown_pct: float = None,
    ) -> bool:
        """
        Send notification when the bot is halted.

        Args:
            reason: Reason for the halt
            balance: Current balance at time of halt
            drawdown_pct: Current drawdown percentage (0-100 or 0-1, auto-converted)

        Returns:
            True if notification was queued successfully
        """
        message = (
            "\U0001F6A8 BOT HALTED\n"  # 🚨
            f"<b>Reason:</b> {reason}\n"
        )

        if drawdown_pct is not None:
            # Auto-convert decimal to percentage
            if drawdown_pct <= 1:
                drawdown_pct = drawdown_pct * 100
            message += f"Drawdown: {drawdown_pct:.1f}%\n"

        message += f"Balance: ${balance:.2f}"

        return self.send_message(message)

    def notify_alert(
        self,
        message: str,
        level: str = "warning",
    ) -> bool:
        """
        Send an alert notification.

        Args:
            message: Alert message text
            level: Alert level - 'info', 'warning', or 'critical'

        Returns:
            True if notification was queued successfully
        """
        # Select emoji based on level
        level_emojis = {
            "info": "\u2139\ufe0f",      # ℹ️
            "warning": "\u26a0\ufe0f",   # ⚠️
            "critical": "\U0001F6A8",    # 🚨
        }
        emoji = level_emojis.get(level, level_emojis["warning"])

        level_text = level.upper()
        formatted_message = f"{emoji} {level_text}\n{message}"

        return self.send_message(formatted_message)

    def notify_resumed(
        self,
        balance: float,
        drawdown_pct: float,
    ) -> bool:
        """
        Send notification when the bot is resumed after being halted.

        Args:
            balance: Current balance at time of resume
            drawdown_pct: Current drawdown percentage (0-100 or 0-1, auto-converted)

        Returns:
            True if notification was queued successfully
        """
        # Auto-convert decimal to percentage
        if drawdown_pct <= 1:
            drawdown_pct = drawdown_pct * 100

        message = (
            "\u2705 BOT RESUMED\n"  # ✅
            f"Drawdown: {drawdown_pct:.1f}%\n"
            f"Balance: ${balance:.2f}"
        )

        return self.send_message(message)


    # =========================================================================
    # REDEMPTION AND STARTUP NOTIFICATIONS
    # =========================================================================

    def notify_redemption(self, count: int, total_value: float) -> bool:
        """
        Send notification when positions are redeemed.

        Args:
            count: Number of positions redeemed
            total_value: Total value redeemed in USD

        Returns:
            True if notification was queued successfully
        """
        # Only notify if meaningful redemption
        if count <= 0 or total_value < 1.0:
            return False

        message = (
            "\U0001F4B0 REDEEMED\n"  # 💰
            f"Positions: {count}\n"
            f"Value: ${total_value:.2f}"
        )

        return self.send_message(message)

    def notify_startup(
        self,
        balance: float,
        peak: float,
        trades: int,
        wins: int,
        losses: int,
    ) -> bool:
        """
        Send notification when bot starts.

        Args:
            balance: Current balance
            peak: Peak balance for drawdown calculation
            trades: Total number of trades
            wins: Total wins
            losses: Total losses

        Returns:
            True if notification was queued successfully
        """
        # Calculate drawdown
        drawdown_pct = ((peak - balance) / peak * 100) if peak > 0 else 0

        # Calculate win rate
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0

        message = (
            "\U0001F916 BOT STARTED\n"  # 🤖
            f"Balance: ${balance:.2f}\n"
            f"Peak: ${peak:.2f} | Drawdown: {drawdown_pct:.1f}%\n"
            f"Record: {wins}W/{losses}L ({win_rate:.1f}%)\n"
            f"Trading window: minutes 3-10"
        )

        return self.send_message(message)

    # =========================================================================
    # COMMAND POLLING AND HANDLING
    # =========================================================================

    def start_polling(self, state_getter=None) -> None:
        """
        Start background polling for Telegram commands.

        Args:
            state_getter: Callable that returns current BotState, or None to disable commands
        """
        if not self.enabled:
            return

        if self._polling:
            log.warning("Telegram polling already running")
            return

        self._state_getter = state_getter
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        log.info("Telegram command polling started")

    def stop_polling(self) -> None:
        """Stop the background polling loop."""
        self._polling = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        log.info("Telegram command polling stopped")

    def _poll_loop(self) -> None:
        """Internal polling loop - runs in background thread."""
        import time

        while self._polling:
            try:
                self._process_updates()
            except Exception as e:
                log.warning(f"Telegram poll error: {e}")

            time.sleep(2)  # Poll every 2 seconds

    def _process_updates(self) -> None:
        """Fetch and process pending Telegram updates."""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            params = {"offset": self._update_offset, "timeout": 1}
            resp = requests.get(url, params=params, timeout=5)

            if resp.status_code != 200:
                return

            data = resp.json()
            if not data.get("ok"):
                return

            for update in data.get("result", []):
                self._update_offset = update["update_id"] + 1
                self._handle_update(update)

        except Exception as e:
            log.warning(f"Telegram getUpdates failed: {e}")

    def _handle_update(self, update: dict) -> None:
        """Handle a single Telegram update."""
        message = update.get("message", {})
        if not message:
            return

        user_id = message.get("from", {}).get("id")
        text = message.get("text", "")

        # Check authorization
        if not self.is_authorized(user_id):
            log.warning(f"Unauthorized Telegram access from user {user_id}")
            return

        # Parse command
        if not text.startswith("/"):
            return

        command = text.split()[0].lower()
        self._handle_command(command)

    def _handle_command(self, command: str) -> None:
        """Handle a Telegram command."""
        handlers = {
            "/help": self._cmd_help,
            "/balance": self._cmd_balance,
            "/positions": self._cmd_positions,
            "/status": self._cmd_status,
            "/stats": self._cmd_stats,
            "/halt": self._cmd_halt,
            "/resume": self._cmd_resume,
        }

        handler = handlers.get(command)
        if handler:
            handler()
        else:
            self.send_message(f"Unknown command: {command}\nUse /help for available commands.")

    def _cmd_help(self) -> None:
        """Handle /help command."""
        message = (
            "\U0001F4CB <b>Commands</b>\n\n"  # 📋
            "/balance - Current balance and drawdown\n"
            "/positions - Open positions\n"
            "/status - Bot status and epoch info\n"
            "/stats - Trading statistics\n"
            "/halt - Stop trading\n"
            "/resume - Resume trading\n"
            "/help - This message"
        )
        self.send_message(message)

    def _cmd_balance(self) -> None:
        """Handle /balance command."""
        state = self._get_state()
        if not state:
            self.send_message("Unable to read bot state")
            return

        balance = state.get("current_balance", 0)
        peak = state.get("peak_balance", balance)
        daily_pnl = state.get("daily_pnl", 0)
        drawdown = ((peak - balance) / peak * 100) if peak > 0 else 0

        pnl_sign = "+" if daily_pnl >= 0 else ""
        message = (
            "\U0001F4B0 BALANCE\n"  # 💰
            f"Current: ${balance:.2f}\n"
            f"Peak: ${peak:.2f} | Drawdown: {drawdown:.1f}%\n"
            f"Daily P&L: {pnl_sign}${daily_pnl:.2f}"
        )
        self.send_message(message)

    def _cmd_positions(self) -> None:
        """Handle /positions command."""
        state = self._get_state()
        if not state:
            self.send_message("Unable to read bot state")
            return

        positions = state.get("positions", {})
        if not positions:
            self.send_message("No open positions")
            return

        lines = [f"\U0001F4CA POSITIONS ({len(positions)} open)\n"]  # 📊
        for crypto, pos in positions.items():
            direction = pos.get("direction", "?")
            entry = pos.get("entry_price", 0)
            size = pos.get("size", 0)
            epoch = pos.get("epoch", 0)

            # Convert epoch timestamp to time string
            from datetime import datetime, timezone
            epoch_time = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%H:%M") if epoch else "?"

            lines.append(f"\n{crypto} {direction} @ ${entry:.2f}")
            lines.append(f"Size: ${size:.2f} | Epoch: {epoch_time}")

        self.send_message("\n".join(lines))

    def _cmd_status(self) -> None:
        """Handle /status command."""
        state = self._get_state()
        if not state:
            self.send_message("Unable to read bot state")
            return

        halted = state.get("halted", False)
        positions = state.get("positions", {})

        # Get current epoch info
        import time
        from datetime import datetime, timezone

        now = time.time()
        epoch_start = int(now // 900) * 900  # 15-minute epochs
        time_in_epoch = int(now - epoch_start)
        minutes = time_in_epoch // 60
        seconds = time_in_epoch % 60
        epoch_time = datetime.fromtimestamp(epoch_start, tz=timezone.utc).strftime("%H:%M")

        # Trading window status
        if 3 <= minutes <= 10:
            window_status = "OPEN (min 3-10)"
        elif minutes < 3:
            window_status = f"Opens in {3 - minutes} min"
        else:
            window_status = "CLOSED (waiting for next epoch)"

        mode = "HALTED" if halted else "Trading"

        message = (
            "\U0001F916 STATUS\n"  # 🤖
            f"Mode: {mode}\n"
            f"Current Epoch: {epoch_time} UTC\n"
            f"Time in Epoch: {minutes}:{seconds:02d}\n"
            f"Trading Window: {window_status}\n"
            f"Positions: {len(positions)} open"
        )
        self.send_message(message)

    def _cmd_stats(self) -> None:
        """Handle /stats command."""
        state = self._get_state()
        if not state:
            self.send_message("Unable to read bot state")
            return

        total = state.get("total_trades", 0)
        wins = state.get("total_wins", 0)
        losses = state.get("total_losses", 0)
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        message = (
            "\U0001F4C8 STATISTICS\n"  # 📈
            f"Total Trades: {total}\n"
            f"Wins: {wins} | Losses: {losses}\n"
            f"Win Rate: {win_rate:.1f}%"
        )
        self.send_message(message)

    def _cmd_halt(self) -> None:
        """Handle /halt command."""
        state = self._get_state()
        if not state:
            self.send_message("Unable to read bot state")
            return

        if state.get("halted"):
            self.send_message("Bot is already halted")
            return

        # Set halt flag via state file
        if self._set_halt(True, "Manual halt via Telegram"):
            self.send_message("\U0001F6D1 Trading HALTED.\nUse /resume to restart.")  # 🛑
        else:
            self.send_message("Failed to halt bot - state file error")

    def _cmd_resume(self) -> None:
        """Handle /resume command."""
        state = self._get_state()
        if not state:
            self.send_message("Unable to read bot state")
            return

        if not state.get("halted"):
            self.send_message("Bot is not halted")
            return

        # Check drawdown before resuming
        balance = state.get("current_balance", 0)
        peak = state.get("peak_balance", balance)
        drawdown = ((peak - balance) / peak) if peak > 0 else 0

        if drawdown > 0.30:
            self.send_message(
                f"Cannot resume: Drawdown is {drawdown*100:.1f}% (exceeds 30%)\n"
                "Reset peak balance first or wait for recovery."
            )
            return

        if self._set_halt(False, None):
            self.send_message(f"\u2705 Trading RESUMED.\nBalance: ${balance:.2f}")  # ✅
        else:
            self.send_message("Failed to resume bot - state file error")

    def _get_state(self) -> Optional[dict]:
        """Read current bot state from file."""
        import json
        from pathlib import Path

        # Try multiple paths
        paths = [
            Path("/opt/polymarket-autotrader/state/intra_epoch_state.json"),
            Path(__file__).parent.parent / "state" / "intra_epoch_state.json",
        ]

        for path in paths:
            if path.exists():
                try:
                    with open(path, "r") as f:
                        return json.load(f)
                except Exception as e:
                    log.warning(f"Failed to read state from {path}: {e}")

        return None

    def _set_halt(self, halted: bool, reason: Optional[str]) -> bool:
        """Set halt state in bot state file with file locking."""
        import json
        import fcntl
        from pathlib import Path

        paths = [
            Path("/opt/polymarket-autotrader/state/intra_epoch_state.json"),
            Path(__file__).parent.parent / "state" / "intra_epoch_state.json",
        ]

        for path in paths:
            if path.exists():
                try:
                    with open(path, "r+") as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        try:
                            state = json.load(f)
                            state["halted"] = halted
                            state["halt_reason"] = reason
                            f.seek(0)
                            json.dump(state, f, indent=2)
                            f.truncate()
                            return True
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception as e:
                    log.warning(f"Failed to update state at {path}: {e}")

        return False


# Module-level singleton for convenience
_bot_instance: Optional[TelegramBot] = None


def get_telegram_bot() -> TelegramBot:
    """Get or create the singleton TelegramBot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TelegramBot()
    return _bot_instance
