"""
Parameter Adjustment Executor for Optimizer

Safely applies parameter changes to config files with:
- Backup before modification
- Regex-based value replacement
- Audit logging
- State tracking
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Base directory for the project (parent of optimizer/)
BASE_DIR = Path(__file__).parent.parent


def _get_timestamp() -> str:
    """Get ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def _create_backup(file_path: Path) -> Path | None:
    """
    Create a backup of a file before modification.

    Args:
        file_path: Path to the file to backup

    Returns:
        Path to backup file, or None if backup failed
    """
    try:
        backup_path = file_path.with_suffix(file_path.suffix + '.bak')
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception:
        return None


def _build_param_regex(param: str) -> re.Pattern[str]:
    """
    Build regex pattern to match parameter assignment.

    Matches patterns like:
        PARAM_NAME = 0.50
        PARAM_NAME = 0.735    # comment
        PARAM_NAME=0.50

    Captures:
        - Group 1: Everything before the value (param name + whitespace + =)
        - Group 2: The numeric value
        - Group 3: Everything after (whitespace/comment to end of line)
    """
    # Match: param_name (optional whitespace) = (optional whitespace) value (rest of line)
    pattern = rf'^({param}\s*=\s*)(\d+\.?\d*)(.*?)$'
    return re.compile(pattern, re.MULTILINE)


def _replace_param_value(content: str, param: str, new_value: float) -> tuple[str, bool]:
    """
    Replace a parameter value in file content.

    Args:
        content: File content
        param: Parameter name
        new_value: New value to set

    Returns:
        Tuple of (modified_content, success)
    """
    regex = _build_param_regex(param)

    # Format new value - use appropriate precision
    if new_value == int(new_value):
        new_value_str = str(int(new_value))
    elif new_value * 100 == int(new_value * 100):
        new_value_str = f'{new_value:.2f}'
    else:
        new_value_str = f'{new_value:.3f}'

    # Check if parameter exists
    if not regex.search(content):
        return content, False

    # Replace value, preserving everything else
    new_content = regex.sub(rf'\g<1>{new_value_str}\g<3>', content)

    return new_content, content != new_content


def _log_adjustment(
    param: str,
    old_value: float,
    new_value: float,
    reason: str,
    file_path: str,
    history_dir: Path
) -> bool:
    """
    Log adjustment to history/adjustments.txt.

    Format:
        [timestamp] PARAM_NAME: old_value -> new_value (file) - reason

    Returns:
        True if logged successfully
    """
    try:
        log_file = history_dir / 'adjustments.txt'
        timestamp = _get_timestamp()

        log_entry = f'[{timestamp}] {param}: {old_value} -> {new_value} ({file_path}) - {reason}\n'

        with open(log_file, 'a') as f:
            f.write(log_entry)

        return True
    except Exception:
        return False


def _update_parameter_history(
    param: str,
    old_value: float,
    new_value: float,
    reason: str,
    rule_name: str,
    state_dir: Path
) -> bool:
    """
    Update state/parameter_history.json with change record.

    JSON structure:
    {
        "PARAM_NAME": [
            {"timestamp": "...", "old": 0.50, "new": 0.55, "reason": "...", "rule": "..."},
            ...
        ]
    }

    Returns:
        True if updated successfully
    """
    try:
        history_file = state_dir / 'parameter_history.json'

        # Load existing history or create new
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
        else:
            history = {}

        # Ensure parameter has entry
        if param not in history:
            history[param] = []

        # Add new record
        record = {
            'timestamp': _get_timestamp(),
            'old': old_value,
            'new': new_value,
            'reason': reason,
            'rule': rule_name,
        }
        history[param].append(record)

        # Write back
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)

        return True
    except Exception:
        return False


