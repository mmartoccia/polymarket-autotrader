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

# Consensus requirements (RAISED Jan 15, 2026 - reduce low-quality trades after 87% loss)
CONSENSUS_THRESHOLD = 0.75     # Minimum weighted score to trade (RAISED from 0.40)
MIN_CONFIDENCE = 0.60          # Minimum average agent confidence (RAISED from 0.40)
MIN_INDIVIDUAL_CONFIDENCE = 0.30  # Minimum per-agent confidence (enforced in vote_aggregator.py)
ADAPTIVE_WEIGHTS = True        # Enable performance-based weight tuning

# Agent weights (base multipliers, will be adjusted by performance)
AGENT_WEIGHTS = {
    'TechAgent': 1.0,              # Technical analysis
    'SentimentAgent': 1.0,         # Contrarian signals
    'RegimeAgent': 1.0,            # Market classification
    'CandlestickAgent': 1.0,       # Candlestick pattern analysis
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
AGENT_ENABLED = {
    'TechAgent': True,
    'SentimentAgent': True,
    'RegimeAgent': True,
    'CandlestickAgent': True,
    'TimePatternAgent': True,
    'OrderBookAgent': True,
    'FundingRateAgent': True,
    'OnChainAgent': False,  # Disabled: No API keys configured
    'SocialSentimentAgent': False,  # Disabled: No API keys configured
    'RiskAgent': True,
    'GamblerAgent': True,
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
# ENTRY PRICE LIMITS (Bug Fix Jan 16, 2026)
# =============================================================================

# Global maximum entry price across all strategies
# Lower entry prices = lower fees = lower breakeven win rate
MAX_ENTRY = 0.25                  # Global cap (reduces breakeven WR from 52% to 51%)
EARLY_MAX_ENTRY = 0.30            # Early momentum maximum (overridden by MAX_ENTRY if lower)

# =============================================================================
# TECH AGENT SETTINGS
# =============================================================================

# Exchange confluence requirements
TECH_MIN_EXCHANGES_AGREE = 2      # Minimum exchanges agreeing on direction
TECH_CONFLUENCE_THRESHOLD = 0.0015 # 0.15% minimum price change

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

# Contrarian thresholds
SENTIMENT_CONTRARIAN_PRICE_THRESHOLD = 0.70  # When one side >70%, consider fading
SENTIMENT_CONTRARIAN_MAX_ENTRY = 0.20        # Max price to pay for contrarian entry
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
REGIME_TREND_THRESHOLD = 0.001      # 0.1% mean return = trend
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
RISK_DAILY_LOSS_LIMIT_USD = 30.0
RISK_DAILY_LOSS_LIMIT_PCT = 0.20            # 20%

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
        'CONSENSUS_THRESHOLD': 0.75,
        'MIN_CONFIDENCE': 0.60,
        'description': 'Higher threshold, more selective trades'
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
]

# Shadow trading configuration
SHADOW_STARTING_BALANCE = 100.0  # Virtual starting balance for each shadow strategy
SHADOW_DB_PATH = 'simulation/trade_journal.db'  # SQLite database for logging
