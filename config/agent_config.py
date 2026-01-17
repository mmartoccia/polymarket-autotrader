#!/usr/bin/env python3
"""
Agent System Configuration

Controls behavior of the multi-expert consensus trading system.
"""

# =============================================================================
# AGENT SYSTEM SETTINGS
# =============================================================================

# Master enable/disable switch
AGENT_SYSTEM_ENABLED = True  # Set True to enable agent decisions, False for log-only

# Consensus requirements (Jan 17, 2026 - LOWERED for data collection phase)
# Phase 1: Data Collection - Need 100+ trades to establish baseline
CONSENSUS_THRESHOLD = 0.55     # LOWERED from 0.82 → 55% majority agreement (data collection mode)
MIN_CONFIDENCE = 0.40          # LOWERED from 0.65 → 40% positive lean (data collection mode)
MIN_INDIVIDUAL_CONFIDENCE = 0.30  # Minimum per-agent confidence (enforced in vote_aggregator.py)
ADAPTIVE_WEIGHTS = True        # Enable performance-based weight tuning

# NOTE: After 100 trades, analyze win rate and adjust:
#   - If WR >60%: Lower to 0.50/0.35 (too conservative)
#   - If WR 55-60%: Raise to 0.60/0.45 (sweet spot)
#   - If WR <55%: Raise to 0.70/0.55 (too aggressive)

# Agent weights (base multipliers, will be adjusted by performance)
# US-RI-003 (Jan 16, 2026): Disabled underperforming agents (TechAgent, SentimentAgent, CandlestickAgent)
AGENT_WEIGHTS = {
    'TechAgent': 0.0,              # DISABLED (US-RI-003): 0% WR impact
    'SentimentAgent': 0.0,         # DISABLED (US-RI-003): 0% WR impact
    'RegimeAgent': 1.0,            # Market classification
    'CandlestickAgent': 0.0,       # DISABLED (US-RI-003): 0% WR impact
    'TimePatternAgent': 0.5,       # Historical hourly patterns (ENABLED for live trading)
    'OrderBookAgent': 0.8,         # Orderbook microstructure analysis (NEW - Phase 1)
    'FundingRateAgent': 0.8,       # Derivatives funding rate analysis (NEW - Phase 1)
    'OnChainAgent': 0.0,           # Blockchain whale tracking (NEW - Phase 1, disabled until API key)
    'SocialSentimentAgent': 0.0,   # Crowd psychology analysis (NEW - Phase 1, disabled until API keys)
    'RiskAgent': 1.0,              # Risk management (veto)
    'GamblerAgent': 1.0,           # Probability gating (veto - blocks trades <60% win prob)
}

# =============================================================================
# PER-AGENT ENABLE/DISABLE FLAGS
# =============================================================================

# Per-Agent Enable/Disable Flags
# Set to False to disable specific agents based on performance tracking
# Use analytics/agent_performance_tracker.py to identify underperformers
#
# US-RI-003 (Jan 16, 2026): Disabled underperforming agents per elimination_candidates.md
# - TechAgent: 0% WR impact (Score 7.0 - DISABLE)
# - SentimentAgent: 0% WR impact (Score 7.0 - DISABLE, also ENABLE_CONTRARIAN_TRADES=False)
# - CandlestickAgent: 0% WR impact (Score 5.0 - REVIEW low value)
# Kept: RegimeAgent (regime awareness), RiskAgent (essential), GamblerAgent (gating)
AGENT_ENABLED = {
    'TechAgent': False,  # DISABLED: 0% WR impact, 254 LOC burden (US-RI-003)
    'SentimentAgent': False,  # DISABLED: 0% WR impact, 238 LOC burden (US-RI-003)
    'RegimeAgent': True,  # KEPT: Regime-based weight adjustments
    'CandlestickAgent': False,  # DISABLED: 0% WR impact, 154 LOC burden (US-RI-003)
    'TimePatternAgent': True,  # KEPT: Shadow testing shows promise
    'OrderBookAgent': True,  # KEPT: Phase 1 testing
    'FundingRateAgent': True,  # KEPT: Phase 1 testing
    'OnChainAgent': False,  # Disabled: No API keys configured
    'SocialSentimentAgent': False,  # Disabled: No API keys configured
    'RiskAgent': True,  # ESSENTIAL: Position sizing and risk management
    'GamblerAgent': True,  # KEPT: Probability gating (60% threshold)
}

