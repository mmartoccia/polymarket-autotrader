#!/usr/bin/env python3
"""
Telegram Bot for Polymarket AutoTrader

Provides:
- Query commands: /balance, /positions, /status, /stats
- Real-time notifications: trades, redemptions, alerts
- Daily summaries and bot control
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.message_formatter import MessageFormatter

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER_ID = int(os.getenv('TELEGRAM_AUTHORIZED_USER_ID', '0'))
NOTIFICATIONS_ENABLED = os.getenv('TELEGRAM_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def is_authorized(update: Update) -> bool:
    """Check if user is authorized to interact with bot."""
    if not update.effective_user:
        return False

    user_id = update.effective_user.id
    is_auth = user_id == AUTHORIZED_USER_ID

    if not is_auth:
        logger.warning(f"Unauthorized access attempt from user {user_id}")

    return is_auth


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    welcome_message = (
        "🤖 *Polymarket AutoTrader Bot*\n\n"
        "Available commands:\n\n"
        "*Query Commands:*\n"
        "/balance - Current balance and P&L\n"
        "/positions - Active positions\n"
        "/status - Bot status and mode\n"
        "/stats - Trading statistics\n\n"
        "*Help:*\n"
        "/help - Show this message\n\n"
        "🔔 Real-time notifications enabled for:\n"
        "• New trades\n"
        "• Redemptions\n"
        "• Critical alerts"
    )

    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"User {update.effective_user.username} started bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    await start(update, context)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command - show balance and P&L."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    try:
        formatter = MessageFormatter()
        message = formatter.format_balance()
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Balance query by {update.effective_user.username}")
    except Exception as e:
        logger.error(f"Error in balance_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error fetching balance: {str(e)}")


async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /positions command - show active positions."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    try:
        formatter = MessageFormatter()
        message = formatter.format_positions()
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Positions query by {update.effective_user.username}")
    except Exception as e:
        logger.error(f"Error in positions_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error fetching positions: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show bot status."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    try:
        formatter = MessageFormatter()
        message = formatter.format_status()
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Status query by {update.effective_user.username}")
    except Exception as e:
        logger.error(f"Error in status_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error fetching status: {str(e)}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show trading statistics."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    try:
        formatter = MessageFormatter()
        message = formatter.format_statistics()
        await update.message.reply_text(message)  # Plain text, no Markdown parsing
        logger.info(f"Stats query by {update.effective_user.username}")
    except Exception as e:
        logger.error(f"Error in stats_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error fetching statistics: {str(e)}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the telegram bot."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)


def main():
    """Start the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment")
        sys.exit(1)

    if not AUTHORIZED_USER_ID:
        logger.error("TELEGRAM_AUTHORIZED_USER_ID not found in environment")
        sys.exit(1)

    logger.info(f"Starting Telegram bot (authorized user: {AUTHORIZED_USER_ID})")
    logger.info(f"Notifications enabled: {NOTIFICATIONS_ENABLED}")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("positions", positions_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Bot started successfully - polling for messages")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