def apply_adjustment(
    param: str,
    old_value: float,
    new_value: float,
    reason: str,
    rule_name: str,
    config: dict[str, Any],
    base_dir: Path | None = None
) -> bool:
    """
    Apply a parameter adjustment to the appropriate config file.

    Args:
        param: Parameter name (e.g., 'MAX_ENTRY_PRICE_CAP')
        old_value: Expected current value
        new_value: New value to set
        reason: Human-readable reason for the change
        rule_name: Name of the tuning rule that triggered this
        config: Config dict with tunable_parameters info
        base_dir: Base directory (default: project root)

    Returns:
        True if adjustment was applied successfully, False otherwise

    Process:
        1. Determine target file from config
        2. Create backup
        3. Read and modify file content
        4. Write modified content
        5. Log to adjustments.txt
        6. Update parameter_history.json
    """
    if base_dir is None:
        base_dir = BASE_DIR

    # Get parameter config
    tunable = config.get('tunable_parameters', {})
    if param not in tunable:
        return False

    param_config = tunable[param]
    relative_file_path = param_config.get('file')
    if not relative_file_path:
        return False

    # Resolve paths
    target_file = base_dir / relative_file_path
    history_dir = base_dir / 'optimizer' / 'history'
    state_dir = base_dir / 'optimizer' / 'state'

    # Check target file exists
    if not target_file.exists():
        return False

    # Create backup
    backup = _create_backup(target_file)
    if backup is None:
        return False

    try:
        # Read file
        with open(target_file, 'r') as f:
            content = f.read()

        # Replace value
        new_content, changed = _replace_param_value(content, param, new_value)

        if not changed:
            # Value not found or already at target - restore backup
            return False

        # Write modified content
        with open(target_file, 'w') as f:
            f.write(new_content)

        # Log to history
        _log_adjustment(param, old_value, new_value, reason, relative_file_path, history_dir)

        # Update parameter history
        _update_parameter_history(param, old_value, new_value, reason, rule_name, state_dir)

        # Update config's "current" value for tracking
        # (This is in-memory only - the source of truth is the actual file)
        param_config['current'] = new_value

        return True

    except Exception:
        # Attempt to restore backup on failure
        try:
            shutil.copy2(backup, target_file)
        except Exception:
            pass
        return False


def apply_adjustments(
    adjustments: list[dict[str, Any]],
    config: dict[str, Any],
    base_dir: Path | None = None
) -> dict[str, bool]:
    """
    Apply multiple adjustments.

    Args:
        adjustments: List of adjustment dicts from tuning_rules.select_tunings()
        config: Config dict with tunable_parameters info
        base_dir: Base directory (default: project root)

    Returns:
        Dict mapping parameter name to success status
    """
    results: dict[str, bool] = {}

    for adj in adjustments:
        param = adj['parameter']
        success = apply_adjustment(
            param=param,
            old_value=adj['old_value'],
            new_value=adj['new_value'],
            reason=adj.get('reason', 'No reason provided'),
            rule_name=adj.get('rule_name', 'unknown'),
            config=config,
            base_dir=base_dir,
        )
        results[param] = success

    return results


def get_adjustment_history(base_dir: Path | None = None, limit: int = 20) -> list[str]:
    """
    Read recent entries from adjustments.txt.

    Args:
        base_dir: Base directory (default: project root)
        limit: Maximum number of entries to return

    Returns:
        List of log entries (most recent first)
    """
    if base_dir is None:
        base_dir = BASE_DIR

    log_file = base_dir / 'optimizer' / 'history' / 'adjustments.txt'

    if not log_file.exists():
        return []

    try:
        with open(log_file) as f:
            lines = f.readlines()

        # Return most recent entries
        return [line.strip() for line in lines[-limit:]][::-1]
    except Exception:
        return []


def get_parameter_history(param: str, base_dir: Path | None = None) -> list[dict[str, Any]]:
    """
    Get change history for a specific parameter.

    Args:
        param: Parameter name
        base_dir: Base directory (default: project root)

    Returns:
        List of change records (most recent first)
    """
    if base_dir is None:
        base_dir = BASE_DIR

    history_file = base_dir / 'optimizer' / 'state' / 'parameter_history.json'

    if not history_file.exists():
        return []

    try:
        with open(history_file) as f:
            history = json.load(f)

        return history.get(param, [])[::-1]
    except Exception:
        return []