def get_enabled_agents():
    """Returns list of enabled agent names"""
    return [name for name, enabled in AGENT_ENABLED.items() if enabled]

# =============================================================================
# REGIME-SPECIFIC ADJUSTMENTS
# =============================================================================

# How much to adjust agent weights based on regime
REGIME_ADJUSTMENT_STRENGTH = 1.0  # 0.0 = no adjustment, 1.0 = full adjustment

# Override: If True, regime adjustments are applied
# If False, all agents keep equal weights regardless of regime
REGIME_ADJUSTMENT_ENABLED = True

# =============================================================================
# ENTRY PRICE LIMITS (US-RI-007: Jan 16, 2026 - Lower thresholds for cheaper entries)
# =============================================================================

# Global maximum entry price across all strategies
# Lower entry prices = lower fees = lower breakeven win rate
# Jan 17, 2026: RAISED for data collection - need volume to optimize
MAX_ENTRY = 0.30                  # RAISED from 0.12 → 0.30 for data collection (66% WR breakeven)
EARLY_MAX_ENTRY = 0.30            # RAISED from 0.12 → 0.30 for data collection
LATE_MAX_ENTRY = 0.35             # RAISED from 0.15 → 0.35 for data collection

# =============================================================================
# TIMING WINDOW OPTIMIZATION (US-RI-006: Jan 16, 2026)
# =============================================================================

# Based on research: Late trades (600-900s) have 62% WR, Early trades (0-300s) have 54% WR
# Apply confidence adjustments based on timing to prioritize late entries

TIMING_OPTIMIZATION_ENABLED = True  # Enable/disable timing bonuses

# Timing windows (seconds into epoch)
EARLY_WINDOW_END = 300      # 0-300s: Early window (higher risk)
LATE_WINDOW_START = 600     # 600-900s: Late window (best performance)

# Confidence adjustments (applied to final confidence score)
LATE_TIMING_BONUS = 0.05    # +5% confidence for late trades (600-900s)
EARLY_TIMING_PENALTY = 0.03 # -3% confidence for early trades (0-300s)

# =============================================================================
# TECH AGENT SETTINGS
# =============================================================================

# Exchange confluence requirements
TECH_MIN_EXCHANGES_AGREE = 2      # Minimum exchanges agreeing on direction
# Lowered from 0.30% to 0.20% to detect cumulative multi-epoch trends (US-BF-017)
TECH_CONFLUENCE_THRESHOLD = 0.002  # 0.20% minimum price change

# RSI settings
TECH_RSI_PERIOD = 14
TECH_RSI_OVERBOUGHT = 70
TECH_RSI_OVERSOLD = 30

# Scoring weights (must sum to 1.0)
TECH_EXCHANGE_WEIGHT = 0.35
TECH_MAGNITUDE_WEIGHT = 0.25
TECH_RSI_WEIGHT = 0.25
TECH_PRICE_WEIGHT = 0.15

# =============================================================================
# SENTIMENT AGENT SETTINGS
# =============================================================================

# EMERGENCY: Disable contrarian fading in trending markets
# Contrarian strategy only works in choppy/volatile regimes, NOT trending markets
# When False: SentimentAgent will skip voting (prevents counter-trend trades)
ENABLE_CONTRARIAN_TRADES = False  # DISABLED: Bleeding funds - strategy not working (Jan 16, 2026 17:00 UTC)

# Contrarian thresholds
SENTIMENT_CONTRARIAN_PRICE_THRESHOLD = 0.70  # When one side >70%, consider fading
SENTIMENT_CONTRARIAN_MAX_ENTRY = 0.10        # US-TO-QUICK-001: Max contrarian entry (LOWERED from 0.15 → ultra-cheap only)
SENTIMENT_EXTREME_THRESHOLD = 0.85           # >85% is extreme overpricing
SENTIMENT_CHEAP_ENTRY = 0.10                 # <$0.10 is very cheap

# Time window for contrarian trades (seconds into epoch)
SENTIMENT_MIN_TIME = 30
SENTIMENT_MAX_TIME = 700

