"""
Tuning Rules Engine for Optimizer

Defines rules that map analysis findings to parameter adjustments.
Rules are evaluated in priority order and respect bounds from config.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class TuningRule:
    """
    A rule that maps an analysis condition to a parameter adjustment.

    Attributes:
        name: Unique rule identifier
        condition_fn: Function that takes (analysis, config) -> bool
        parameter: Parameter name to adjust (must be in tunable_parameters)
        direction: 'increase' or 'decrease'
        step: Number of steps to adjust (uses step from config)
        description: Human-readable description of what the rule does
    """
    name: str
    condition_fn: Callable[[dict[str, Any], dict[str, Any]], bool]
    parameter: str
    direction: str  # 'increase' or 'decrease'
    step: int = 1  # Number of config steps to adjust
    description: str = ""


def _get_skip_pct(analysis: dict[str, Any], skip_type: str) -> float:
    """Get percentage of skips for a given skip type."""
    skip_dist = analysis.get('skip_distribution', {})
    by_type_pct = skip_dist.get('by_type_pct', {})
    return by_type_pct.get(skip_type, 0.0)


def _get_win_rate(analysis: dict[str, Any]) -> float | None:
    """Get win rate from analysis, or None if not enough trades."""
    trade_perf = analysis.get('trade_performance', {})
    return trade_perf.get('win_rate')


def _get_resolved_trades(analysis: dict[str, Any]) -> int:
    """Get number of resolved trades."""
    trade_perf = analysis.get('trade_performance', {})
    return trade_perf.get('resolved_trades', 0)


def _get_total_trades(analysis: dict[str, Any]) -> int:
    """Get total number of trades."""
    trade_perf = analysis.get('trade_performance', {})
    return trade_perf.get('total_trades', 0)


def _get_total_skips(analysis: dict[str, Any]) -> int:
    """Get total number of skips."""
    skip_dist = analysis.get('skip_distribution', {})
    return skip_dist.get('total_skips', 0)


# ==============================================================================
# Rule Condition Functions
# ==============================================================================

def condition_too_few_trades_entry_price(analysis: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    True if >40% of skips are due to SKIP_ENTRY_PRICE and we have low trade activity.
    This suggests MAX_ENTRY_PRICE_CAP is too restrictive.
    """
    # Only trigger if we have low activity (< 3 trades) and some skips
    if _get_total_trades(analysis) >= 3:
        return False

    total_skips = _get_total_skips(analysis)
    if total_skips < 5:  # Need meaningful sample
        return False

    return _get_skip_pct(analysis, 'SKIP_ENTRY_PRICE') > 0.40


