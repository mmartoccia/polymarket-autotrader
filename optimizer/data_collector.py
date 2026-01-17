"""
Data Collection Module for Optimizer

Collects trading data from logs, database, and state files.
Designed to run on VPS with direct file access.
"""

import json
import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# File paths (relative to project root on VPS)
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "simulation" / "trade_journal.db"
STATE_FILE = PROJECT_ROOT / "state" / "intra_epoch_state.json"
BOT_LOG = PROJECT_ROOT / "bot.log"


def collect_trades(hours: int = 2) -> list[dict[str, Any]]:
    """
    Get trades from SQLite trade_journal.db for the specified time period.

    Args:
        hours: Number of hours to look back (default 2)

    Returns:
        List of trade dicts with: crypto, epoch, direction, entry_price,
        size, shares, confidence, timestamp, pnl (if resolved)
    """
    if not DB_PATH.exists():
        return []

    cutoff_ts = datetime.now().timestamp() - (hours * 3600)
    trades: list[dict[str, Any]] = []

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get trades with optional outcome info
        query = """
            SELECT
                t.id,
                t.strategy,
                t.crypto,
                t.epoch,
                t.direction,
                t.entry_price,
                t.size,
                t.shares,
                t.confidence,
                t.weighted_score,
                t.timestamp,
                o.actual_direction,
                o.pnl,
                o.payout
            FROM trades t
            LEFT JOIN outcomes o ON t.id = o.trade_id AND t.strategy = o.strategy
            WHERE t.timestamp >= ? AND t.strategy = 'live'
            ORDER BY t.timestamp DESC
        """

        cursor.execute(query, (cutoff_ts,))

        for row in cursor.fetchall():
            trade = dict(row)
            # Determine win/loss if outcome exists
            if trade.get('actual_direction'):
                trade['resolved'] = True
                trade['won'] = trade['direction'] == trade['actual_direction']
            else:
                trade['resolved'] = False
                trade['won'] = None
            trades.append(trade)

        conn.close()

    except sqlite3.Error:
        # Database error - return empty list
        pass

    return trades


def collect_skips(hours: int = 2) -> list[dict[str, Any]]:
    """
    Get skip decisions from SQLite decisions table.

    Args:
        hours: Number of hours to look back (default 2)

    Returns:
        List of skip dicts with: crypto, epoch, reason, confidence, timestamp
    """
    if not DB_PATH.exists():
        return []

    cutoff_ts = datetime.now().timestamp() - (hours * 3600)
    skips: list[dict[str, Any]] = []

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get decisions where should_trade is False (skipped)
        query = """
            SELECT
                crypto,
                epoch,
                timestamp,
                reason,
                confidence,
                weighted_score
            FROM decisions
            WHERE should_trade = 0
              AND timestamp >= ?
              AND strategy = 'live'
            ORDER BY timestamp DESC
        """

        cursor.execute(query, (cutoff_ts,))

        for row in cursor.fetchall():
            skip = dict(row)
            # Categorize the skip reason
            skip['skip_type'] = _categorize_skip_reason(skip.get('reason', ''))
            skips.append(skip)

        conn.close()

    except sqlite3.Error:
        pass

    return skips


def _categorize_skip_reason(reason: str) -> str:
    """
    Categorize a skip reason into a standard type.

    Skip types:
    - SKIP_WEAK: Pattern too weak
    - SKIP_ENTRY_PRICE: Entry price too high
    - SKIP_CONFLUENCE: Confluence mismatch or missing
    - SKIP_CONFIDENCE: Confidence too low
    - SKIP_CONSENSUS: Consensus threshold not met
    - SKIP_OTHER: Unknown or uncategorized
    """
    reason_lower = reason.lower() if reason else ''

    if 'weak' in reason_lower or 'pattern' in reason_lower:
        return 'SKIP_WEAK'
    elif 'entry' in reason_lower or 'price' in reason_lower:
        return 'SKIP_ENTRY_PRICE'
    elif 'confluence' in reason_lower or 'mismatch' in reason_lower:
        return 'SKIP_CONFLUENCE'
    elif 'confidence' in reason_lower:
        return 'SKIP_CONFIDENCE'
    elif 'consensus' in reason_lower or 'threshold' in reason_lower:
        return 'SKIP_CONSENSUS'
    else:
        return 'SKIP_OTHER'


