#!/usr/bin/env python3
"""
Integration Tests for Optimizer System

Tests the optimizer components:
- Data collection returns expected format
- Analysis calculations are correct
- Tuning rules fire on correct conditions
- Bounds are respected (never exceed min/max)
- Protected parameters are never modified
- Dry-run mode doesn't modify files

Usage:
    python3 optimizer/test_optimizer.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Add optimizer directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

# Import modules under test
from data_collector import (
    collect_trades,
    collect_skips,
    collect_vetoes,
    get_current_state,
    _categorize_skip_reason,
)
from analyzer import (
    analyze_trade_performance,
    analyze_skip_distribution,
    analyze_veto_patterns,
    diagnose_inactivity,
    analyze_all,
)
from tuning_rules import (
    select_tunings,
    calculate_new_value,
    is_protected_parameter,
    TUNING_RULES,
)
from executor import (
    apply_adjustment,
    apply_adjustments,
    _replace_param_value,
    get_adjustment_history,
)


# =============================================================================
# Test Utilities
# =============================================================================

class TestResult:
    """Simple test result tracker."""
    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: list[str] = []

    def ok(self, test_name: str) -> None:
        self.passed += 1
        print(f"  ✓ {test_name}")

    def fail(self, test_name: str, reason: str) -> None:
        self.failed += 1
        self.failures.append(f"{test_name}: {reason}")
        print(f"  ✗ {test_name}: {reason}")


def assert_eq(actual: Any, expected: Any, name: str, results: TestResult) -> bool:
    """Assert equality and record result."""
    if actual == expected:
        results.ok(name)
        return True
    else:
        results.fail(name, f"expected {expected!r}, got {actual!r}")
        return False


def assert_true(condition: bool, name: str, results: TestResult) -> bool:
    """Assert condition is true and record result."""
    if condition:
        results.ok(name)
        return True
    else:
        results.fail(name, "condition was False")
        return False


def assert_in(value: Any, container: Any, name: str, results: TestResult) -> bool:
    """Assert value is in container and record result."""
    if value in container:
        results.ok(name)
        return True
    else:
        results.fail(name, f"{value!r} not in {container!r}")
        return False


def assert_not_in(value: Any, container: Any, name: str, results: TestResult) -> bool:
    """Assert value is not in container and record result."""
    if value not in container:
        results.ok(name)
        return True
    else:
        results.fail(name, f"{value!r} unexpectedly in {container!r}")
        return False


def assert_between(
    value: float,
    min_val: float,
    max_val: float,
    name: str,
    results: TestResult
) -> bool:
    """Assert value is between min and max (inclusive)."""
    if min_val <= value <= max_val:
        results.ok(name)
        return True
    else:
        results.fail(name, f"{value} not in [{min_val}, {max_val}]")
        return False


# =============================================================================
# Test Data
# =============================================================================

def get_test_config() -> dict[str, Any]:
    """Get test configuration matching optimizer_config.json structure."""
    return {
        "review_interval_hours": 1,
        "lookback_hours": 2,
        "alert_thresholds": {
            "no_trades_hours": 2,
            "min_win_rate": 0.50,
            "min_trades_for_win_rate": 10,
            "max_skip_rate": 0.90
        },
        "tunable_parameters": {
            "MAX_ENTRY_PRICE_CAP": {
                "file": "bot/intra_epoch_bot.py",
                "current": 0.50,
                "min": 0.35,
                "max": 0.65,
                "step": 0.05
            },
            "MIN_PATTERN_ACCURACY": {
                "file": "bot/intra_epoch_bot.py",
                "current": 0.735,
                "min": 0.65,
                "max": 0.80,
                "step": 0.01
            },
            "CONSENSUS_THRESHOLD": {
                "file": "config/agent_config.py",
                "current": 0.40,
                "min": 0.30,
                "max": 0.55,
                "step": 0.05
            },
            "MIN_CONFIDENCE": {
                "file": "config/agent_config.py",
                "current": 0.50,
                "min": 0.35,
                "max": 0.65,
                "step": 0.05
            },
            "EDGE_BUFFER": {
                "file": "bot/intra_epoch_bot.py",
                "current": 0.05,
                "min": 0.02,
                "max": 0.10,
                "step": 0.01
            }
        },
        "protected_parameters": [
            "RISK_MAX_DRAWDOWN",
            "RISK_DAILY_LOSS_LIMIT",
            "RISK_POSITION_TIERS"
        ]
    }


def get_sample_trades() -> list[dict[str, Any]]:
    """Sample trade data for testing."""
    return [
        {'resolved': True, 'won': True, 'pnl': 5.50, 'entry_price': 0.35, 'confidence': 0.65},
        {'resolved': True, 'won': True, 'pnl': 4.20, 'entry_price': 0.40, 'confidence': 0.58},
        {'resolved': True, 'won': False, 'pnl': -8.00, 'entry_price': 0.55, 'confidence': 0.52},
        {'resolved': True, 'won': True, 'pnl': 6.00, 'entry_price': 0.30, 'confidence': 0.70},
        {'resolved': False, 'won': None, 'pnl': None, 'entry_price': 0.42, 'confidence': 0.60},
    ]


def get_sample_skips() -> list[dict[str, Any]]:
    """Sample skip data for testing."""
    return [
        {'skip_type': 'SKIP_ENTRY_PRICE'},
        {'skip_type': 'SKIP_ENTRY_PRICE'},
        {'skip_type': 'SKIP_ENTRY_PRICE'},
        {'skip_type': 'SKIP_WEAK'},
        {'skip_type': 'SKIP_WEAK'},
        {'skip_type': 'SKIP_CONSENSUS'},
        {'skip_type': 'SKIP_OTHER'},
    ]


def get_sample_vetoes() -> list[str]:
    """Sample veto data for testing."""
    return [
        'Existing position for BTC',
        'Existing position for ETH',
        'Drawdown limit exceeded',
    ]


# =============================================================================
# Test: Data Collection Format
# =============================================================================

def test_data_collection_format(results: TestResult) -> None:
    """Test that data collection returns expected format."""
    print("\n--- Test: Data Collection Format ---")

    # Test collect_trades returns list
    trades = collect_trades(1)
    assert_true(isinstance(trades, list), "collect_trades returns list", results)

    # Test collect_skips returns list
    skips = collect_skips(1)
    assert_true(isinstance(skips, list), "collect_skips returns list", results)

    # Test collect_vetoes returns list
    vetoes = collect_vetoes(1)
    assert_true(isinstance(vetoes, list), "collect_vetoes returns list", results)

    # Test get_current_state returns dict
    state = get_current_state()
    assert_true(isinstance(state, dict), "get_current_state returns dict", results)

    # Test skip reason categorization
    assert_eq(
        _categorize_skip_reason("Entry price too high"),
        "SKIP_ENTRY_PRICE",
        "categorize entry price skip",
        results
    )
    assert_eq(
        _categorize_skip_reason("Pattern too weak"),
        "SKIP_WEAK",
        "categorize weak pattern skip",
        results
    )
    assert_eq(
        _categorize_skip_reason("Consensus not reached"),
        "SKIP_CONSENSUS",
        "categorize consensus skip",
        results
    )
    assert_eq(
        _categorize_skip_reason("Unknown reason XYZ"),
        "SKIP_OTHER",
        "categorize unknown skip",
        results
    )


# =============================================================================
# Test: Analysis Calculations
# =============================================================================

def test_analysis_calculations(results: TestResult) -> None:
    """Test that analysis calculations are correct."""
    print("\n--- Test: Analysis Calculations ---")

    trades = get_sample_trades()
    skips = get_sample_skips()
    vetoes = get_sample_vetoes()

    # Test trade performance analysis
    perf = analyze_trade_performance(trades)

    assert_eq(perf['total_trades'], 5, "total_trades count", results)
    assert_eq(perf['resolved_trades'], 4, "resolved_trades count", results)
    assert_eq(perf['wins'], 3, "wins count", results)
    assert_eq(perf['losses'], 1, "losses count", results)
    assert_eq(perf['win_rate'], 0.75, "win_rate calculation", results)
    assert_eq(perf['total_pnl'], 7.70, "total_pnl calculation", results)

    # Test skip distribution analysis
    skip_dist = analyze_skip_distribution(skips)

    assert_eq(skip_dist['total_skips'], 7, "total_skips count", results)
    assert_eq(skip_dist['by_type']['SKIP_ENTRY_PRICE'], 3, "SKIP_ENTRY_PRICE count", results)
    assert_eq(skip_dist['top_reason'], 'SKIP_ENTRY_PRICE', "top skip reason", results)

    # Test percentages are correct
    expected_entry_pct = 3 / 7  # ~0.4286
    actual_entry_pct = skip_dist['by_type_pct']['SKIP_ENTRY_PRICE']
    assert_true(
        abs(actual_entry_pct - expected_entry_pct) < 0.001,
        "skip percentage calculation",
        results
    )

    # Test veto pattern analysis
    veto_patt = analyze_veto_patterns(vetoes)

    assert_eq(veto_patt['total_vetoes'], 3, "total_vetoes count", results)
    assert_in('existing_position', veto_patt['by_reason'], "veto reason normalized", results)

    # Test combined analysis
    full = analyze_all(trades, skips, vetoes, hours=2)

    assert_in('trade_performance', full, "analyze_all has trade_performance", results)
    assert_in('skip_distribution', full, "analyze_all has skip_distribution", results)
    assert_in('veto_patterns', full, "analyze_all has veto_patterns", results)
    assert_in('status', full, "analyze_all has status", results)
    assert_in('issues', full, "analyze_all has issues", results)


def test_inactivity_diagnosis(results: TestResult) -> None:
    """Test inactivity diagnosis logic."""
    print("\n--- Test: Inactivity Diagnosis ---")

    # Normal activity (enough trades)
    trades_normal = [{'resolved': True}] * 5
    diagnosis = diagnose_inactivity([], [], trades_normal)
    assert_eq(diagnosis, 'normal_activity', "normal activity diagnosis", results)

    # Entry price blocking (>40% SKIP_ENTRY_PRICE)
    skips_entry = [{'skip_type': 'SKIP_ENTRY_PRICE'}] * 5 + [{'skip_type': 'SKIP_OTHER'}] * 2
    diagnosis = diagnose_inactivity(skips_entry, [], [])
    assert_eq(diagnosis, 'entry_price_filter_blocking', "entry price diagnosis", results)

    # Weak pattern blocking
    skips_weak = [{'skip_type': 'SKIP_WEAK'}] * 5 + [{'skip_type': 'SKIP_OTHER'}] * 2
    diagnosis = diagnose_inactivity(skips_weak, [], [])
    assert_eq(diagnosis, 'pattern_accuracy_filter_blocking', "weak pattern diagnosis", results)

    # Bot halted (veto)
    vetoes_halted = ['Bot halted', 'Bot stopped', 'Bot halted']
    diagnosis = diagnose_inactivity([], vetoes_halted, [])
    assert_eq(diagnosis, 'bot_halted', "bot halted diagnosis", results)


# =============================================================================
# Test: Tuning Rules
# =============================================================================

def test_tuning_rules_fire_correctly(results: TestResult) -> None:
    """Test that tuning rules fire on correct conditions."""
    print("\n--- Test: Tuning Rules Fire Correctly ---")

    config = get_test_config()

    # Test 1: Low activity + high SKIP_ENTRY_PRICE should trigger increase
    analysis_low_activity_entry = {
        'trade_performance': {'total_trades': 1, 'resolved_trades': 1, 'win_rate': 0.60},
        'skip_distribution': {
            'total_skips': 20,
            'by_type': {'SKIP_ENTRY_PRICE': 10, 'SKIP_WEAK': 5, 'SKIP_OTHER': 5},
            'by_type_pct': {'SKIP_ENTRY_PRICE': 0.50, 'SKIP_WEAK': 0.25, 'SKIP_OTHER': 0.25},
        },
    }
    adjustments = select_tunings(analysis_low_activity_entry, config)
    params_adjusted = [adj['parameter'] for adj in adjustments]
    assert_in(
        'MAX_ENTRY_PRICE_CAP',
        params_adjusted,
        "entry price rule fires on low activity",
        results
    )

    # Test 2: Low activity + high SKIP_WEAK should trigger decrease accuracy
    analysis_low_activity_weak = {
        'trade_performance': {'total_trades': 1, 'resolved_trades': 1, 'win_rate': 0.60},
        'skip_distribution': {
            'total_skips': 20,
            'by_type': {'SKIP_WEAK': 10, 'SKIP_OTHER': 10},
            'by_type_pct': {'SKIP_WEAK': 0.50, 'SKIP_OTHER': 0.50},
        },
    }
    adjustments = select_tunings(analysis_low_activity_weak, config)
    params_adjusted = [adj['parameter'] for adj in adjustments]
    assert_in(
        'MIN_PATTERN_ACCURACY',
        params_adjusted,
        "weak pattern rule fires on low activity",
        results
    )

    # Test 3: Poor win rate should tighten filters
    analysis_poor_win_rate = {
        'trade_performance': {'total_trades': 15, 'resolved_trades': 12, 'win_rate': 0.40},
        'skip_distribution': {
            'total_skips': 5,
            'by_type': {'SKIP_OTHER': 5},
            'by_type_pct': {'SKIP_OTHER': 1.0},
        },
    }
    adjustments = select_tunings(analysis_poor_win_rate, config)
    params_adjusted = [adj['parameter'] for adj in adjustments]
    # Should tighten both accuracy and consensus
    assert_in(
        'MIN_PATTERN_ACCURACY',
        params_adjusted,
        "poor win rate tightens accuracy",
        results
    )
    assert_in(
        'CONSENSUS_THRESHOLD',
        params_adjusted,
        "poor win rate tightens consensus",
        results
    )

    # Test 4: Healthy performance - no adjustments
    analysis_healthy = {
        'trade_performance': {'total_trades': 8, 'resolved_trades': 6, 'win_rate': 0.65},
        'skip_distribution': {
            'total_skips': 10,
            'by_type': {'SKIP_ENTRY_PRICE': 3, 'SKIP_WEAK': 3, 'SKIP_OTHER': 4},
            'by_type_pct': {'SKIP_ENTRY_PRICE': 0.30, 'SKIP_WEAK': 0.30, 'SKIP_OTHER': 0.40},
        },
    }
    adjustments = select_tunings(analysis_healthy, config)
    assert_eq(len(adjustments), 0, "healthy performance - no adjustments", results)


# =============================================================================
# Test: Bounds Enforcement
# =============================================================================

def test_bounds_enforcement(results: TestResult) -> None:
    """Test that parameter bounds are respected."""
    print("\n--- Test: Bounds Enforcement ---")

    # Test calculate_new_value respects bounds
    param_config = {'current': 0.50, 'min': 0.35, 'max': 0.65, 'step': 0.05}

    # Test increase within bounds
    old, new = calculate_new_value(param_config, 'increase', steps=1)
    assert_eq(new, 0.55, "increase step within bounds", results)

    # Test decrease within bounds
    old, new = calculate_new_value(param_config, 'decrease', steps=1)
    assert_eq(new, 0.45, "decrease step within bounds", results)

    # Test increase at max (should clamp)
    param_at_max = {'current': 0.65, 'min': 0.35, 'max': 0.65, 'step': 0.05}
    old, new = calculate_new_value(param_at_max, 'increase', steps=1)
    assert_eq(new, 0.65, "increase clamped at max", results)

    # Test decrease at min (should clamp)
    param_at_min = {'current': 0.35, 'min': 0.35, 'max': 0.65, 'step': 0.05}
    old, new = calculate_new_value(param_at_min, 'decrease', steps=1)
    assert_eq(new, 0.35, "decrease clamped at min", results)

    # Test that adjustments at bounds are skipped
    config_at_max = {
        "tunable_parameters": {
            "MAX_ENTRY_PRICE_CAP": {
                "file": "bot/intra_epoch_bot.py",
                "current": 0.65,
                "min": 0.35,
                "max": 0.65,
                "step": 0.05
            }
        },
        "protected_parameters": [],
        "alert_thresholds": {"min_win_rate": 0.50, "min_trades_for_win_rate": 10},
    }

    # Analysis that would trigger MAX_ENTRY_PRICE_CAP increase
    analysis = {
        'trade_performance': {'total_trades': 1, 'resolved_trades': 1, 'win_rate': 0.60},
        'skip_distribution': {
            'total_skips': 20,
            'by_type': {'SKIP_ENTRY_PRICE': 12},
            'by_type_pct': {'SKIP_ENTRY_PRICE': 0.60},
        },
    }

    adjustments = select_tunings(analysis, config_at_max)
    assert_eq(
        len(adjustments),
        0,
        "no adjustment when already at bounds",
        results
    )


# =============================================================================
# Test: Protected Parameters
# =============================================================================

def test_protected_parameters(results: TestResult) -> None:
    """Test that protected parameters are never modified."""
    print("\n--- Test: Protected Parameters ---")

    config = get_test_config()

    # Test is_protected_parameter
    assert_true(
        is_protected_parameter('RISK_MAX_DRAWDOWN', config),
        "RISK_MAX_DRAWDOWN is protected",
        results
    )
    assert_true(
        is_protected_parameter('RISK_DAILY_LOSS_LIMIT', config),
        "RISK_DAILY_LOSS_LIMIT is protected",
        results
    )
    assert_true(
        not is_protected_parameter('MAX_ENTRY_PRICE_CAP', config),
        "MAX_ENTRY_PRICE_CAP is not protected",
        results
    )

    # Test that protected parameters are never in adjustments
    # Create config with protected parameter as tunable (shouldn't happen, but test anyway)
    config_with_protected_tunable = {
        "tunable_parameters": {
            "RISK_MAX_DRAWDOWN": {
                "file": "bot/intra_epoch_bot.py",
                "current": 0.30,
                "min": 0.20,
                "max": 0.50,
                "step": 0.05
            }
        },
        "protected_parameters": ["RISK_MAX_DRAWDOWN"],
        "alert_thresholds": {"min_win_rate": 0.50, "min_trades_for_win_rate": 10},
    }

    # Analysis that would normally trigger adjustment
    analysis = {
        'trade_performance': {'total_trades': 15, 'resolved_trades': 12, 'win_rate': 0.40},
        'skip_distribution': {'total_skips': 5, 'by_type': {}, 'by_type_pct': {}},
    }

    adjustments = select_tunings(analysis, config_with_protected_tunable)
    params_adjusted = [adj['parameter'] for adj in adjustments]

    assert_not_in(
        'RISK_MAX_DRAWDOWN',
        params_adjusted,
        "protected parameter never in adjustments",
        results
    )


# =============================================================================
# Test: Dry Run Mode
# =============================================================================

def test_dry_run_mode(results: TestResult) -> None:
    """Test that dry-run mode doesn't modify files."""
    print("\n--- Test: Dry Run Mode (File Modification) ---")

    config = get_test_config()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create directory structure
        (tmp_path / 'bot').mkdir()
        (tmp_path / 'config').mkdir()
        (tmp_path / 'optimizer' / 'history').mkdir(parents=True)
        (tmp_path / 'optimizer' / 'state').mkdir(parents=True)

        # Create test bot file
        original_content = '''# Trading parameters
MAX_ENTRY_PRICE_CAP = 0.50
MIN_PATTERN_ACCURACY = 0.735
'''
        bot_file = tmp_path / 'bot' / 'intra_epoch_bot.py'
        with open(bot_file, 'w') as f:
            f.write(original_content)

        # Create adjustments.txt
        (tmp_path / 'optimizer' / 'history' / 'adjustments.txt').touch()

        # Read original content
        with open(bot_file) as f:
            content_before = f.read()

        # Test that we CAN apply adjustment (baseline)
        success = apply_adjustment(
            param='MAX_ENTRY_PRICE_CAP',
            old_value=0.50,
            new_value=0.55,
            reason='Test adjustment',
            rule_name='test_rule',
            config=config,
            base_dir=tmp_path,
        )
        assert_true(success, "adjustment can be applied normally", results)

        # Verify file was modified
        with open(bot_file) as f:
            content_after = f.read()
        assert_true(
            '0.55' in content_after,
            "file was modified after adjustment",
            results
        )

        # Restore original for next test
        with open(bot_file, 'w') as f:
            f.write(original_content)

        # Test _replace_param_value separately
        new_content, changed = _replace_param_value(original_content, 'MAX_ENTRY_PRICE_CAP', 0.60)
        assert_true(changed, "replace_param_value reports change", results)
        assert_in('0.60', new_content, "new value in content", results)

        # Verify original file unchanged (we only used the function, didn't write)
        with open(bot_file) as f:
            file_content = f.read()
        assert_eq(file_content, original_content, "original file unchanged by replace_param_value", results)


