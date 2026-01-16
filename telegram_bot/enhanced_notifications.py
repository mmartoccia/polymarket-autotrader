#!/usr/bin/env python3
"""
Enhanced Telegram Notification Templates

Improved message formatting with:
- Better visual hierarchy
- More context and details
- Actionable information
- Risk indicators
- Performance metrics
"""

from datetime import datetime
from typing import Optional


def format_trade_notification(
    crypto: str,
    direction: str,
    entry_price: float,
    size: float,
    shares: int,
    confidence: float,
    agents_voted: list[str],
    strategy: str = "Unknown",
    balance: Optional[float] = None,
    position_count: Optional[int] = None,
    expected_return: Optional[float] = None
) -> str:
    """
    Format trade notification with comprehensive context.

    Returns rich formatted message with:
    - Trade details
    - Risk indicators
    - Expected outcomes
    - Context (balance, positions)
    """
    # Determine emoji and risk indicator
    direction_emoji = "📈" if direction == "Up" else "📉"

    # Risk level based on entry price
    if entry_price < 0.20:
        risk = "🟢 LOW"  # Cheap entry = low cost if wrong
        win_potential = f"${shares * (1.0 - entry_price):.2f} (+{((1.0 - entry_price) / entry_price * 100):.0f}%)"
    elif entry_price < 0.40:
        risk = "🟡 MEDIUM"
        win_potential = f"${shares * (1.0 - entry_price):.2f} (+{((1.0 - entry_price) / entry_price * 100):.0f}%)"
    else:
        risk = "🔴 HIGH"  # Expensive entry = high cost if wrong
        win_potential = f"${shares * (1.0 - entry_price):.2f} (+{((1.0 - entry_price) / entry_price * 100):.0f}%)"

    loss_potential = f"-${size:.2f} (-100%)"

    # Strategy emoji
    if "contrarian" in strategy.lower():
        strategy_emoji = "🔄"
        strategy_note = "Fading overpriced side"
    elif "late" in strategy.lower() or "confirmation" in strategy.lower():
        strategy_emoji = "✅"
        strategy_note = "High probability confirmation"
    elif "early" in strategy.lower() or "momentum" in strategy.lower():
        strategy_emoji = "🚀"
        strategy_note = "Early momentum capture"
    else:
        strategy_emoji = "🤖"
        strategy_note = "ML model signal"

    # Build message
    lines = [
        f"{strategy_emoji} *NEW TRADE OPENED*",
        "",
        f"{direction_emoji} *{crypto} {direction.upper()}* @ ${entry_price:.2f}",
        f"Position: {shares} shares = ${size:.2f}",
        f"Confidence: {confidence * 100:.1f}%",
        "",
        "📊 *EXPECTED OUTCOMES*",
        f"Win:  {win_potential}",
        f"Loss: {loss_potential}",
        f"Risk Level: {risk}",
        "",
        f"🤖 *STRATEGY*",
        f"{strategy}",
        f"_{strategy_note}_",
        "",
        f"🗳️ *AGENTS VOTED* ({len(agents_voted)})",
        f"{', '.join(agents_voted) if agents_voted else 'None'}",
    ]

    # Add context if available
    if balance is not None or position_count is not None:
        lines.append("")
        lines.append("📍 *CONTEXT*")
        if balance is not None:
            lines.append(f"Balance: ${balance:.2f}")
        if position_count is not None:
            lines.append(f"Open Positions: {position_count}")

    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}")

    return "\n".join(lines)