def collect_vetoes(hours: int = 2) -> list[str]:
    """
    Parse VETO lines from bot.log.

    Args:
        hours: Number of hours to look back (default 2)

    Returns:
        List of veto reason strings
    """
    if not BOT_LOG.exists():
        return []

    cutoff_time = datetime.now() - timedelta(hours=hours)
    vetoes: list[str] = []

    # Pattern for log lines with timestamps and VETO
    # Format: 2026-01-17 10:30:15 INFO ... VETO ...
    log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})')
    veto_pattern = re.compile(r'VETO[:\s]+(.+)', re.IGNORECASE)

    try:
        with open(BOT_LOG, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Check for timestamp
                ts_match = log_pattern.match(line)
                if ts_match:
                    try:
                        line_time = datetime.strptime(ts_match.group(1), '%Y-%m-%d %H:%M:%S')
                        if line_time < cutoff_time:
                            continue
                    except ValueError:
                        continue

                # Check for VETO
                veto_match = veto_pattern.search(line)
                if veto_match:
                    vetoes.append(veto_match.group(1).strip())

    except IOError:
        pass

    return vetoes


def get_current_state() -> dict[str, Any]:
    """
    Read current state from intra_epoch_state.json.

    Returns:
        Dict with state fields: current_balance, peak_balance, mode,
        consecutive_wins, consecutive_losses, total_trades, total_wins, etc.
        Returns empty dict if file doesn't exist.
    """
    if not STATE_FILE.exists():
        return {}

    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def get_trade_summary(hours: int = 2) -> dict[str, Any]:
    """
    Get a quick summary of recent trading activity.

    Returns dict with:
    - total_trades: Number of trades in period
    - resolved_trades: Number with known outcomes
    - wins: Number of wins
    - losses: Number of losses
    - win_rate: Win percentage (or None if no resolved trades)
    - total_pnl: Sum of P&L
    - skips: Number of skip decisions
    """
    trades = collect_trades(hours)
    skips = collect_skips(hours)

    resolved = [t for t in trades if t.get('resolved')]
    wins = sum(1 for t in resolved if t.get('won'))
    losses = len(resolved) - wins
    total_pnl = sum(t.get('pnl', 0) or 0 for t in resolved)

    return {
        'total_trades': len(trades),
        'resolved_trades': len(resolved),
        'wins': wins,
        'losses': losses,
        'win_rate': wins / len(resolved) if resolved else None,
        'total_pnl': total_pnl,
        'skips': len(skips),
        'period_hours': hours
    }


if __name__ == '__main__':
    # Test the data collector
    print("Testing data collector...")
    print(f"\nDB Path: {DB_PATH}")
    print(f"DB exists: {DB_PATH.exists()}")
    print(f"\nState File: {STATE_FILE}")
    print(f"State exists: {STATE_FILE.exists()}")
    print(f"\nBot Log: {BOT_LOG}")
    print(f"Log exists: {BOT_LOG.exists()}")

    print("\n--- Trade Summary (2h) ---")
    summary = get_trade_summary(2)
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print("\n--- Current State ---")
    state = get_current_state()
    for k, v in state.items():
        print(f"  {k}: {v}")

    print("\n--- Recent Trades ---")
    trades = collect_trades(2)
    print(f"  Found {len(trades)} trades")
    for t in trades[:3]:
        print(f"    {t.get('crypto')} {t.get('direction')} @ ${t.get('entry_price', 0):.2f}")

    print("\n--- Recent Skips ---")
    skips = collect_skips(2)
    print(f"  Found {len(skips)} skips")
    skip_types: dict[str, int] = {}
    for s in skips:
        skip_types[s['skip_type']] = skip_types.get(s['skip_type'], 0) + 1
    for st, count in sorted(skip_types.items(), key=lambda x: -x[1]):
        print(f"    {st}: {count}")

    print("\n--- Recent Vetoes ---")
    vetoes = collect_vetoes(2)
    print(f"  Found {len(vetoes)} vetoes")
    for v in vetoes[:5]:
        print(f"    {v}")