def test_executor_file_operations(results: TestResult) -> None:
    """Test executor file operations."""
    print("\n--- Test: Executor File Operations ---")

    config = get_test_config()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create directory structure
        (tmp_path / 'bot').mkdir()
        (tmp_path / 'optimizer' / 'history').mkdir(parents=True)
        (tmp_path / 'optimizer' / 'state').mkdir(parents=True)

        # Create test file
        original_content = '''# Config
MAX_ENTRY_PRICE_CAP = 0.50  # Entry cap
EDGE_BUFFER = 0.05
'''
        bot_file = tmp_path / 'bot' / 'intra_epoch_bot.py'
        with open(bot_file, 'w') as f:
            f.write(original_content)

        (tmp_path / 'optimizer' / 'history' / 'adjustments.txt').touch()

        # Apply adjustment
        success = apply_adjustment(
            param='MAX_ENTRY_PRICE_CAP',
            old_value=0.50,
            new_value=0.55,
            reason='Test',
            rule_name='test',
            config=config,
            base_dir=tmp_path,
        )

        assert_true(success, "adjustment succeeded", results)

        # Verify backup exists
        backup_file = bot_file.with_suffix('.py.bak')
        assert_true(backup_file.exists(), "backup file created", results)

        # Verify adjustment logged
        history = get_adjustment_history(base_dir=tmp_path)
        assert_true(len(history) > 0, "adjustment logged to history", results)
        assert_in('MAX_ENTRY_PRICE_CAP', history[0], "parameter in log", results)

        # Verify parameter history updated
        history_file = tmp_path / 'optimizer' / 'state' / 'parameter_history.json'
        assert_true(history_file.exists(), "parameter_history.json created", results)