if __name__ == '__main__':
    # Test the executor with sample data
    import tempfile

    print("Testing executor.py...")

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create directory structure
        (tmp_path / 'bot').mkdir()
        (tmp_path / 'config').mkdir()
        (tmp_path / 'optimizer' / 'history').mkdir(parents=True)
        (tmp_path / 'optimizer' / 'state').mkdir(parents=True)

        # Create test bot file
        bot_content = '''# Trading parameters
EDGE_BUFFER = 0.05              # Require 5% edge
MIN_PATTERN_ACCURACY = 0.735    # Only trade 73.5%+ patterns
MAX_ENTRY_PRICE_CAP = 0.50
'''
        with open(tmp_path / 'bot' / 'intra_epoch_bot.py', 'w') as f:
            f.write(bot_content)

        # Create test config file
        config_content = '''# Agent config
CONSENSUS_THRESHOLD = 0.40     # Validated threshold
MIN_CONFIDENCE = 0.50          # Require 50% confidence
'''
        with open(tmp_path / 'config' / 'agent_config.py', 'w') as f:
            f.write(config_content)

        # Create adjustments.txt
        (tmp_path / 'optimizer' / 'history' / 'adjustments.txt').touch()

        # Test config
        test_config = {
            'tunable_parameters': {
                'MAX_ENTRY_PRICE_CAP': {
                    'file': 'bot/intra_epoch_bot.py',
                    'current': 0.50,
                    'min': 0.35,
                    'max': 0.65,
                    'step': 0.05,
                },
                'CONSENSUS_THRESHOLD': {
                    'file': 'config/agent_config.py',
                    'current': 0.40,
                    'min': 0.30,
                    'max': 0.55,
                    'step': 0.05,
                },
            },
            'protected_parameters': [],
        }

        # Test 1: Apply single adjustment
        print("\n--- Test 1: Apply single adjustment ---")
        success = apply_adjustment(
            param='MAX_ENTRY_PRICE_CAP',
            old_value=0.50,
            new_value=0.55,
            reason='Testing executor',
            rule_name='test_rule',
            config=test_config,
            base_dir=tmp_path,
        )
        print(f"Success: {success}")

        # Verify file was modified
        with open(tmp_path / 'bot' / 'intra_epoch_bot.py') as f:
            modified = f.read()
        print(f"File contains '0.55': {'0.55' in modified}")

        # Verify backup exists
        backup_exists = (tmp_path / 'bot' / 'intra_epoch_bot.py.bak').exists()
        print(f"Backup exists: {backup_exists}")

        # Verify history logged
        history = get_adjustment_history(base_dir=tmp_path)
        print(f"History entries: {len(history)}")
        if history:
            print(f"  Latest: {history[0][:60]}...")

        # Test 2: Apply multiple adjustments
        print("\n--- Test 2: Apply multiple adjustments ---")
        adjustments = [
            {
                'parameter': 'CONSENSUS_THRESHOLD',
                'old_value': 0.40,
                'new_value': 0.35,
                'reason': 'Test decrease',
                'rule_name': 'test_consensus',
            },
        ]
        results = apply_adjustments(adjustments, test_config, base_dir=tmp_path)
        print(f"Results: {results}")

        # Test 3: Invalid parameter
        print("\n--- Test 3: Invalid parameter (should fail) ---")
        success = apply_adjustment(
            param='NONEXISTENT_PARAM',
            old_value=1.0,
            new_value=2.0,
            reason='Should fail',
            rule_name='test_fail',
            config=test_config,
            base_dir=tmp_path,
        )
        print(f"Success (should be False): {success}")

        # Test 4: Get parameter history
        print("\n--- Test 4: Get parameter history ---")
        param_history = get_parameter_history('MAX_ENTRY_PRICE_CAP', base_dir=tmp_path)
        print(f"Parameter history entries: {len(param_history)}")
        if param_history:
            print(f"  Latest: {param_history[0]}")

        print("\n✅ All tests completed!")