# Scoring weights (must sum to 1.0)
SENTIMENT_CONTRARIAN_WEIGHT = 0.40
SENTIMENT_LIQUIDITY_WEIGHT = 0.20
SENTIMENT_EXTREMITY_WEIGHT = 0.30
SENTIMENT_RSI_WEIGHT = 0.10

# =============================================================================
# REGIME AGENT SETTINGS
# =============================================================================

# Regime classification thresholds
REGIME_HIGH_VOLATILITY = 0.015      # 1.5% std dev = volatile
REGIME_TREND_THRESHOLD = 0.0005     # 0.05% mean return = trend (lowered from 0.10% per US-BF-017)
REGIME_STRONG_TREND_RATIO = 0.75    # 75% of cryptos agreeing = strong trend

# Lookback period (number of price samples)
REGIME_LOOKBACK_WINDOWS = 20

# Weight multipliers for each regime (applied to other agents)
REGIME_MULTIPLIERS = {
    'bull_momentum': {
        'TechAgent': 1.3,
        'SentimentAgent': 0.7,
        'RiskAgent': 1.0,
    },
    'bear_momentum': {
        'TechAgent': 1.3,
        'SentimentAgent': 0.7,
        'RiskAgent': 1.0,
    },
    'sideways': {
        'TechAgent': 0.9,
        'SentimentAgent': 1.4,
        'RiskAgent': 1.0,
    },
    'volatile': {
        'TechAgent': 0.8,
        'SentimentAgent': 0.6,
        'RiskAgent': 1.5,
    }
}

# =============================================================================
# RISK AGENT SETTINGS
# =============================================================================

# Position sizing tiers (balance_threshold, max_percentage)
RISK_POSITION_TIERS = [
    (30, 0.15),      # Balance < $30: max 15% per trade
    (75, 0.10),      # Balance $30-75: max 10%
    (150, 0.07),     # Balance $75-150: max 7%
    (float('inf'), 0.05),  # Balance > $150: max 5%
]

# Absolute limits
RISK_MAX_POSITION_USD = 15.0
RISK_MIN_BET_USD = 1.10

# Risk limits
RISK_MAX_DRAWDOWN = 0.30                    # 30% drawdown = halt
RISK_MAX_TOTAL_POSITIONS = 4                # Max 4 positions at once
RISK_MAX_SAME_DIRECTION = 3                 # Max 3 positions in same direction
RISK_MAX_DIRECTIONAL_EXPOSURE = 0.08        # Max 8% of balance in one direction

# Daily limits
RISK_DAILY_LOSS_LIMIT_USD = 50.0            # Raised from $30 to $50 (Jan 16, 2026 - allow recovery trading)
RISK_DAILY_LOSS_LIMIT_PCT = 0.50            # 50% (raised from 20% to allow contrarian recovery)

# Mode multipliers (applied to position sizing)
RISK_MODE_MULTIPLIERS = {
    'aggressive': 1.0,
    'normal': 0.75,
    'conservative': 0.80,
    'defensive': 0.65,
    'recovery': 0.50,
    'halted': 0.0
}

# Consecutive loss adjustments
RISK_LOSS_ADJUSTMENTS = {
    2: 0.80,  # After 2 losses, reduce to 80%
    3: 0.65,  # After 3 losses, reduce to 65%
    4: 0.50,  # After 4 losses, reduce to 50%
}

# =============================================================================
# LOGGING & MONITORING
# =============================================================================

# Log level for agent system
AGENT_LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR

# Log vote details
LOG_VOTE_BREAKDOWN = True      # Log individual agent votes
LOG_DECISION_SUMMARY = True    # Log final decision summary
LOG_PERFORMANCE_UPDATES = True # Log when weights change

# Performance tracking
TRACK_REGIME_PERFORMANCE = True  # Track accuracy per regime
TRACK_TIME_PERFORMANCE = False   # Track accuracy by time of day (future)

# =============================================================================
# SAFETY & FALLBACK
# =============================================================================

# Fallback to old bot logic if agents fail
FALLBACK_ON_ERROR = True

# Maximum consecutive agent errors before disabling
MAX_AGENT_ERRORS = 5