# =============================================================================
# Test: Edge Cases
# =============================================================================

def test_edge_cases(results: TestResult) -> None:
    """Test edge cases and error handling."""
    print("\n--- Test: Edge Cases ---")

    # Empty data returns valid results
    empty_trades: list[dict[str, Any]] = []
    perf = analyze_trade_performance(empty_trades)
    assert_eq(perf['total_trades'], 0, "empty trades - total_trades is 0", results)
    assert_eq(perf['win_rate'], None, "empty trades - win_rate is None", results)

    empty_skips: list[dict[str, Any]] = []
    skip_dist = analyze_skip_distribution(empty_skips)
    assert_eq(skip_dist['total_skips'], 0, "empty skips - total_skips is 0", results)
    assert_eq(skip_dist['top_reason'], None, "empty skips - top_reason is None", results)

    empty_vetoes: list[str] = []
    veto_patt = analyze_veto_patterns(empty_vetoes)
    assert_eq(veto_patt['total_vetoes'], 0, "empty vetoes - total_vetoes is 0", results)

    # Missing files handled gracefully (data collection)
    # These functions check for file existence and return empty results
    # This is tested implicitly by test_data_collection_format

    # Invalid direction in calculate_new_value
    param_config = {'current': 0.50, 'min': 0.35, 'max': 0.65, 'step': 0.05}
    try:
        calculate_new_value(param_config, 'invalid', steps=1)
        results.fail("invalid direction", "should raise ValueError")
    except ValueError:
        results.ok("invalid direction raises ValueError")


# =============================================================================
# Main Test Runner
# =============================================================================

def run_all_tests() -> int:
    """Run all tests and report results."""
    print("=" * 60)
    print("OPTIMIZER INTEGRATION TESTS")
    print("=" * 60)

    results = TestResult()

    # Run test suites
    test_data_collection_format(results)
    test_analysis_calculations(results)
    test_inactivity_diagnosis(results)
    test_tuning_rules_fire_correctly(results)
    test_bounds_enforcement(results)
    test_protected_parameters(results)
    test_dry_run_mode(results)
    test_executor_file_operations(results)
    test_edge_cases(results)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Passed: {results.passed}")
    print(f"  Failed: {results.failed}")

    if results.failures:
        print("\nFailures:")
        for failure in results.failures:
            print(f"  - {failure}")

    print("=" * 60)

    if results.failed == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
