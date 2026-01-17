"""
Telegram Reporting Module for Optimizer

Sends hourly reports and alerts via Telegram.
Uses existing bot/telegram_handler.py TelegramBot class.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.telegram_handler import TelegramBot

log = logging.getLogger(__name__)


def _format_pct(value: float | None, decimals: int = 1) -> str:
    """Format a decimal value as percentage string."""
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def _format_currency(value: float | None, show_sign: bool = False) -> str:
    """Format a currency value."""
    if value is None:
        return "N/A"
    if show_sign:
        sign = "+" if value >= 0 else ""
        return f"{sign}${value:.2f}"
    return f"${value:.2f}"


def send_hourly_report(
    analysis: dict[str, Any],
    adjustments: list[dict[str, Any]],
    current_state: dict[str, Any] | None = None,
    silent: bool = True
) -> bool:
    """
    Send an hourly performance report via Telegram.

    Args:
        analysis: Analysis dict from analyzer.analyze_all()
        adjustments: List of adjustment dicts from tuning_rules.select_tunings()
        current_state: Optional current bot state from data_collector.get_current_state()
        silent: If True, send without notification sound (default True for healthy)

    Returns:
        True if message was sent successfully, False otherwise
    """
    telegram = TelegramBot()

    if not telegram.enabled:
        log.info("Telegram disabled, skipping report")
        return False

    # Build the report message
    message = _build_report_message(analysis, adjustments, current_state)

    # Determine if this should alert (sound notification)
    status = analysis.get('status', 'healthy')
    should_alert = status == 'alert' or len(adjustments) > 0

    # Override silent param if alert condition
    if should_alert:
        silent = False

    # Send the message
    try:
        return telegram.send_message_sync(message, parse_mode="HTML", silent=silent)
    except Exception as e:
        log.error(f"Failed to send Telegram report: {e}")
        return False


def _build_report_message(
    analysis: dict[str, Any],
    adjustments: list[dict[str, Any]],
    current_state: dict[str, Any] | None = None
) -> str:
    """Build the formatted report message."""
    lines: list[str] = []

    # Header with status emoji
    status = analysis.get('status', 'healthy')
    status_emoji = {
        'healthy': '\u2705',   # ✅
        'warning': '\u26a0\ufe0f',  # ⚠️
        'alert': '\U0001F6A8',     # 🚨
    }.get(status, '\u2754')  # ❔

    period_hours = analysis.get('period_hours', 1)
    timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")

    lines.append(f"{status_emoji} <b>OPTIMIZER REPORT</b> ({timestamp})")
    lines.append(f"Period: Last {period_hours}h | Status: {status.upper()}")
    lines.append("")

    # Trade summary
    trade_perf = analysis.get('trade_performance', {})
    total_trades = trade_perf.get('total_trades', 0)
    resolved = trade_perf.get('resolved_trades', 0)
    wins = trade_perf.get('wins', 0)
    losses = trade_perf.get('losses', 0)
    win_rate = trade_perf.get('win_rate')
    total_pnl = trade_perf.get('total_pnl', 0)

    lines.append("\U0001F4CA <b>Trades</b>")  # 📊
    if total_trades == 0:
        lines.append("  No trades in period")
    else:
        lines.append(f"  Count: {total_trades} ({resolved} resolved)")
        if resolved > 0:
            lines.append(f"  Record: {wins}W / {losses}L ({_format_pct(win_rate)})")
            lines.append(f"  P&L: {_format_currency(total_pnl, show_sign=True)}")
    lines.append("")

    # Balance info (if state available)
    if current_state:
        balance = current_state.get('current_balance')
        peak = current_state.get('peak_balance')
        daily_pnl = current_state.get('daily_pnl')

        if balance is not None:
            lines.append("\U0001F4B0 <b>Balance</b>")  # 💰
            lines.append(f"  Current: {_format_currency(balance)}")
            if peak is not None and peak > 0:
                drawdown = (peak - balance) / peak
                lines.append(f"  Peak: {_format_currency(peak)} (DD: {_format_pct(drawdown)})")
            if daily_pnl is not None:
                lines.append(f"  Daily P&L: {_format_currency(daily_pnl, show_sign=True)}")
            lines.append("")

    # Skip analysis (top 3 reasons)
    skip_dist = analysis.get('skip_distribution', {})
    total_skips = skip_dist.get('total_skips', 0)

    if total_skips > 0:
        lines.append("\U0001F6AB <b>Skips</b>")  # 🚫
        lines.append(f"  Total: {total_skips}")

        by_type_pct = skip_dist.get('by_type_pct', {})
        by_type = skip_dist.get('by_type', {})

        # Sort by count descending and take top 3
        sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:3]

        for skip_type, count in sorted_types:
            pct = by_type_pct.get(skip_type, 0)
            lines.append(f"  • {skip_type}: {count} ({_format_pct(pct)})")
        lines.append("")

    # Issues detected
    issues = analysis.get('issues', [])
    if issues:
        lines.append("\u26a0\ufe0f <b>Issues</b>")  # ⚠️
        for issue in issues[:5]:  # Limit to 5
            lines.append(f"  • {issue}")
        lines.append("")

    # Adjustments made
    if adjustments:
        lines.append("\U0001F527 <b>Adjustments</b>")  # 🔧
        for adj in adjustments:
            param = adj.get('parameter', 'unknown')
            old_val = adj.get('old_value', 0)
            new_val = adj.get('new_value', 0)
            reason = adj.get('reason', '')

            # Format values based on magnitude
            if old_val < 1:
                old_str = f"{old_val:.2f}"
                new_str = f"{new_val:.2f}"
            else:
                old_str = f"{old_val:.0f}"
                new_str = f"{new_val:.0f}"

            lines.append(f"  • {param}: {old_str} → {new_str}")
            if reason:
                lines.append(f"    ({reason})")
        lines.append("")
    else:
        lines.append("\U0001F44D No adjustments needed")  # 👍
        lines.append("")

    # Inactivity diagnosis (if relevant)
    diagnosis = analysis.get('inactivity_diagnosis', '')
    if diagnosis and diagnosis not in ('normal_activity', ''):
        lines.append(f"\U0001F50D Diagnosis: {diagnosis}")  # 🔍

    return "\n".join(lines)


def send_alert(
    message: str,
    level: str = "warning"
) -> bool:
    """
    Send an alert notification via Telegram.

    Args:
        message: Alert message text
        level: Alert level - 'info', 'warning', or 'critical'

    Returns:
        True if message was sent successfully, False otherwise
    """
    telegram = TelegramBot()

    if not telegram.enabled:
        log.info("Telegram disabled, skipping alert")
        return False

    try:
        return telegram.notify_alert(message, level=level)
    except Exception as e:
        log.error(f"Failed to send Telegram alert: {e}")
        return False


def send_adjustment_notification(
    adjustments: list[dict[str, Any]]
) -> bool:
    """
    Send a notification about parameter adjustments.

    Args:
        adjustments: List of adjustment dicts

    Returns:
        True if message was sent successfully, False otherwise
    """
    if not adjustments:
        return True

    telegram = TelegramBot()

    if not telegram.enabled:
        log.info("Telegram disabled, skipping adjustment notification")
        return False

    lines = ["\U0001F527 <b>OPTIMIZER ADJUSTMENT</b>"]  # 🔧
    lines.append("")

    for adj in adjustments:
        param = adj.get('parameter', 'unknown')
        old_val = adj.get('old_value', 0)
        new_val = adj.get('new_value', 0)
        reason = adj.get('reason', '')

        # Format values
        if old_val < 1:
            change = f"{old_val:.2f} → {new_val:.2f}"
        else:
            change = f"{old_val:.0f} → {new_val:.0f}"

        lines.append(f"<b>{param}</b>: {change}")
        if reason:
            lines.append(f"Reason: {reason}")
        lines.append("")

    timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines.append(f"Time: {timestamp}")

    message = "\n".join(lines)

    try:
        # Adjustments should always alert (sound notification)
        return telegram.send_message_sync(message, parse_mode="HTML", silent=False)
    except Exception as e:
        log.error(f"Failed to send adjustment notification: {e}")
        return False


if __name__ == '__main__':
    # Test the reporter with sample data
    print("Testing reporter with sample data...")

    # Sample analysis from analyzer.analyze_all()
    sample_analysis: dict[str, Any] = {
        'period_hours': 2,
        'trade_performance': {
            'total_trades': 5,
            'resolved_trades': 4,
            'wins': 3,
            'losses': 1,
            'win_rate': 0.75,
            'total_pnl': 7.70,
            'avg_pnl': 1.925,
            'avg_entry_price': 0.38,
            'avg_confidence': 0.62,
        },
        'skip_distribution': {
            'total_skips': 15,
            'by_type': {
                'SKIP_ENTRY_PRICE': 8,
                'SKIP_WEAK': 4,
                'SKIP_CONSENSUS': 2,
                'SKIP_OTHER': 1,
            },
            'by_type_pct': {
                'SKIP_ENTRY_PRICE': 0.533,
                'SKIP_WEAK': 0.267,
                'SKIP_CONSENSUS': 0.133,
                'SKIP_OTHER': 0.067,
            },
            'top_reason': 'SKIP_ENTRY_PRICE',
            'top_reason_pct': 0.533,
        },
        'veto_patterns': {
            'total_vetoes': 3,
            'by_reason': {'existing_position': 2, 'drawdown_limit': 1},
            'by_reason_pct': {'existing_position': 0.667, 'drawdown_limit': 0.333},
            'top_reason': 'existing_position',
            'top_reason_pct': 0.667,
        },
        'inactivity_diagnosis': 'normal_activity',
        'issues': [],
        'status': 'healthy',
    }

    # Sample adjustments
    sample_adjustments: list[dict[str, Any]] = [
        {
            'parameter': 'MAX_ENTRY_PRICE_CAP',
            'old_value': 0.50,
            'new_value': 0.55,
            'reason': 'Entry price filter blocking >40% of signals',
        },
    ]

    # Sample state
    sample_state: dict[str, Any] = {
        'current_balance': 185.50,
        'peak_balance': 200.00,
        'daily_pnl': 12.30,
    }

    print("\n=== Sample Healthy Report ===")
    message = _build_report_message(sample_analysis, [], sample_state)
    print(message)

    print("\n=== Sample Report with Adjustments ===")
    message = _build_report_message(sample_analysis, sample_adjustments, sample_state)
    print(message)

    # Test alert scenario
    sample_analysis['status'] = 'alert'
    sample_analysis['issues'] = ['no_trades_in_2h', 'high_skip_rate']

    print("\n=== Sample Alert Report ===")
    message = _build_report_message(sample_analysis, sample_adjustments, sample_state)
    print(message)

    print("\n--- Reporter test complete ---")
    print("Note: Actual Telegram sending requires valid credentials.")
