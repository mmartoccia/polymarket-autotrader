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
import json
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
from telegram_bot.enhanced_notifications import (
    format_trade_notification,
    format_redemption_notification,
    format_alert_notification,
    format_daily_summary
)
from telegram_bot.management_commands import (
    logs_command,
    trades_command,
    performance_command,
    risks_command,
    markets_command,
    force_redeem_command,
    confirm_redeem_command,
    reset_peak_command,
    confirm_reset_peak_command,
    export_command
)

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
        "*📊 Query Commands:*\n"
        "/balance - Current balance and P&L\n"
        "/positions - Active positions\n"
        "/status - Bot status and mode\n"
        "/stats - Trading statistics\n"
        "/performance - Quick snapshot\n"
        "/risks - Risk metrics\n\n"
        "*🎛️ Control Commands:*\n"
        "/halt - Stop all trading\n"
        "/resume - Resume trading\n"
        "/mode <mode> - Change mode\n"
        "/force_redeem - Manual redemption\n"
        "/reset_peak - Reset peak (emergency)\n\n"
        "*🔧 Management:*\n"
        "/logs - Recent bot logs\n"
        "/trades - Recent trade history\n"
        "/markets - Available markets\n"
        "/export - Export data\n\n"
        "*Help:*\n"
        "/help - Show this message\n\n"
        "🔔 *Real-time notifications:*\n"
        "• New trades (with risk indicators)\n"
        "• Redemptions (with ROI)\n"
        "• Position updates\n"
        "• Alerts (with recommendations)\n"
        "• Mode changes\n"
        "• Daily summaries"
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


async def halt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /halt command - request confirmation to halt bot."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    confirmation_message = (
        "⚠️ *CONFIRM HALT?*\n\n"
        "This will stop all trading.\n"
        "Reply /confirm\\_halt to proceed."
    )

    await update.message.reply_text(confirmation_message, parse_mode='Markdown')
    logger.info(f"Halt request by {update.effective_user.username}")


async def confirm_halt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /confirm_halt command - actually halt the bot."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    try:
        # Update trading state to HALTED mode
        state_file = '/opt/polymarket-autotrader/state/trading_state.json'
        if not os.path.exists(state_file):
            state_file = 'state/trading_state.json'

        with open(state_file, 'r') as f:
            state = json.load(f)

        state['mode'] = 'halted'

        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

        message = (
            "🛑 *BOT HALTED*\n\n"
            "Trading stopped.\n"
            "Use /resume to restart."
        )

        await update.message.reply_text(message, parse_mode='Markdown')
        logger.warning(f"Bot halted by {update.effective_user.username}")

    except Exception as e:
        logger.error(f"Error in confirm_halt_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error halting bot: {str(e)}")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resume command - request confirmation to resume trading."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    confirmation_message = (
        "✅ *CONFIRM RESUME?*\n\n"
        "This will resume normal trading.\n"
        "Reply /confirm\\_resume to proceed."
    )

    await update.message.reply_text(confirmation_message, parse_mode='Markdown')
    logger.info(f"Resume request by {update.effective_user.username}")


async def confirm_resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /confirm_resume command - actually resume the bot."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    try:
        # Update trading state to NORMAL mode
        state_file = '/opt/polymarket-autotrader/state/trading_state.json'
        if not os.path.exists(state_file):
            state_file = 'state/trading_state.json'

        with open(state_file, 'r') as f:
            state = json.load(f)

        state['mode'] = 'normal'

        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

        message = (
            "✅ *BOT RESUMED*\n\n"
            "Trading resumed in NORMAL mode.\n"
            "Use /status to check bot status."
        )

        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Bot resumed by {update.effective_user.username}")

    except Exception as e:
        logger.error(f"Error in confirm_resume_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error resuming bot: {str(e)}")


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mode <mode> command - change trading mode with confirmation."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    # Check if mode argument provided
    if not context.args or len(context.args) != 1:
        message = (
            "📋 *MODE COMMAND*\n\n"
            "Usage: /mode <mode>\n\n"
            "Valid modes:\n"
            "• normal - Standard trading\n"
            "• conservative - Reduced position sizes\n"
            "• defensive - Further reduced sizes\n"
            "• recovery - Minimal position sizes\n"
            "• halted - Stop trading (use /halt instead)\n\n"
            "Example: /mode conservative"
        )
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    new_mode = context.args[0].lower()
    valid_modes = ['normal', 'conservative', 'defensive', 'recovery', 'halted']

    if new_mode not in valid_modes:
        await update.message.reply_text(
            f"❌ Invalid mode: {new_mode}\n"
            f"Valid modes: {', '.join(valid_modes)}"
        )
        return

    # Store pending mode change in context
    context.user_data['pending_mode'] = new_mode

    confirmation_message = (
        f"⚠️ *CONFIRM MODE CHANGE?*\n\n"
        f"Change mode to: *{new_mode.upper()}*\n\n"
        f"Reply /confirm\\_mode to proceed."
    )

    await update.message.reply_text(confirmation_message, parse_mode='Markdown')
    logger.info(f"Mode change request by {update.effective_user.username}: {new_mode}")


