#!/usr/bin/env python3
"""
Optimizer Main Orchestrator

Main entry point for the hourly optimization system.
Run via cron on VPS to automatically review and tune bot parameters.

Usage:
    python3 optimizer/optimizer.py           # Normal run (applies changes)
    python3 optimizer/optimizer.py --dry-run # Preview changes without applying
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add optimizer directory to path for local imports, and parent for bot imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import optimizer modules (after sys.path setup)
from data_collector import (
    collect_trades,
    collect_skips,
    collect_vetoes,
    get_current_state,
)
from analyzer import analyze_all
from tuning_rules import select_tunings
from executor import apply_adjustments
from reporter import send_hourly_report


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = Path(__file__).parent / "optimizer_config.json"
STATE_DIR = Path(__file__).parent / "state"
LAST_REVIEW_PATH = STATE_DIR / "last_review.json"
RATE_LIMIT_PATH = STATE_DIR / "rate_limit.json"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    """Load optimizer configuration from JSON file."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        log.error(f"Config file not found: {CONFIG_PATH}")
        return {}
    except json.JSONDecodeError as e:
        log.error(f"Invalid JSON in config file: {e}")
        return {}


def get_timestamp() -> str:
    """Get ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def load_rate_limit_state() -> dict[str, Any]:
    """
    Load rate limit state from file.

    Returns:
        Dict with parameter names as keys and last adjustment timestamps as values.
    """
    if not RATE_LIMIT_PATH.exists():
        return {}

    try:
        with open(RATE_LIMIT_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_rate_limit_state(state: dict[str, Any]) -> None:
    """Save rate limit state to file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(RATE_LIMIT_PATH, 'w') as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        log.warning(f"Failed to save rate limit state: {e}")


def apply_rate_limiting(
    adjustments: list[dict[str, Any]],
    rate_limit_hours: int = 1
) -> list[dict[str, Any]]:
    """
    Filter adjustments to enforce rate limiting.

    Only allows 1 adjustment per parameter per hour.

    Args:
        adjustments: List of proposed adjustments
        rate_limit_hours: Hours between adjustments for same parameter

    Returns:
        Filtered list of adjustments that pass rate limiting
    """
    rate_state = load_rate_limit_state()
    now = datetime.now(timezone.utc)
    filtered: list[dict[str, Any]] = []

    for adj in adjustments:
        param = adj['parameter']
        last_adjusted = rate_state.get(param)

        if last_adjusted:
            try:
                last_time = datetime.fromisoformat(last_adjusted.replace(' UTC', '+00:00'))
                hours_since = (now - last_time).total_seconds() / 3600

                if hours_since < rate_limit_hours:
                    log.info(f"Rate limited: {param} was adjusted {hours_since:.1f}h ago")
                    continue
            except ValueError:
                # Invalid timestamp format - allow adjustment
                pass

        filtered.append(adj)
        # Update rate limit state
        rate_state[param] = get_timestamp()

    # Save updated state
    if filtered:
        save_rate_limit_state(rate_state)

    return filtered


def save_review_results(
    analysis: dict[str, Any],
    adjustments: list[dict[str, Any]],
    applied_results: dict[str, bool],
    dry_run: bool
) -> None:
    """Save review results to state/last_review.json."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        'timestamp': get_timestamp(),
        'dry_run': dry_run,
        'analysis': analysis,
        'proposed_adjustments': adjustments,
        'applied_results': applied_results,
    }

    try:
        with open(LAST_REVIEW_PATH, 'w') as f:
            json.dump(results, f, indent=2)
    except IOError as e:
        log.warning(f"Failed to save review results: {e}")


def run_optimizer(dry_run: bool = False) -> int:
    """
    Main optimizer execution flow.

    Args:
        dry_run: If True, analyze and report but don't apply changes

    Returns:
        Exit code: 0 for success, 1 for error
    """
    log.info("=" * 60)
    log.info("OPTIMIZER START" + (" (DRY RUN)" if dry_run else ""))
    log.info("=" * 60)

    # Load configuration
    config = load_config()
    if not config:
        log.error("Failed to load configuration")
        return 1

    lookback_hours = config.get('lookback_hours', 2)

    # Collect data
    log.info(f"Collecting data for last {lookback_hours} hours...")

    trades = collect_trades(lookback_hours)
    skips = collect_skips(lookback_hours)
    vetoes = collect_vetoes(lookback_hours)
    current_state = get_current_state()

    log.info(f"  Trades: {len(trades)}")
    log.info(f"  Skips: {len(skips)}")
    log.info(f"  Vetoes: {len(vetoes)}")

    # Analyze data
    log.info("Analyzing trading activity...")

    analysis = analyze_all(trades, skips, vetoes, hours=lookback_hours)

    log.info(f"  Status: {analysis.get('status', 'unknown')}")
    log.info(f"  Issues: {analysis.get('issues', [])}")
    log.info(f"  Diagnosis: {analysis.get('inactivity_diagnosis', 'N/A')}")

    # Select tuning adjustments
    log.info("Evaluating tuning rules...")

    raw_adjustments = select_tunings(analysis, config)
    log.info(f"  Proposed adjustments: {len(raw_adjustments)}")

    # Apply rate limiting
    adjustments = apply_rate_limiting(raw_adjustments, rate_limit_hours=1)
    log.info(f"  After rate limiting: {len(adjustments)}")

    for adj in adjustments:
        log.info(f"    {adj['parameter']}: {adj['old_value']} -> {adj['new_value']}")
        log.info(f"      Reason: {adj['reason']}")

    # Apply adjustments (unless dry run)
    applied_results: dict[str, bool] = {}

    if adjustments and not dry_run:
        log.info("Applying adjustments...")
        applied_results = apply_adjustments(adjustments, config, base_dir=PROJECT_ROOT)

        for param, success in applied_results.items():
            status = "SUCCESS" if success else "FAILED"
            log.info(f"  {param}: {status}")
    elif adjustments and dry_run:
        log.info("DRY RUN - Skipping adjustment application")
    else:
        log.info("No adjustments needed")

    # Send Telegram report
    log.info("Sending Telegram report...")

    # In dry run, don't send report with adjustments (they weren't applied)
    report_adjustments = [] if dry_run else adjustments
    silent = analysis.get('status') == 'healthy' and not report_adjustments

    report_sent = send_hourly_report(
        analysis=analysis,
        adjustments=report_adjustments,
        current_state=current_state,
        silent=silent
    )

    if report_sent:
        log.info("  Report sent successfully")
    else:
        log.warning("  Failed to send report (Telegram may be disabled)")

    # Save review results
    log.info("Saving review results...")
    save_review_results(analysis, adjustments, applied_results, dry_run)

    log.info("=" * 60)
    log.info("OPTIMIZER COMPLETE")
    log.info("=" * 60)

    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Optimizer - Hourly performance review and auto-tuning system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python3 optimizer/optimizer.py           # Normal run
    python3 optimizer/optimizer.py --dry-run # Preview without changes
        '''
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Analyze and report without applying changes'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose debug logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        return run_optimizer(dry_run=args.dry_run)
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        return 130
    except Exception as e:
        log.exception(f"Optimizer error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
