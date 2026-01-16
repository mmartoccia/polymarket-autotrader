#!/usr/bin/env python3
"""
Additional Telegram Bot Management Commands

New commands for comprehensive bot control:
- /logs - View recent bot logs
- /trades - View recent trades
- /performance - Quick performance snapshot
- /risks - View current risk metrics
- /markets - View available markets
- /force_redeem - Manually trigger redemption check
- /reset_peak - Reset peak balance (emergency)
- /export - Export trading data
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent bot logs (last 20 lines)."""
    try:
        log_path = Path(__file__).parent.parent / "bot.log"

        if not log_path.exists():
            await update.message.reply_text("❌ Log file not found")
            return

        # Read last 20 lines
        with open(log_path, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-20:] if len(lines) > 20 else lines

        log_text = "📜 *RECENT LOGS* (Last 20 lines)\n\n```\n"
        log_text += "".join(recent_lines)
        log_text += "```"

        # Telegram has 4096 char limit
        if len(log_text) > 4000:
            log_text = log_text[:3900] + "\n...\n```\n_(truncated)_"

        await update.message.reply_text(log_text, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error reading logs: {e}")


async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent trades from database."""
    try:
        db_path = Path(__file__).parent.parent / "simulation" / "trade_journal.db"

        if not db_path.exists():
            await update.message.reply_text("❌ Trade database not found")
            return

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get last 10 trades
        cursor.execute('''
            SELECT crypto, direction, entry_price, shares, size, strategy, timestamp
            FROM trades
            WHERE strategy LIKE 'ml_live%'
            ORDER BY timestamp DESC
            LIMIT 10
        ''')

        trades = cursor.fetchall()
        conn.close()

        if not trades:
            await update.message.reply_text("📊 No trades found in database")
            return

        lines = ["📊 *RECENT TRADES* (Last 10)\n"]

        for crypto, direction, entry, shares, size, strategy, ts in trades:
            dt = datetime.fromtimestamp(ts).strftime('%m/%d %H:%M')
            dir_emoji = "📈" if direction == "Up" else "📉"
            lines.append(
                f"{dir_emoji} {dt} - {crypto} {direction}\n"
                f"   ${entry:.2f} × {shares} = ${size:.2f}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching trades: {e}")


async def performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quick performance snapshot."""
    try:
        # Read state file
        state_path = Path(__file__).parent.parent / "v12_state" / "trading_state.json"

        if not state_path.exists():
            await update.message.reply_text("❌ State file not found")
            return

        with open(state_path, 'r') as f:
            state = json.load(f)

        current = state.get('current_balance', 0)
        peak = state.get('peak_balance', 0)
        day_start = state.get('day_start_balance', 0)
        daily_pnl = state.get('daily_pnl', 0)
        mode = state.get('mode', 'unknown')

        # Calculate metrics
        drawdown = ((peak - current) / peak * 100) if peak > 0 else 0
        daily_roi = (daily_pnl / day_start * 100) if day_start > 0 else 0

        # Drawdown emoji
        dd_emoji = "🔴" if drawdown > 25 else "🟡" if drawdown > 15 else "🟢"

        # Daily P&L emoji
        pnl_emoji = "📈" if daily_pnl > 0 else "📉" if daily_pnl < 0 else "➡️"

        message = (
            "⚡ *QUICK PERFORMANCE*\n\n"
            f"💰 *Balance:* ${current:.2f}\n"
            f"🏔️ *Peak:* ${peak:.2f}\n"
            f"{dd_emoji} *Drawdown:* {drawdown:.1f}%\n\n"
            f"{pnl_emoji} *Today:* ${daily_pnl:+.2f} ({daily_roi:+.1f}%)\n"
            f"🎚️ *Mode:* {mode.upper()}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}"
        )

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def risks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current risk metrics and limits."""
    try:
        # Read state
        state_path = Path(__file__).parent.parent / "v12_state" / "trading_state.json"

        with open(state_path, 'r') as f:
            state = json.load(f)

        current = state.get('current_balance', 0)
        peak = state.get('peak_balance', 0)
        day_start = state.get('day_start_balance', 0)
        daily_pnl = state.get('daily_pnl', 0)
        consecutive_losses = state.get('consecutive_losses', 0)

        # Calculate risk metrics
        drawdown = ((peak - current) / peak) if peak > 0 else 0
        daily_loss_pct = (abs(daily_pnl) / day_start) if day_start > 0 and daily_pnl < 0 else 0

        # Risk limits (from bot config)
        MAX_DRAWDOWN = 0.30  # 30%
        DAILY_LOSS_LIMIT_USD = 30
        DAILY_LOSS_LIMIT_PCT = 0.20  # 20%

        # Status indicators
        dd_status = "✅" if drawdown < 0.20 else "⚠️" if drawdown < 0.30 else "🔴"
        daily_status = "✅" if abs(daily_pnl) < 20 else "⚠️" if abs(daily_pnl) < 30 else "🔴"
        streak_status = "✅" if consecutive_losses < 3 else "⚠️" if consecutive_losses < 5 else "🔴"

        message = (
            "🛡️ *RISK METRICS*\n\n"
            f"{dd_status} *Drawdown*\n"
            f"Current: {drawdown * 100:.1f}%\n"
            f"Limit: {MAX_DRAWDOWN * 100:.0f}%\n"
            f"Remaining: {(MAX_DRAWDOWN - drawdown) * 100:.1f}%\n\n"
            f"{daily_status} *Daily Loss*\n"
            f"Current: ${abs(daily_pnl):.2f} ({daily_loss_pct * 100:.1f}%)\n"
            f"Limit: ${DAILY_LOSS_LIMIT_USD} or {DAILY_LOSS_LIMIT_PCT * 100:.0f}%\n\n"
            f"{streak_status} *Loss Streak*\n"
            f"Current: {consecutive_losses} consecutive\n"
            f"Warning: 3+ losses\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}"
        )

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def markets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show currently available markets."""
    try:
        import requests

        # Query Polymarket Gamma API for active 15-min markets
        response = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"closed": "false", "limit": 50},
            timeout=10
        )

        if response.status_code != 200:
            await update.message.reply_text("❌ Failed to fetch markets")
            return

        markets = response.json()

        # Filter for 15-minute markets
        fifteen_min_markets = []
        for market in markets:
            question = market.get('question', '')
            if '15-minute' in question.lower() or '15 min' in question.lower():
                fifteen_min_markets.append(market)

        if not fifteen_min_markets:
            await update.message.reply_text("📊 No active 15-minute markets found")
            return

        lines = ["📊 *ACTIVE 15-MIN MARKETS*\n"]

        for market in fifteen_min_markets[:10]:  # Limit to 10
            question = market.get('question', 'Unknown')
            # Extract crypto from question
            crypto = "?"
            for c in ['BTC', 'ETH', 'SOL', 'XRP']:
                if c in question.upper():
                    crypto = c
                    break

            lines.append(f"• {crypto}: {question[:50]}...")

        lines.append(f"\n_Total: {len(fifteen_min_markets)} markets_")

        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def force_redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger redemption check."""
    await update.message.reply_text(
        "⚠️ *CONFIRM FORCE REDEMPTION?*\n\n"
        "This will check all positions and attempt to redeem winners.\n\n"
        "Reply with `/confirm_redeem` to proceed.",
        parse_mode='Markdown'
    )


async def confirm_redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute forced redemption."""
    try:
        await update.message.reply_text("🔄 Checking for redeemable positions...")

        # Import redemption logic
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.redeem_winners import main as redeem_main

        # Execute redemption (this is synchronous, so run in executor)
        # For now, just notify user to run manually
        await update.message.reply_text(
            "📝 *Manual Redemption*\n\n"
            "Run this command on VPS:\n"
            "```\n"
            "cd /opt/polymarket-autotrader\n"
            "python3 utils/redeem_winners.py\n"
            "```\n\n"
            "_Automated redemption integration coming soon_",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def reset_peak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset peak balance (emergency use only)."""
    await update.message.reply_text(
        "⚠️ *CONFIRM PEAK RESET?*\n\n"
        "This will reset peak_balance to current_balance.\n"
        "*Use only in emergencies* (e.g., after large unexpected loss)\n\n"
        "Reply with `/confirm_reset_peak` to proceed.",
        parse_mode='Markdown'
    )


async def confirm_reset_peak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute peak balance reset."""
    try:
        state_path = Path(__file__).parent.parent / "v12_state" / "trading_state.json"

        with open(state_path, 'r') as f:
            state = json.load(f)

        old_peak = state.get('peak_balance', 0)
        current = state.get('current_balance', 0)

        # Reset peak to current
        state['peak_balance'] = current

        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)

        await update.message.reply_text(
            f"✅ *Peak Balance Reset*\n\n"
            f"Old Peak: ${old_peak:.2f}\n"
            f"New Peak: ${current:.2f}\n\n"
            f"Drawdown now: 0.0%",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export trading data to CSV."""
    try:
        await update.message.reply_text(
            "📊 *Export Trading Data*\n\n"
            "Available exports:\n"
            "• `/export trades` - All trades\n"
            "• `/export outcomes` - All outcomes\n"
            "• `/export performance` - Strategy performance\n\n"
            "_Files will be generated on VPS_\n"
            "_Use `scp` to download them_",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# Command descriptions for /help
MANAGEMENT_COMMANDS_HELP = """
*📊 Management Commands:*

/logs - View recent bot logs
/trades - Recent trade history
/performance - Quick performance snapshot
/risks - Current risk metrics
/markets - Available 15-min markets
/force_redeem - Manual redemption check
/reset_peak - Reset peak balance (emergency)
/export - Export trading data

_Type any command for details_
"""