def format_redemption_notification(
    crypto: str,
    direction: str,
    outcome: str,
    pnl: float,
    shares_redeemed: int,
    entry_price: float,
    new_balance: float,
    epoch_duration: Optional[int] = None,
    win_rate_updated: Optional[float] = None
) -> str:
    """
    Format redemption notification with performance context.
    """
    # Outcome emoji
    if outcome == "win":
        outcome_emoji = "✅"
        outcome_text = "WINNER"
        direction_emoji = "🎉"
    else:
        outcome_emoji = "❌"
        outcome_text = "EXPIRED"
        direction_emoji = "💨"

    # PnL formatting
    pnl_sign = "+" if pnl >= 0 else ""
    pnl_emoji = "📈" if pnl >= 0 else "📉"

    # Calculate ROI
    cost = shares_redeemed * entry_price if outcome == "win" else entry_price * (pnl / -1.0) if pnl < 0 else 0
    roi = (pnl / cost * 100) if cost > 0 else 0

    lines = [
        f"{outcome_emoji} *POSITION REDEEMED*",
        "",
        f"{direction_emoji} *{crypto} {direction.upper()}* - {outcome_text}",
        f"Entry: ${entry_price:.2f} × {shares_redeemed if outcome == 'win' else int(cost / entry_price) if entry_price > 0 else 0} shares",
    ]

    if outcome == "win":
        lines.append(f"Redeemed: {shares_redeemed} shares = ${shares_redeemed * 1.0:.2f}")
    else:
        lines.append(f"Expired: Worthless ($0.00)")

    lines.extend([
        "",
        f"{pnl_emoji} *RESULT*",
        f"P&L: ${pnl_sign}{pnl:.2f} ({pnl_sign}{roi:.1f}%)",
        f"New Balance: ${new_balance:.2f}",
    ])

    if epoch_duration:
        lines.append(f"Duration: {epoch_duration} minutes")

    if win_rate_updated is not None:
        lines.append("")
        lines.append(f"📊 Win Rate: {win_rate_updated * 100:.1f}%")

    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}")

    return "\n".join(lines)


def format_alert_notification(
    level: str,
    title: str,
    message: str,
    recommended_action: Optional[str] = None,
    current_balance: Optional[float] = None,
    current_drawdown: Optional[float] = None
) -> str:
    """
    Format alert notification with actionable context.
    """
    # Level emoji
    if level == "critical":
        level_emoji = "🚨"
        level_text = "CRITICAL ALERT"
    elif level == "warning":
        level_emoji = "⚠️"
        level_text = "WARNING"
    else:
        level_emoji = "ℹ️"
        level_text = "INFO"

    lines = [
        f"{level_emoji} *{level_text}*",
        "",
        f"*{title}*",
        "",
        message,
    ]

    if current_balance is not None or current_drawdown is not None:
        lines.append("")
        lines.append("📊 *STATUS*")
        if current_balance is not None:
            lines.append(f"Balance: ${current_balance:.2f}")
        if current_drawdown is not None:
            dd_emoji = "🔴" if current_drawdown > 0.25 else "🟡" if current_drawdown > 0.15 else "🟢"
            lines.append(f"Drawdown: {dd_emoji} {current_drawdown * 100:.1f}%")

    if recommended_action:
        lines.append("")
        lines.append(f"💡 *RECOMMENDED ACTION*")
        lines.append(recommended_action)

    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}")

    return "\n".join(lines)