async def confirm_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /confirm_mode command - actually change the mode."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized access")
        return

    # Check if there's a pending mode change
    new_mode = context.user_data.get('pending_mode')
    if not new_mode:
        await update.message.reply_text("❌ No pending mode change. Use /mode <mode> first.")
        return

    try:
        # Update trading state
        state_file = '/opt/polymarket-autotrader/state/trading_state.json'
        if not os.path.exists(state_file):
            state_file = 'state/trading_state.json'

        with open(state_file, 'r') as f:
            state = json.load(f)

        old_mode = state.get('mode', 'unknown')
        state['mode'] = new_mode

        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

        # Clear pending mode change
        context.user_data.pop('pending_mode', None)

        # Mode-specific emojis
        mode_emoji = {
            'normal': '🟢',
            'conservative': '🟡',
            'defensive': '🟠',
            'recovery': '🔴',
            'halted': '🛑'
        }

        message = (
            f"{mode_emoji.get(new_mode, '📋')} *MODE CHANGED*\n\n"
            f"{old_mode.upper()} → {new_mode.upper()}\n\n"
            f"Use /status to verify."
        )

        await update.message.reply_text(message, parse_mode='Markdown')
        logger.warning(f"Mode changed by {update.effective_user.username}: {old_mode} → {new_mode}")

    except Exception as e:
        logger.error(f"Error in confirm_mode_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error changing mode: {str(e)}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the telegram bot."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)


# ============================================================================
# NOTIFICATION FUNCTIONS (for integration with trading bot)
# ============================================================================

# Global application instance for sending notifications
_application: Optional[Application] = None


def set_application(app: Application):
    """Set the global application instance for notifications."""
    global _application
    _application = app


async def send_trade_notification(
    crypto: str,
    direction: str,
    entry_price: float,
    size: float,
    shares: int,
    confidence: float,
    agents_voted: list[str],
    strategy: str = "Unknown"
) -> None:
    """
    Send notification when a new trade is placed.

    Args:
        crypto: Cryptocurrency symbol (e.g., "BTC", "ETH")
        direction: Trade direction ("Up" or "Down")
        entry_price: Entry price per share
        size: Position size in USD
        shares: Number of shares purchased
        confidence: Confidence score (0-1)
        agents_voted: List of agent names that voted for this trade
        strategy: Strategy name (e.g., "Contrarian fade", "Early momentum")
    """
    if not NOTIFICATIONS_ENABLED or not _application:
        return

    try:
        # Format agent votes
        agent_votes = ", ".join(agents_voted) if agents_voted else "Unknown"

        # Determine emoji based on strategy
        strategy_emoji = "🚀"
        if "contrarian" in strategy.lower():
            strategy_emoji = "🔄"
        elif "late" in strategy.lower():
            strategy_emoji = "✅"

        message = (
            f"{strategy_emoji} *NEW TRADE*\n\n"
            f"*{crypto} {direction}* @ ${entry_price:.2f}\n"
            f"Size: ${size:.2f} ({shares} shares)\n"
            f"Confidence: {confidence * 100:.1f}%\n\n"
            f"*Agents:* {agent_votes}\n"
            f"*Strategy:* {strategy}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}"
        )

        await _application.bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Trade notification sent: {crypto} {direction}")

    except Exception as e:
        logger.error(f"Error sending trade notification: {e}", exc_info=True)
        # Don't raise - notifications should never break trading bot


def notify_trade(
    crypto: str,
    direction: str,
    entry_price: float,
    size: float,
    shares: int,
    confidence: float,
    agents_voted: Optional[list[str]] = None,
    strategy: str = "Unknown"
) -> None:
    """
    Synchronous wrapper for send_trade_notification.
    Safe to call from non-async code (e.g., trading bot main loop).
    """
    if agents_voted is None:
        agents_voted = []

    # Run the async function in a new event loop (non-blocking)
    try:
        # Create a new event loop for this thread if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_trade_notification(
            crypto=crypto,
            direction=direction,
            entry_price=entry_price,
            size=size,
            shares=shares,
            confidence=confidence,
            agents_voted=agents_voted,
            strategy=strategy
        ))
        loop.close()
    except Exception as e:
        logger.error(f"Error in notify_trade wrapper: {e}", exc_info=True)


