"""
Analysis Engine for Optimizer

Analyzes collected data to identify issues and optimization opportunities.
"""

from typing import Any


def analyze_trade_performance(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze trade performance metrics.

    Args:
        trades: List of trade dicts from data_collector.collect_trades()

    Returns:
        Dict with:
        - total_trades: Total number of trades
        - resolved_trades: Number of trades with known outcomes
        - wins: Number of winning trades
        - losses: Number of losing trades
        - win_rate: Win percentage (0.0-1.0) or None if no resolved trades
        - total_pnl: Sum of P&L from resolved trades
        - avg_pnl: Average P&L per resolved trade
        - avg_entry_price: Average entry price
        - avg_confidence: Average confidence score
    """
    resolved = [t for t in trades if t.get('resolved')]
    wins = sum(1 for t in resolved if t.get('won'))
    losses = len(resolved) - wins

    total_pnl = sum(t.get('pnl', 0) or 0 for t in resolved)
    avg_pnl = total_pnl / len(resolved) if resolved else 0.0

    entry_prices = [t.get('entry_price', 0) or 0 for t in trades if t.get('entry_price')]
    avg_entry = sum(entry_prices) / len(entry_prices) if entry_prices else 0.0

    confidences = [t.get('confidence', 0) or 0 for t in trades if t.get('confidence')]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        'total_trades': len(trades),
        'resolved_trades': len(resolved),
        'wins': wins,
        'losses': losses,
        'win_rate': wins / len(resolved) if resolved else None,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'avg_entry_price': avg_entry,
        'avg_confidence': avg_conf,
    }


def analyze_skip_distribution(skips: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze skip decision distribution by reason type.

    Args:
        skips: List of skip dicts from data_collector.collect_skips()

    Returns:
        Dict with:
        - total_skips: Total number of skips
        - by_type: Dict mapping skip_type to count
        - by_type_pct: Dict mapping skip_type to percentage (0.0-1.0)
        - top_reason: Most common skip type (or None if no skips)
        - top_reason_pct: Percentage of top reason (0.0-1.0)
    """
    total = len(skips)

    if total == 0:
        return {
            'total_skips': 0,
            'by_type': {},
            'by_type_pct': {},
            'top_reason': None,
            'top_reason_pct': 0.0,
        }

    # Count by skip type
    by_type: dict[str, int] = {}
    for skip in skips:
        skip_type = skip.get('skip_type', 'SKIP_OTHER')
        by_type[skip_type] = by_type.get(skip_type, 0) + 1

    # Calculate percentages
    by_type_pct = {k: v / total for k, v in by_type.items()}

    # Find top reason
    top_reason = max(by_type, key=lambda k: by_type[k]) if by_type else None
    top_reason_pct = by_type_pct.get(top_reason, 0.0) if top_reason else 0.0

    return {
        'total_skips': total,
        'by_type': by_type,
        'by_type_pct': by_type_pct,
        'top_reason': top_reason,
        'top_reason_pct': top_reason_pct,
    }


def analyze_veto_patterns(vetoes: list[str]) -> dict[str, Any]:
    """
    Analyze veto patterns from log entries.

    Args:
        vetoes: List of veto reason strings from data_collector.collect_vetoes()

    Returns:
        Dict with:
        - total_vetoes: Total number of vetoes
        - by_reason: Dict mapping veto reason (normalized) to count
        - by_reason_pct: Dict mapping veto reason to percentage
        - top_reason: Most common veto reason (or None if no vetoes)
        - top_reason_pct: Percentage of top reason
    """
    total = len(vetoes)

    if total == 0:
        return {
            'total_vetoes': 0,
            'by_reason': {},
            'by_reason_pct': {},
            'top_reason': None,
            'top_reason_pct': 0.0,
        }

    # Normalize and count veto reasons
    by_reason: dict[str, int] = {}
    for veto in vetoes:
        # Normalize: lowercase, strip whitespace, truncate to first 50 chars
        normalized = veto.lower().strip()[:50] if veto else 'unknown'
        # Group similar reasons
        normalized = _normalize_veto_reason(normalized)
        by_reason[normalized] = by_reason.get(normalized, 0) + 1

    # Calculate percentages
    by_reason_pct = {k: v / total for k, v in by_reason.items()}

    # Find top reason
    top_reason = max(by_reason, key=lambda k: by_reason[k]) if by_reason else None
    top_reason_pct = by_reason_pct.get(top_reason, 0.0) if top_reason else 0.0

    return {
        'total_vetoes': total,
        'by_reason': by_reason,
        'by_reason_pct': by_reason_pct,
        'top_reason': top_reason,
        'top_reason_pct': top_reason_pct,
    }


def _normalize_veto_reason(reason: str) -> str:
    """
    Normalize veto reason strings for grouping.

    Groups similar reasons together for easier analysis.
    """
    reason = reason.lower()

    if 'position' in reason:
        return 'existing_position'
    elif 'drawdown' in reason:
        return 'drawdown_limit'
    elif 'balance' in reason or 'insufficient' in reason:
        return 'balance_issue'
    elif 'halted' in reason or 'stopped' in reason:
        return 'bot_halted'
    elif 'cooldown' in reason:
        return 'trade_cooldown'
    elif 'correlation' in reason:
        return 'correlation_limit'
    elif 'daily' in reason and 'loss' in reason:
        return 'daily_loss_limit'
    else:
        return reason[:30] if reason else 'unknown'


def diagnose_inactivity(
    skips: list[dict[str, Any]],
    vetoes: list[str],
    trades: list[dict[str, Any]] | None = None
) -> str:
    """
    Diagnose the primary cause of trading inactivity.

    Args:
        skips: List of skip decisions
        vetoes: List of veto reasons
        trades: Optional list of trades for context

    Returns:
        String diagnosis explaining the primary cause of inactivity.
        Returns 'normal_activity' if there are enough trades.
    """
    # If we have trades, check if activity is actually low
    if trades and len(trades) >= 5:
        return 'normal_activity'

    total_skips = len(skips)
    total_vetoes = len(vetoes)
    total_signals = total_skips + total_vetoes

    # No signals at all - might be a bigger issue
    if total_signals == 0:
        return 'no_signals_detected'

    # Analyze skip distribution
    skip_analysis = analyze_skip_distribution(skips)
    veto_analysis = analyze_veto_patterns(vetoes)

    # Determine primary cause based on skip types
    skip_pcts = skip_analysis.get('by_type_pct', {})
    veto_pcts = veto_analysis.get('by_reason_pct', {})

    # Check vetoes first (higher priority - risk/safety issues)
    if total_vetoes > 0:
        if veto_pcts.get('bot_halted', 0) > 0.1:
            return 'bot_halted'
        if veto_pcts.get('existing_position', 0) > 0.3:
            return 'position_blocking'
        if veto_pcts.get('drawdown_limit', 0) > 0.1:
            return 'drawdown_protection_active'
        if veto_pcts.get('balance_issue', 0) > 0.1:
            return 'insufficient_balance'
        if veto_pcts.get('daily_loss_limit', 0) > 0.1:
            return 'daily_loss_limit_reached'

    # Check skip reasons (filter/threshold issues)
    if total_skips > 0:
        if skip_pcts.get('SKIP_ENTRY_PRICE', 0) > 0.4:
            return 'entry_price_filter_blocking'
        if skip_pcts.get('SKIP_WEAK', 0) > 0.4:
            return 'pattern_accuracy_filter_blocking'
        if skip_pcts.get('SKIP_CONSENSUS', 0) > 0.4:
            return 'consensus_threshold_blocking'
        if skip_pcts.get('SKIP_CONFIDENCE', 0) > 0.4:
            return 'confidence_filter_blocking'
        if skip_pcts.get('SKIP_CONFLUENCE', 0) > 0.4:
            return 'confluence_mismatch'

    # Mixed reasons - no single dominant cause
    if total_skips > total_vetoes:
        return 'multiple_filter_issues'
    elif total_vetoes > total_skips:
        return 'risk_management_blocking'
    else:
        return 'unknown_cause'


def analyze_all(
    trades: list[dict[str, Any]],
    skips: list[dict[str, Any]],
    vetoes: list[str],
    hours: int = 2
) -> dict[str, Any]:
    """
    Run all analysis and return combined results.

    Args:
        trades: List of trades from data_collector
        skips: List of skips from data_collector
        vetoes: List of vetoes from data_collector
        hours: Lookback period (for reporting)

    Returns:
        Dict with all analysis results combined:
        - period_hours: Lookback period
        - trade_performance: Results from analyze_trade_performance
        - skip_distribution: Results from analyze_skip_distribution
        - veto_patterns: Results from analyze_veto_patterns
        - inactivity_diagnosis: Result from diagnose_inactivity
        - issues: List of identified issues
        - status: 'healthy', 'warning', or 'alert'
    """
    trade_perf = analyze_trade_performance(trades)
    skip_dist = analyze_skip_distribution(skips)
    veto_patt = analyze_veto_patterns(vetoes)
    diagnosis = diagnose_inactivity(skips, vetoes, trades)

    # Identify issues
    issues: list[str] = []
    status = 'healthy'

    # Check for inactivity
    if trade_perf['total_trades'] == 0:
        issues.append(f'no_trades_in_{hours}h')
        status = 'alert'
    elif trade_perf['total_trades'] < 3:
        issues.append('low_trade_activity')
        if status != 'alert':
            status = 'warning'

    # Check win rate (only if enough resolved trades)
    if trade_perf['resolved_trades'] >= 10:
        win_rate = trade_perf.get('win_rate')
        if win_rate is not None and win_rate < 0.50:
            issues.append('low_win_rate')
            status = 'alert'

    # Check skip rate
    total_signals = trade_perf['total_trades'] + skip_dist['total_skips']
    if total_signals > 0:
        skip_rate = skip_dist['total_skips'] / total_signals
        if skip_rate > 0.90:
            issues.append('high_skip_rate')
            if status != 'alert':
                status = 'warning'

    # Check for dominant skip reason
    if skip_dist['top_reason_pct'] > 0.50 and skip_dist['total_skips'] >= 10:
        issues.append(f'dominant_skip_reason:{skip_dist["top_reason"]}')

    return {
        'period_hours': hours,
        'trade_performance': trade_perf,
        'skip_distribution': skip_dist,
        'veto_patterns': veto_patt,
        'inactivity_diagnosis': diagnosis,
        'issues': issues,
        'status': status,
    }


if __name__ == '__main__':
    # Test the analyzer with sample data
    print("Testing analyzer with sample data...")

    # Sample trades
    sample_trades = [
        {'resolved': True, 'won': True, 'pnl': 5.50, 'entry_price': 0.35, 'confidence': 0.65},
        {'resolved': True, 'won': True, 'pnl': 4.20, 'entry_price': 0.40, 'confidence': 0.58},
        {'resolved': True, 'won': False, 'pnl': -8.00, 'entry_price': 0.55, 'confidence': 0.52},
        {'resolved': True, 'won': True, 'pnl': 6.00, 'entry_price': 0.30, 'confidence': 0.70},
        {'resolved': False, 'won': None, 'pnl': None, 'entry_price': 0.42, 'confidence': 0.60},
    ]

    # Sample skips
    sample_skips = [
        {'skip_type': 'SKIP_ENTRY_PRICE'},
        {'skip_type': 'SKIP_ENTRY_PRICE'},
        {'skip_type': 'SKIP_ENTRY_PRICE'},
        {'skip_type': 'SKIP_WEAK'},
        {'skip_type': 'SKIP_WEAK'},
        {'skip_type': 'SKIP_CONSENSUS'},
        {'skip_type': 'SKIP_OTHER'},
    ]

    # Sample vetoes
    sample_vetoes = [
        'Existing position for BTC',
        'Existing position for ETH',
        'Drawdown limit exceeded',
    ]

    print("\n--- Trade Performance Analysis ---")
    trade_result = analyze_trade_performance(sample_trades)
    for k, v in trade_result.items():
        print(f"  {k}: {v}")

    print("\n--- Skip Distribution Analysis ---")
    skip_result = analyze_skip_distribution(sample_skips)
    for k, v in skip_result.items():
        print(f"  {k}: {v}")

    print("\n--- Veto Patterns Analysis ---")
    veto_result = analyze_veto_patterns(sample_vetoes)
    for k, v in veto_result.items():
        print(f"  {k}: {v}")

    print("\n--- Inactivity Diagnosis ---")
    diagnosis = diagnose_inactivity(sample_skips, sample_vetoes, sample_trades)
    print(f"  Diagnosis: {diagnosis}")

    print("\n--- Full Analysis ---")
    full_result = analyze_all(sample_trades, sample_skips, sample_vetoes, hours=2)
    print(f"  Status: {full_result['status']}")
    print(f"  Issues: {full_result['issues']}")
    print(f"  Diagnosis: {full_result['inactivity_diagnosis']}")