def format_daily_summary(
    date: str,
    daily_pnl: float,
    total_trades: int,
    wins: int,
    losses: int,
    win_rate: float,
    best_trade: float,
    worst_trade: float,
    starting_balance: float,
    ending_balance: float,
    peak_balance: float,
    top_shadow_strategy: Optional[dict] = None
) -> str:
    """
    Format comprehensive daily summary.
    """
    pnl_sign = "+" if daily_pnl >= 0 else ""
    pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
    day_emoji = "🎉" if daily_pnl > 0 else "😔" if daily_pnl < 0 else "😐"

    roi = (daily_pnl / starting_balance * 100) if starting_balance > 0 else 0

    lines = [
        f"📊 *DAILY SUMMARY* {day_emoji}",
        "",
        f"📅 {date}",
        "",
        f"{pnl_emoji} *PERFORMANCE*",
        f"P&L: ${pnl_sign}{daily_pnl:.2f} ({pnl_sign}{roi:.1f}%)",
        f"Trades: {total_trades} ({wins}W / {losses}L)",
        f"Win Rate: {win_rate * 100:.1f}%",
        "",
        f"🎯 *BEST/WORST*",
        f"Best: ${best_trade:+.2f}",
        f"Worst: ${worst_trade:+.2f}",
        "",
        f"💰 *BALANCE*",
        f"Start: ${starting_balance:.2f}",
        f"End: ${ending_balance:.2f}",
        f"Peak: ${peak_balance:.2f}",
    ]

    if top_shadow_strategy:
        lines.append("")
        lines.append("🏆 *TOP SHADOW STRATEGY*")
        lines.append(f"{top_shadow_strategy['name']}")
        lines.append(f"Win Rate: {top_shadow_strategy['win_rate'] * 100:.1f}%")
        lines.append(f"P&L: ${top_shadow_strategy['pnl']:+.2f}")

    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}")

    return "\n".join(lines)


def format_position_update(
    crypto: str,
    direction: str,
    current_price: float,
    entry_price: float,
    probability: float,
    unrealized_pnl: float,
    time_remaining: int
) -> str:
    """
    Format position status update notification.
    """
    direction_emoji = "📈" if direction == "Up" else "📉"

    # Trend indicator
    if probability > 0.80:
        status = "✅ WINNING"
    elif probability > 0.50:
        status = "🟢 LIKELY"
    elif probability > 0.30:
        status = "🟡 UNCERTAIN"
    else:
        status = "❌ LOSING"

    pnl_sign = "+" if unrealized_pnl >= 0 else ""

    lines = [
        f"📍 *POSITION UPDATE*",
        "",
        f"{direction_emoji} *{crypto} {direction.upper()}*",
        f"Entry: ${entry_price:.2f}",
        f"Current: ${current_price:.2f}",
        f"Probability: {probability * 100:.1f}% {status}",
        "",
        f"Unrealized P&L: ${pnl_sign}{unrealized_pnl:.2f}",
        f"Time Remaining: {time_remaining} min",
        "",
        f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}"
    ]

    return "\n".join(lines)


def format_halt_notification(
    reason: str,
    current_balance: float,
    peak_balance: float,
    drawdown: float,
    recovery_instructions: str
) -> str:
    """
    Format bot halt notification with recovery instructions.
    """
    lines = [
        "🛑 *BOT HALTED*",
        "",
        f"*Reason:* {reason}",
        "",
        "📊 *CURRENT STATE*",
        f"Balance: ${current_balance:.2f}",
        f"Peak: ${peak_balance:.2f}",
        f"Drawdown: 🔴 {drawdown * 100:.1f}%",
        "",
        "🔧 *RECOVERY INSTRUCTIONS*",
        recovery_instructions,
        "",
        "Use /resume to restart trading (after recovery)",
        "",
        f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}"
    ]

    return "\n".join(lines)


def format_mode_change_notification(
    old_mode: str,
    new_mode: str,
    reason: str,
    position_sizing_change: Optional[str] = None
) -> str:
    """
    Format trading mode change notification.
    """
    mode_emojis = {
        'normal': '🟢',
        'conservative': '🟡',
        'defensive': '🟠',
        'recovery': '🔴',
        'halted': '🛑'
    }

    old_emoji = mode_emojis.get(old_mode, '⚪')
    new_emoji = mode_emojis.get(new_mode, '⚪')

    lines = [
        "⚙️ *MODE CHANGE*",
        "",
        f"{old_emoji} {old_mode.upper()} → {new_emoji} {new_mode.upper()}",
        "",
        f"*Reason:* {reason}",
    ]

    if position_sizing_change:
        lines.append("")
        lines.append("📊 *POSITION SIZING*")
        lines.append(position_sizing_change)

    lines.append("")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M:%S UTC')}")

    return "\n".join(lines)