def condition_too_few_trades_weak_pattern(analysis: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    True if >40% of skips are due to SKIP_WEAK (pattern accuracy) and we have low activity.
    This suggests MIN_PATTERN_ACCURACY is too restrictive.
    """
    if _get_total_trades(analysis) >= 3:
        return False

    total_skips = _get_total_skips(analysis)
    if total_skips < 5:
        return False

    return _get_skip_pct(analysis, 'SKIP_WEAK') > 0.40


def condition_too_few_trades_consensus(analysis: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    True if >40% of skips are due to SKIP_CONSENSUS and we have low activity.
    This suggests CONSENSUS_THRESHOLD is too restrictive.
    """
    if _get_total_trades(analysis) >= 3:
        return False

    total_skips = _get_total_skips(analysis)
    if total_skips < 5:
        return False

    return _get_skip_pct(analysis, 'SKIP_CONSENSUS') > 0.40


def condition_too_few_trades_confidence(analysis: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    True if >40% of skips are due to SKIP_CONFIDENCE and we have low activity.
    This suggests MIN_CONFIDENCE is too restrictive.
    """
    if _get_total_trades(analysis) >= 3:
        return False

    total_skips = _get_total_skips(analysis)
    if total_skips < 5:
        return False

    return _get_skip_pct(analysis, 'SKIP_CONFIDENCE') > 0.40


def condition_poor_win_rate(analysis: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    True if win rate is below 50% with enough resolved trades.
    This suggests we need tighter filters (more selective trading).
    """
    min_trades = config.get('alert_thresholds', {}).get('min_trades_for_win_rate', 10)
    min_win_rate = config.get('alert_thresholds', {}).get('min_win_rate', 0.50)

    resolved = _get_resolved_trades(analysis)
    if resolved < min_trades:
        return False

    win_rate = _get_win_rate(analysis)
    if win_rate is None:
        return False

    return win_rate < min_win_rate


# ==============================================================================
# Rule Definitions
# ==============================================================================

TUNING_RULES: list[TuningRule] = [
    # Rules for too few trades (loosen filters)
    TuningRule(
        name='too_few_trades_entry_price',
        condition_fn=condition_too_few_trades_entry_price,
        parameter='MAX_ENTRY_PRICE_CAP',
        direction='increase',
        step=1,
        description='Increase MAX_ENTRY_PRICE_CAP because >40% skips are due to entry price filter',
    ),
    TuningRule(
        name='too_few_trades_weak_pattern',
        condition_fn=condition_too_few_trades_weak_pattern,
        parameter='MIN_PATTERN_ACCURACY',
        direction='decrease',
        step=1,
        description='Decrease MIN_PATTERN_ACCURACY because >40% skips are due to weak pattern filter',
    ),
    TuningRule(
        name='too_few_trades_consensus',
        condition_fn=condition_too_few_trades_consensus,
        parameter='CONSENSUS_THRESHOLD',
        direction='decrease',
        step=1,
        description='Decrease CONSENSUS_THRESHOLD because >40% skips are due to consensus filter',
    ),
    TuningRule(
        name='too_few_trades_confidence',
        condition_fn=condition_too_few_trades_confidence,
        parameter='MIN_CONFIDENCE',
        direction='decrease',
        step=1,
        description='Decrease MIN_CONFIDENCE because >40% skips are due to confidence filter',
    ),

    # Rules for poor performance (tighten filters)
    TuningRule(
        name='poor_win_rate_tighten_accuracy',
        condition_fn=condition_poor_win_rate,
        parameter='MIN_PATTERN_ACCURACY',
        direction='increase',
        step=1,
        description='Increase MIN_PATTERN_ACCURACY because win rate is below 50%',
    ),
    TuningRule(
        name='poor_win_rate_tighten_consensus',
        condition_fn=condition_poor_win_rate,
        parameter='CONSENSUS_THRESHOLD',
        direction='increase',
        step=1,
        description='Increase CONSENSUS_THRESHOLD because win rate is below 50%',
    ),
]


def calculate_new_value(
    param_config: dict[str, Any],
    direction: str,
    steps: int = 1
) -> tuple[float, float]:
    """
    Calculate the new value for a parameter given direction and steps.

    Args:
        param_config: Parameter config with 'current', 'min', 'max', 'step'
        direction: 'increase' or 'decrease'
        steps: Number of steps to adjust

    Returns:
        Tuple of (old_value, new_value), clamped to bounds
    """
    current = param_config['current']
    step_size = param_config['step']
    min_val = param_config['min']
    max_val = param_config['max']

    if direction == 'increase':
        new_value = current + (step_size * steps)
    elif direction == 'decrease':
        new_value = current - (step_size * steps)
    else:
        raise ValueError(f"Invalid direction: {direction}")

    # Clamp to bounds
    new_value = max(min_val, min(max_val, new_value))

    # Round to avoid floating point issues
    new_value = round(new_value, 4)

    return (current, new_value)


def select_tunings(
    analysis: dict[str, Any],
    config: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Evaluate all tuning rules and return list of adjustments to make.

    Args:
        analysis: Analysis dict from analyzer.analyze_all()
        config: Config dict loaded from optimizer_config.json

    Returns:
        List of adjustment dicts, each with:
        - parameter: Parameter name
        - old_value: Current value
        - new_value: Proposed new value
        - reason: Human-readable reason for adjustment
        - rule_name: Name of the rule that triggered this

    Rules:
        - Only tunable parameters are adjusted (never protected)
        - Bounds are strictly enforced
        - If old_value == new_value (at bounds), adjustment is skipped
        - Rules are evaluated in order; multiple rules can apply to same parameter
          (last one wins, but in practice we dedupe by parameter)
    """
    tunable = config.get('tunable_parameters', {})
    protected = config.get('protected_parameters', [])

    # Track adjustments by parameter (only one adjustment per parameter)
    adjustments_by_param: dict[str, dict[str, Any]] = {}

    for rule in TUNING_RULES:
        # Skip if parameter is protected
        if rule.parameter in protected:
            continue

        # Skip if parameter not in tunable config
        if rule.parameter not in tunable:
            continue

        # Check if rule condition is met
        try:
            if not rule.condition_fn(analysis, config):
                continue
        except Exception:
            # Silently skip rules that error
            continue

        # Calculate new value
        param_config = tunable[rule.parameter]
        old_value, new_value = calculate_new_value(
            param_config,
            rule.direction,
            rule.step
        )

        # Skip if no change (already at bounds)
        if old_value == new_value:
            continue

        # Store adjustment (overwrites if same parameter adjusted by multiple rules)
        adjustments_by_param[rule.parameter] = {
            'parameter': rule.parameter,
            'old_value': old_value,
            'new_value': new_value,
            'reason': rule.description,
            'rule_name': rule.name,
            'file': param_config.get('file', 'unknown'),
        }

    return list(adjustments_by_param.values())


def is_protected_parameter(param: str, config: dict[str, Any]) -> bool:
    """Check if a parameter is protected from auto-adjustment."""
    protected = config.get('protected_parameters', [])
    return param in protected


def get_available_rules() -> list[dict[str, Any]]:
    """Get list of all available tuning rules with metadata."""
    return [
        {
            'name': rule.name,
            'parameter': rule.parameter,
            'direction': rule.direction,
            'description': rule.description,
        }
        for rule in TUNING_RULES
    ]


if __name__ == '__main__':
    # Test the tuning rules with sample data
    import json
    print("Testing tuning_rules.py...")

    # Load config
    config_path = 'optimizer/optimizer_config.json'
    try:
        with open(config_path) as f:
            config = json.load(f)
        print(f"Loaded config from {config_path}")
    except FileNotFoundError:
        print(f"Config not found at {config_path}, using test config")
        config = {
            'alert_thresholds': {
                'min_win_rate': 0.50,
                'min_trades_for_win_rate': 10,
            },
            'tunable_parameters': {
                'MAX_ENTRY_PRICE_CAP': {'current': 0.50, 'min': 0.35, 'max': 0.65, 'step': 0.05},
                'MIN_PATTERN_ACCURACY': {'current': 0.735, 'min': 0.65, 'max': 0.80, 'step': 0.01},
                'CONSENSUS_THRESHOLD': {'current': 0.40, 'min': 0.30, 'max': 0.55, 'step': 0.05},
                'MIN_CONFIDENCE': {'current': 0.50, 'min': 0.35, 'max': 0.65, 'step': 0.05},
            },
            'protected_parameters': ['RISK_MAX_DRAWDOWN'],
        }

    # Test case 1: Low activity due to entry price filtering
    print("\n--- Test 1: Low activity, >40% SKIP_ENTRY_PRICE ---")
    analysis1 = {
        'trade_performance': {'total_trades': 1, 'resolved_trades': 1, 'win_rate': 0.60},
        'skip_distribution': {
            'total_skips': 20,
            'by_type': {'SKIP_ENTRY_PRICE': 10, 'SKIP_WEAK': 5, 'SKIP_OTHER': 5},
            'by_type_pct': {'SKIP_ENTRY_PRICE': 0.50, 'SKIP_WEAK': 0.25, 'SKIP_OTHER': 0.25},
        },
    }
    adjustments1 = select_tunings(analysis1, config)
    print(f"Adjustments: {len(adjustments1)}")
    for adj in adjustments1:
        print(f"  {adj['parameter']}: {adj['old_value']} -> {adj['new_value']}")
        print(f"    Reason: {adj['reason']}")

    # Test case 2: Poor win rate
    print("\n--- Test 2: Poor win rate (<50%) ---")
    analysis2 = {
        'trade_performance': {'total_trades': 15, 'resolved_trades': 12, 'win_rate': 0.40},
        'skip_distribution': {
            'total_skips': 5,
            'by_type': {'SKIP_OTHER': 5},
            'by_type_pct': {'SKIP_OTHER': 1.0},
        },
    }
    adjustments2 = select_tunings(analysis2, config)
    print(f"Adjustments: {len(adjustments2)}")
    for adj in adjustments2:
        print(f"  {adj['parameter']}: {adj['old_value']} -> {adj['new_value']}")
        print(f"    Reason: {adj['reason']}")

    # Test case 3: Healthy - no adjustments needed
    print("\n--- Test 3: Healthy performance ---")
    analysis3 = {
        'trade_performance': {'total_trades': 8, 'resolved_trades': 6, 'win_rate': 0.65},
        'skip_distribution': {
            'total_skips': 10,
            'by_type': {'SKIP_ENTRY_PRICE': 3, 'SKIP_WEAK': 3, 'SKIP_OTHER': 4},
            'by_type_pct': {'SKIP_ENTRY_PRICE': 0.30, 'SKIP_WEAK': 0.30, 'SKIP_OTHER': 0.40},
        },
    }
    adjustments3 = select_tunings(analysis3, config)
    print(f"Adjustments: {len(adjustments3)}")
    if not adjustments3:
        print("  (No adjustments needed - healthy performance)")

    # Test case 4: Bounds checking
    print("\n--- Test 4: Bounds checking ---")
    config_at_bounds = {
        'alert_thresholds': {'min_win_rate': 0.50, 'min_trades_for_win_rate': 10},
        'tunable_parameters': {
            'MAX_ENTRY_PRICE_CAP': {'current': 0.65, 'min': 0.35, 'max': 0.65, 'step': 0.05},
        },
        'protected_parameters': [],
    }
    # This should NOT create adjustment because already at max
    adjustments4 = select_tunings(analysis1, config_at_bounds)
    print(f"Adjustments (at max bound): {len(adjustments4)}")
    if not adjustments4:
        print("  (No adjustment - already at max bound)")

    # Test protected parameters
    print("\n--- Test 5: Protected parameter check ---")
    print(f"Is RISK_MAX_DRAWDOWN protected? {is_protected_parameter('RISK_MAX_DRAWDOWN', config)}")
    print(f"Is MAX_ENTRY_PRICE_CAP protected? {is_protected_parameter('MAX_ENTRY_PRICE_CAP', config)}")

    # List all rules
    print("\n--- Available Rules ---")
    for rule_info in get_available_rules():
        print(f"  {rule_info['name']}: {rule_info['parameter']} ({rule_info['direction']})")

    print("\n✅ All tests completed!")