# Automatic consensus threshold adjustment
AUTO_ADJUST_THRESHOLD = False   # Adjust threshold based on performance
THRESHOLD_ADJUSTMENT_INTERVAL = 100  # Adjust every N trades

# =============================================================================
# PERFORMANCE TUNING
# =============================================================================

# How quickly to adjust weights based on performance
WEIGHT_ADJUSTMENT_SPEED = 0.1  # 0.0 = slow, 1.0 = fast

# Minimum trades before adjusting weights
MIN_TRADES_FOR_ADJUSTMENT = 20

# Regime-specific weight adjustment
REGIME_WEIGHT_ADJUSTMENT_SPEED = 0.2

# =============================================================================
# DEPLOYMENT MODES
# =============================================================================

# Deployment mode presets
DEPLOYMENT_MODES = {
    'log_only': {
        'AGENT_SYSTEM_ENABLED': False,
        'CONSENSUS_THRESHOLD': 0.65,
        'description': 'Log decisions but use old bot logic'
    },
    'conservative': {
        'AGENT_SYSTEM_ENABLED': True,
        'CONSENSUS_THRESHOLD': 0.82,
        'MIN_CONFIDENCE': 0.65,
        'description': 'Higher threshold, more selective trades (US-RI-005 optimized)'
    },
    'moderate': {
        'AGENT_SYSTEM_ENABLED': True,
        'CONSENSUS_THRESHOLD': 0.40,
        'MIN_CONFIDENCE': 0.40,
        'description': 'Balanced threshold (lowered to allow trading)'
    },
    'aggressive': {
        'AGENT_SYSTEM_ENABLED': True,
        'CONSENSUS_THRESHOLD': 0.55,
        'MIN_CONFIDENCE': 0.45,
        'description': 'Lower threshold, more trades (higher risk)'
    }
}

# Current deployment mode
CURRENT_MODE = 'conservative'  # RAISED Jan 15 - reduce low-quality trades (0.75/0.60 thresholds)


def apply_mode(mode_name: str):
    """
    Apply a deployment mode preset.

    Args:
        mode_name: One of 'log_only', 'conservative', 'moderate', 'aggressive'
    """
    global AGENT_SYSTEM_ENABLED, CONSENSUS_THRESHOLD, MIN_CONFIDENCE, CURRENT_MODE

    if mode_name not in DEPLOYMENT_MODES:
        raise ValueError(f"Unknown mode: {mode_name}")

    mode = DEPLOYMENT_MODES[mode_name]

    if 'AGENT_SYSTEM_ENABLED' in mode:
        AGENT_SYSTEM_ENABLED = mode['AGENT_SYSTEM_ENABLED']

    if 'CONSENSUS_THRESHOLD' in mode:
        CONSENSUS_THRESHOLD = mode['CONSENSUS_THRESHOLD']

    if 'MIN_CONFIDENCE' in mode:
        MIN_CONFIDENCE = mode['MIN_CONFIDENCE']

    CURRENT_MODE = mode_name

    print(f"Applied deployment mode: {mode_name}")
    print(f"  {mode['description']}")
    print(f"  Enabled: {AGENT_SYSTEM_ENABLED}")
    print(f"  Consensus: {CONSENSUS_THRESHOLD}")
    print(f"  Min Confidence: {MIN_CONFIDENCE}")


def get_current_config() -> dict:
    """Get current configuration as dict."""
    return {
        'mode': CURRENT_MODE,
        'enabled': AGENT_SYSTEM_ENABLED,
        'consensus_threshold': CONSENSUS_THRESHOLD,
        'min_confidence': MIN_CONFIDENCE,
        'adaptive_weights': ADAPTIVE_WEIGHTS,
        'agent_weights': AGENT_WEIGHTS.copy(),
        'regime_adjustment_enabled': REGIME_ADJUSTMENT_ENABLED
    }


# Apply current mode on import
apply_mode(CURRENT_MODE)

# =============================================================================
# MACHINE LEARNING MODEL
# =============================================================================

# Master enable/disable for ML model (disabled due to feature leakage - 40% WR)
USE_ML_MODEL = False  # Set True to enable ML predictions (bypasses agent voting)

# =============================================================================
# BULL MARKET OVERRIDES (Bug Fix Jan 16, 2026)
# =============================================================================