async def send_redemption_notification(
    crypto: str,
    direction: str,
    outcome: str,
    pnl: float,
    shares_redeemed: float,
    entry_price: float,
    new_balance: float
) -> None:
    """
    Send notification when a position is redeemed.

    Args:
        crypto: Cryptocurrency symbol (e.g., "BTC", "ETH")
        direction: Trade direction ("Up" or "Down")
        outcome: Result of the trade ("win" or "loss")
        pnl: Profit/loss amount in USD
        shares_redeemed: Number of shares redeemed
        entry_price: Original entry price per share
        new_balance: Account balance after redemption
    """
    if not NOTIFICATIONS_ENABLED or not _application:
        return

    try:
        # Determine emoji and outcome text
        if outcome.lower() == "win":
            emoji = "✅"
            outcome_text = "WIN"
            payout = 1.00
        else:
            emoji = "❌"
            outcome_text = "LOSS"
            payout = 0.00

        # Format P&L with sign
        pnl_sign = "+" if pnl >= 0 else ""

        message = (
            f"{emoji} *REDEMPTION - {outcome_text}*\n\n"
            f"*{crypto.upper()} {direction}:* {shares_redeemed:.0f} shares\n"
            f"P&L: ${pnl_sign}{pnl:.2f}\n"
            f"Entry: ${entry_price:.2f} → Payout: ${payout:.2f}\n\n"
            f"💰 New Balance: ${new_balance:.2f}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}"
        )

        await _application.bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Redemption notification sent: {crypto} {direction} - {outcome_text}")

    except Exception as e:
        logger.error(f"Error sending redemption notification: {e}", exc_info=True)
        # Don't raise - notifications should never break trading bot


def notify_redemption(
    crypto: str,
    direction: str,
    outcome: str,
    pnl: float,
    shares_redeemed: float,
    entry_price: float,
    new_balance: float
) -> None:
    """
    Synchronous wrapper for send_redemption_notification.
    Safe to call from non-async code (e.g., trading bot main loop).
    """
    # Run the async function in a new event loop (non-blocking)
    try:
        # Create a new event loop for this thread if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_redemption_notification(
            crypto=crypto,
            direction=direction,
            outcome=outcome,
            pnl=pnl,
            shares_redeemed=shares_redeemed,
            entry_price=entry_price,
            new_balance=new_balance
        ))
        loop.close()
    except Exception as e:
        logger.error(f"Error in notify_redemption wrapper: {e}", exc_info=True)


async def send_alert_notification(
    level: str,
    title: str,
    message: str
) -> None:
    """
    Send notification for critical alerts.

    Args:
        level: Alert severity level ('critical', 'warning', 'info')
        title: Alert title
        message: Detailed alert message
    """
    if not NOTIFICATIONS_ENABLED or not _application:
        return

    try:
        # Determine emoji based on severity
        emoji_map = {
            'critical': '🚨',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        emoji = emoji_map.get(level.lower(), '📢')

        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M UTC')

        # Build notification message
        notification = (
            f"{emoji} *{level.upper()} ALERT*\n\n"
            f"*{title}*\n\n"
            f"{message}\n\n"
            f"⏰ {timestamp}"
        )

        await _application.bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=notification,
            parse_mode='Markdown'
        )
        logger.info(f"Alert notification sent: {level} - {title}")

    except Exception as e:
        logger.error(f"Error sending alert notification: {e}", exc_info=True)
        # Don't raise - notifications should never break trading bot


def notify_alert(level: str, title: str, message: str) -> None:
    """
    Synchronous wrapper for send_alert_notification.
    Safe to call from non-async code (e.g., alert system).
    """
    # Run the async function in a new event loop (non-blocking)
    try:
        # Create a new event loop for this thread if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_alert_notification(
            level=level,
            title=title,
            message=message
        ))
        loop.close()
    except Exception as e:
        logger.error(f"Error in notify_alert wrapper: {e}", exc_info=True)


async def send_daily_summary() -> None:
    """
    Send daily summary notification with P&L, trades, and shadow strategy performance.
    Should be called at end of day (23:59 UTC).
    """
    if not NOTIFICATIONS_ENABLED or not _application:
        return

    try:
        formatter = MessageFormatter()
        message = formatter.format_daily_summary()

        await _application.bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=message
        )
        logger.info("Daily summary notification sent")

    except Exception as e:
        logger.error(f"Error sending daily summary notification: {e}", exc_info=True)
        # Don't raise - notifications should never crash


def notify_daily_summary() -> None:
    """
    Synchronous wrapper for send_daily_summary.
    Safe to call from non-async code (e.g., scheduled task).
    """
    # Run the async function in a new event loop (non-blocking)
    try:
        # Create a new event loop for this thread if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_daily_summary())
        loop.close()
    except Exception as e:
        logger.error(f"Error in notify_daily_summary wrapper: {e}", exc_info=True)


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

    # Set global application instance for notifications
    set_application(application)

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("positions", positions_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Control commands
    application.add_handler(CommandHandler("halt", halt_command))
    application.add_handler(CommandHandler("confirm_halt", confirm_halt_command))
    application.add_handler(CommandHandler("resume", resume_command))
    application.add_handler(CommandHandler("confirm_resume", confirm_resume_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("confirm_mode", confirm_mode_command))

    # Management commands
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("trades", trades_command))
    application.add_handler(CommandHandler("performance", performance_command))
    application.add_handler(CommandHandler("risks", risks_command))
    application.add_handler(CommandHandler("markets", markets_command))
    application.add_handler(CommandHandler("force_redeem", force_redeem_command))
    application.add_handler(CommandHandler("confirm_redeem", confirm_redeem_command))
    application.add_handler(CommandHandler("reset_peak", reset_peak_command))
    application.add_handler(CommandHandler("confirm_reset_peak", confirm_reset_peak_command))
    application.add_handler(CommandHandler("export", export_command))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Bot started successfully - polling for messages")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
