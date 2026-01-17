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


# Module-level singleton for convenience
_bot_instance: Optional[TelegramBot] = None


def get_telegram_bot() -> TelegramBot:
    """Get or create the singleton TelegramBot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TelegramBot()
    return _bot_instance