# Disable bull market overrides (inappropriate for neutral/choppy markets)
# If True, ignores state/bull_market_overrides.json even if present
DISABLE_BULL_OVERRIDES = True  # Keep True to prevent inappropriate bull-biased trading

# =============================================================================
# SHADOW TRADING SYSTEM
# =============================================================================

# Master enable/disable for shadow trading (parallel strategy testing)
ENABLE_SHADOW_TRADING = True  # Set False to disable simulation system

# Shadow strategies to run in parallel (virtual trading for comparison)
# Available strategies: conservative, aggressive, contrarian_focused,
#                      momentum_focused, no_regime_adjustment, equal_weights_static,
#                      high_confidence_only, low_barrier, time_pattern variants,
#                      orderbook/funding_rate variants (Phase 1 NEW)
SHADOW_STRATEGIES = [
    # Current live strategy
    'default',                # Current production config (baseline for comparison)

    # Baseline (coin flip)
    'random_baseline',        # Random 50/50 trades (NO agents)

    # NEW: GamblerAgent + TimePattern strategies
    'gambler_veto_enabled',   # Default + GamblerAgent veto (60% threshold)
    'time_pattern_boost',     # Add TimePattern as 5th agent (0.5 weight)
    'time_pattern_heavy',     # TimePattern with 2.0 weight (strong influence)
    'time_pattern_pure',      # ONLY TimePattern (isolate performance)
    'time_pattern_gambler',   # TimePattern + GamblerAgent (best of both)
    'time_pattern_pure_gambler',  # Pure TimePattern + Gambler veto

    # PHASE 1: OrderBook + FundingRate agents (NEW - testing microstructure + derivatives signals)
    'phase1_combo',           # Both new agents boosted (OrderBook 1.2x + FundingRate 1.2x)
    'orderbook_focused',      # OrderBook 1.5x weight (test microstructure signals)
    'funding_rate_focused',   # FundingRate 1.5x weight (test derivatives signals)
    'orderbook_only',         # ONLY OrderBook (isolate performance)
    'funding_rate_only',      # ONLY FundingRate (isolate performance)
    'phase1_only',            # ONLY both new agents (no legacy agents)

    # Original top performers (kept for comparison)
    'conservative',           # High thresholds (0.75/0.60) - fewer trades
    'contrarian_focused',     # Boost SentimentAgent for contrarian signals

    # Single agent isolation
    'tech_only',             # Technical/momentum only
    'sentiment_only',        # Contrarian/sentiment only

    # INVERSE STRATEGIES (Jan 15, 2026) - Trade OPPOSITE of consensus
    # If agents are consistently wrong, inverse should win
    'inverse_consensus',     # Trade opposite of consensus vote
    'inverse_momentum',      # Trade opposite of TechAgent
    'inverse_sentiment',     # Trade opposite of SentimentAgent

    # ML STRATEGIES (Jan 15, 2026) - Machine Learning Models
    # Random Forest trained on 711 historical samples (67.3% test accuracy)
    'ml_random_forest_50',   # Random Forest with 50% threshold (trade all predictions)
    'ml_random_forest_55',   # Random Forest with 55% threshold (selective)
    'ml_random_forest_60',   # Random Forest with 60% threshold (high confidence only)

    # WEEK 2: SELECTIVE TRADING STRATEGIES (Jan 15, 2026)
    # Testing higher thresholds to improve win rate through quality over quantity
    'ultra_selective',       # Higher thresholds (0.80/0.70) - target 65%+ win rate

    # WEEK 3: KELLY CRITERION POSITION SIZING (Jan 15, 2026)
    # Testing mathematically optimal bet sizing vs fixed tiers
    'kelly_sizing',          # Kelly Criterion (default thresholds 0.40/0.40)

    # BUG FIX VALIDATION (Jan 16, 2026)
    # Shadow strategy with ALL 16 bug fixes applied for 24hr validation
    'fixed_bugs',           # All fixes (US-BF-001 to US-BF-015) - test before live deployment
]

# Shadow trading configuration
SHADOW_STARTING_BALANCE = 100.0  # Virtual starting balance for each shadow strategy
SHADOW_DB_PATH = 'simulation/trade_journal.db'  # SQLite database for logging
