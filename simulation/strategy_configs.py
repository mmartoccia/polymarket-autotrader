#!/usr/bin/env python3
"""
Strategy Configuration Library

Defines strategy configurations for shadow trading simulation.
Each configuration represents a different approach to trading decisions.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Optional
import json


@dataclass
class StrategyConfig:
    """
    Configuration for a trading strategy.
    
    Attributes:
        name: Unique strategy identifier
        description: Human-readable description
        consensus_threshold: Minimum weighted score to trade (0-1)
        min_confidence: Minimum average agent confidence (0-1)
        min_individual_confidence: Minimum per-agent confidence (0-1)
        agent_weights: Base weights for each agent
        adaptive_weights: Enable performance-based weight adjustment
        regime_adjustment_enabled: Enable regime-based weight adjustments
        tech_config: Override TECH_* config settings
        sentiment_config: Override SENTIMENT_* config settings
        regime_config: Override REGIME_* config settings
        risk_config: Override RISK_* config settings
        max_position_pct: Max position size as % of balance
        max_same_direction: Max positions in same direction
        mode: Deployment mode (log_only, conservative, moderate, aggressive)
        created: Creation timestamp
        is_live: True if this strategy controls real bot, False if shadow
    """
    name: str
    description: str

    # Core thresholds
    consensus_threshold: float = 0.40
    min_confidence: float = 0.40
    min_individual_confidence: float = 0.30

    # Agent weights (base multipliers before adaptive adjustment)
    agent_weights: Dict[str, float] = field(default_factory=lambda: {
        'TechAgent': 1.0,
        'SentimentAgent': 1.0,
        'RegimeAgent': 1.0,
        'CandlestickAgent': 1.0,
        'OrderBookAgent': 0.8,
        'FundingRateAgent': 0.8,
        'OnChainAgent': 0.0,           # Disabled by default (requires API key)
        'SocialSentimentAgent': 0.0    # Disabled by default (requires API keys)
    })

    # Features
    adaptive_weights: bool = True
    regime_adjustment_enabled: bool = True

    # Agent-specific config overrides
    tech_config: Optional[Dict] = None
    sentiment_config: Optional[Dict] = None
    regime_config: Optional[Dict] = None
    risk_config: Optional[Dict] = None

    # Risk management
    max_position_pct: float = 0.15
    max_same_direction: int = 3

    # Deployment mode
    mode: str = 'moderate'

    # ML-specific settings (Jan 15, 2026)
    use_ml_model: bool = False  # True to bypass agents and use ML predictions
    ml_model_name: Optional[str] = None  # 'random_forest' or 'logistic_regression'
    ml_threshold: float = 0.50  # Minimum win probability to trade

    # Metadata
    created: datetime = field(default_factory=datetime.now)
    is_live: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = self.to_dict()
        # Convert datetime to ISO format
        data['created'] = data['created'].isoformat() if isinstance(data['created'], datetime) else data['created']
        return json.dumps(data, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> 'StrategyConfig':
        """Create from dictionary."""
        # Convert ISO string back to datetime
        if isinstance(data.get('created'), str):
            data['created'] = datetime.fromisoformat(data['created'])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'StrategyConfig':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


# Pre-defined strategy templates
STRATEGY_LIBRARY = {
    'default': StrategyConfig(
        name='default',
        description='Current production strategy (moderate thresholds)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        is_live=True  # This is the live bot's config
    ),

    'conservative': StrategyConfig(
        name='conservative',
        description='High thresholds - fewer, higher-quality trades',
        consensus_threshold=0.75,
        min_confidence=0.60,
        min_individual_confidence=0.40,
        max_position_pct=0.10,
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.2,  # Boost regime awareness
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'aggressive': StrategyConfig(
        name='aggressive',
        description='Lower thresholds - more trades, higher risk',
        consensus_threshold=0.55,
        min_confidence=0.45,
        min_individual_confidence=0.25,
        max_position_pct=0.20,
        agent_weights={
            'TechAgent': 1.2,
            'SentimentAgent': 1.2,
            'RegimeAgent': 0.8,  # Less regime caution
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'contrarian_focused': StrategyConfig(
        name='contrarian_focused',
        description='Boost sentiment agent for contrarian signals',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.7,
            'SentimentAgent': 1.5,  # Boost contrarian
            'RegimeAgent': 1.0,
            'CandlestickAgent': 0.8,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        },
        sentiment_config={
            'SENTIMENT_CONTRARIAN_MAX_ENTRY': 0.25,  # Allow more expensive entries
            'SENTIMENT_CONTRARIAN_PRICE_THRESHOLD': 0.65  # Lower threshold (>65% = contrarian)
        }
    ),

    'momentum_focused': StrategyConfig(
        name='momentum_focused',
        description='Boost tech agent for momentum signals',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 1.5,  # Boost momentum
            'SentimentAgent': 0.7,
            'RegimeAgent': 1.2,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        },
        tech_config={
            'TECH_CONFLUENCE_THRESHOLD': 0.0010,  # Lower bar (0.10% instead of 0.15%)
            'TECH_MIN_EXCHANGES_AGREE': 2  # Keep at 2
        }
    ),

    'no_regime_adjustment': StrategyConfig(
        name='no_regime_adjustment',
        description='Disable regime-based weight adjustments',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        regime_adjustment_enabled=False,
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'equal_weights_static': StrategyConfig(
        name='equal_weights_static',
        description='All agents equal weight, no adaptive adjustments',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        adaptive_weights=False,
        regime_adjustment_enabled=False,
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    # === INVERSE/CONTRARIAN STRATEGIES (Trade OPPOSITE of consensus) ===

    'inverse_consensus': StrategyConfig(
        name='inverse_consensus',
        description='Trade OPPOSITE direction of agent consensus (contrarian)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': -1.0,      # NEGATIVE weights = inverse direction
            'SentimentAgent': -1.0,
            'RegimeAgent': -1.0,
            'CandlestickAgent': -1.0,
            'OrderBookAgent': -0.8,
            'FundingRateAgent': -0.8
        }
    ),

    'inverse_momentum': StrategyConfig(
        name='inverse_momentum',
        description='Fade momentum - trade against strong directional moves',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': -1.5,      # Strongly fade momentum
            'SentimentAgent': 1.0,  # Keep sentiment normal
            'RegimeAgent': -1.0,
            'CandlestickAgent': -0.8,
            'OrderBookAgent': -0.8,
            'FundingRateAgent': -0.8
        }
    ),

    'inverse_sentiment': StrategyConfig(
        name='inverse_sentiment',
        description='Fade sentiment - go with the crowd instead of against',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': -1.5,  # Invert sentiment (go with crowd)
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    # === EXTREME THRESHOLDS (Very selective vs Very aggressive) ===

    'ultra_conservative': StrategyConfig(
        name='ultra_conservative',
        description='Extremely high thresholds - only perfect setups',
        consensus_threshold=0.85,  # Very high consensus required
        min_confidence=0.75,       # Very high confidence required
        min_individual_confidence=0.60,
        max_position_pct=0.08,     # Smaller positions
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'ultra_aggressive': StrategyConfig(
        name='ultra_aggressive',
        description='Very low thresholds - take every signal',
        consensus_threshold=0.25,  # Low bar
        min_confidence=0.25,       # Low confidence OK
        min_individual_confidence=0.15,
        max_position_pct=0.25,     # Bigger positions
        agent_weights={
            'TechAgent': 1.2,
            'SentimentAgent': 1.2,
            'RegimeAgent': 0.5,  # Ignore regime warnings
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    # === SINGLE AGENT STRATEGIES (Isolate each agent's performance) ===

    'tech_only': StrategyConfig(
        name='tech_only',
        description='Technical analysis only - momentum/confluence signals',
        consensus_threshold=0.30,  # Lower since only 1 agent
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 0.0,  # Disabled
            'RegimeAgent': 0.0,     # Disabled
            'CandlestickAgent': 0.0  # Disabled
        }
    ),

    'sentiment_only': StrategyConfig(
        name='sentiment_only',
        description='Sentiment/contrarian only - fade overpriced sides',
        consensus_threshold=0.30,
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0
        }
    ),

    'regime_only': StrategyConfig(
        name='regime_only',
        description='Regime analysis only - market structure signals',
        consensus_threshold=0.30,
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,
            'SentimentAgent': 0.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 0.0
        }
    ),

    'random_baseline': StrategyConfig(
        name='random_baseline',
        description='Random 50/50 trades as baseline (all agents zero weight)',
        consensus_threshold=0.01,  # Always trade (baseline)
        min_confidence=0.01,
        min_individual_confidence=0.01,
        agent_weights={
            'TechAgent': 0.0,
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0
        }
    ),

    'high_confidence_only': StrategyConfig(
        name='high_confidence_only',
        description='Extreme quality filter - only highest confidence trades',
        consensus_threshold=0.80,
        min_confidence=0.70,
        min_individual_confidence=0.50,
        max_position_pct=0.20,  # Larger bets when confident
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.5,  # Boost regime alignment
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'low_barrier': StrategyConfig(
        name='low_barrier',
        description='Lower thresholds to capture more opportunities',
        consensus_threshold=0.35,
        min_confidence=0.35,
        min_individual_confidence=0.20,
        max_position_pct=0.10,  # Smaller bets due to lower confidence
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    # === TIME PATTERN STRATEGIES (Use historical hour-based patterns) ===

    'time_pattern_pure': StrategyConfig(
        name='time_pattern_pure',
        description='Pure time-pattern agent (no tech/sentiment/regime)',
        consensus_threshold=0.55,  # Single agent, require moderate strength
        min_confidence=0.55,
        min_individual_confidence=0.55,
        agent_weights={
            'TimePatternAgent': 1.0,  # Only agent
            'TechAgent': 0.0,         # Disabled
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0
        }
    ),

    'time_pattern_boost': StrategyConfig(
        name='time_pattern_boost',
        description='All agents + time pattern boost (5th agent)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TimePatternAgent': 0.5,  # Add as 5th agent with half weight
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'time_pattern_heavy': StrategyConfig(
        name='time_pattern_heavy',
        description='Time patterns heavily weighted (2x other agents)',
        consensus_threshold=0.45,
        min_confidence=0.45,
        min_individual_confidence=0.30,
        agent_weights={
            'TimePatternAgent': 2.0,  # Double weight vs others
            'TechAgent': 1.0,
            'SentimentAgent': 0.7,    # Reduce other agents slightly
            'RegimeAgent': 0.7,
            'CandlestickAgent': 0.7,
            'OrderBookAgent': 0.7,
            'FundingRateAgent': 0.7,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    # === GAMBLER AGENT STRATEGIES (Probability veto) ===

    'gambler_veto_enabled': StrategyConfig(
        name='gambler_veto_enabled',
        description='Default strategy + GamblerAgent veto (60% threshold)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            # GamblerAgent automatically added as veto agent in wrapper
        }
    ),

    'time_pattern_gambler': StrategyConfig(
        name='time_pattern_gambler',
        description='TimePattern (0.5 weight) + GamblerAgent veto',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TimePatternAgent': 0.5,  # 5th voting agent (half weight)
            'TechAgent': 1.0,
            'SentimentAgent': 1.0,
            'RegimeAgent': 1.0,
            'CandlestickAgent': 1.0,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 0.8,
            # GamblerAgent automatically added as veto agent
        }
    ),

    'time_pattern_pure_gambler': StrategyConfig(
        name='time_pattern_pure_gambler',
        description='ONLY TimePattern + GamblerAgent (isolate time patterns)',
        consensus_threshold=0.55,  # Higher threshold for single agent
        min_confidence=0.55,
        min_individual_confidence=0.55,
        agent_weights={
            'TimePatternAgent': 1.0,  # Only voting agent
            'TechAgent': 0.0,         # Disabled
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            # GamblerAgent automatically added as veto agent
        }
    ),

    # === PHASE 1 NEW AGENT STRATEGIES (OrderBook + FundingRate) ===

    'orderbook_focused': StrategyConfig(
        name='orderbook_focused',
        description='Boost OrderBookAgent for microstructure signals',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.8,
            'SentimentAgent': 0.8,
            'RegimeAgent': 0.8,
            'CandlestickAgent': 0.8,
            'OrderBookAgent': 1.5,     # Boost orderbook analysis
            'FundingRateAgent': 0.8,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'funding_rate_focused': StrategyConfig(
        name='funding_rate_focused',
        description='Boost FundingRateAgent for derivatives signals',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.8,
            'SentimentAgent': 0.8,
            'RegimeAgent': 0.8,
            'CandlestickAgent': 0.8,
            'OrderBookAgent': 0.8,
            'FundingRateAgent': 1.5     # Boost funding rate analysis
        }
    ),

    'phase1_combo': StrategyConfig(
        name='phase1_combo',
        description='Both new agents boosted (OrderBook + FundingRate)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.7,
            'SentimentAgent': 0.7,
            'RegimeAgent': 0.7,
            'CandlestickAgent': 0.7,
            'OrderBookAgent': 1.2,      # Boost both new agents
            'FundingRateAgent': 1.2,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'orderbook_only': StrategyConfig(
        name='orderbook_only',
        description='ONLY OrderBookAgent (isolate microstructure performance)',
        consensus_threshold=0.30,  # Lower threshold for single agent
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,           # Disabled
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            'OrderBookAgent': 1.0,      # Only agent
            'FundingRateAgent': 0.0,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    'funding_rate_only': StrategyConfig(
        name='funding_rate_only',
        description='ONLY FundingRateAgent (isolate derivatives performance)',
        consensus_threshold=0.30,  # Lower threshold for single agent
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,           # Disabled
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            'OrderBookAgent': 0.0,
            'FundingRateAgent': 1.0     # Only agent
        }
    ),

    'phase1_only': StrategyConfig(
        name='phase1_only',
        description='ONLY new Phase 1 agents (OrderBook + FundingRate)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,           # Disabled
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            'OrderBookAgent': 1.0,      # Both new agents only
            'FundingRateAgent': 1.0,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 0.0
        }
    ),

    # === WEEK 3 AGENTS (OnChain + SocialSentiment) ===

    'onchain_focused': StrategyConfig(
        name='onchain_focused',
        description='Boost OnChainAgent for whale tracking signals',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.7,
            'SentimentAgent': 0.7,
            'RegimeAgent': 0.7,
            'CandlestickAgent': 0.7,
            'OrderBookAgent': 0.7,
            'FundingRateAgent': 0.7,
            'OnChainAgent': 1.5,           # Boost on-chain signals
            'SocialSentimentAgent': 0.0
        }
    ),

    'social_sentiment_focused': StrategyConfig(
        name='social_sentiment_focused',
        description='Boost SocialSentimentAgent for crowd psychology',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.7,
            'SentimentAgent': 0.7,
            'RegimeAgent': 0.7,
            'CandlestickAgent': 0.7,
            'OrderBookAgent': 0.7,
            'FundingRateAgent': 0.7,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 1.5    # Boost social signals
        }
    ),

    'phase1_week3_combo': StrategyConfig(
        name='phase1_week3_combo',
        description='All Phase 1 agents (OrderBook, Funding, OnChain, Social)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.7,
            'SentimentAgent': 0.7,
            'RegimeAgent': 0.7,
            'CandlestickAgent': 0.7,
            'OrderBookAgent': 1.0,         # All Phase 1 agents
            'FundingRateAgent': 1.0,
            'OnChainAgent': 1.0,
            'SocialSentimentAgent': 1.0
        }
    ),

    'onchain_only': StrategyConfig(
        name='onchain_only',
        description='ONLY OnChainAgent (isolate whale tracking performance)',
        consensus_threshold=0.30,  # Lower threshold for single agent
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            'OrderBookAgent': 0.0,
            'FundingRateAgent': 0.0,
            'OnChainAgent': 1.0,           # Only agent
            'SocialSentimentAgent': 0.0
        }
    ),

    'social_sentiment_only': StrategyConfig(
        name='social_sentiment_only',
        description='ONLY SocialSentimentAgent (isolate crowd psychology performance)',
        consensus_threshold=0.30,  # Lower threshold for single agent
        min_confidence=0.35,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            'OrderBookAgent': 0.0,
            'FundingRateAgent': 0.0,
            'OnChainAgent': 0.0,
            'SocialSentimentAgent': 1.0    # Only agent
        }
    ),

    'week3_only': StrategyConfig(
        name='week3_only',
        description='ONLY Week 3 agents (OnChain + SocialSentiment)',
        consensus_threshold=0.40,
        min_confidence=0.40,
        min_individual_confidence=0.30,
        agent_weights={
            'TechAgent': 0.0,
            'SentimentAgent': 0.0,
            'RegimeAgent': 0.0,
            'CandlestickAgent': 0.0,
            'OrderBookAgent': 0.0,
            'FundingRateAgent': 0.0,
            'OnChainAgent': 1.0,           # Week 3 agents only
            'SocialSentimentAgent': 1.0
        }
    ),

    # =============================================================================
    # ML STRATEGIES (Jan 15, 2026)
    # =============================================================================
    # Random Forest model trained on 711 historical samples
    # Test accuracy: 67.3% (+17.3% edge over 50% baseline)
    # These are SPECIAL strategies that bypass agent voting and use ML predictions

    'ml_random_forest_50': StrategyConfig(
        name='ml_random_forest_50',
        description='ML Random Forest model (50% threshold - trade all predictions)',
        consensus_threshold=0.50,  # Not used (ML bypasses consensus)
        min_confidence=0.50,
        min_individual_confidence=0.30,
        use_ml_model=True,  # SPECIAL: Bypass agents, use ML
        ml_model_name='random_forest',
        ml_threshold=0.50,  # Trade if win probability >= 50%
        agent_weights={}  # Empty - ML bypasses agents
    ),

    'ml_random_forest_55': StrategyConfig(
        name='ml_random_forest_55',
        description='ML Random Forest model (55% threshold - selective trading)',
        consensus_threshold=0.55,
        min_confidence=0.55,
        min_individual_confidence=0.30,
        use_ml_model=True,
        ml_model_name='random_forest',
        ml_threshold=0.55,  # Trade if win probability >= 55%
        agent_weights={}
    ),

    'ml_random_forest_60': StrategyConfig(
        name='ml_random_forest_60',
        description='ML Random Forest model (60% threshold - high confidence only)',
        consensus_threshold=0.60,
        min_confidence=0.60,
        min_individual_confidence=0.30,
        use_ml_model=True,
        ml_model_name='random_forest',
        ml_threshold=0.60,  # Trade if win probability >= 60%
        agent_weights={}
    )
}


def get_strategy(name: str) -> StrategyConfig:
    """
    Get strategy config by name.
    
    Args:
        name: Strategy name from STRATEGY_LIBRARY
        
    Returns:
        StrategyConfig instance
        
    Raises:
        KeyError: If strategy not found
    """
    if name not in STRATEGY_LIBRARY:
        available = ', '.join(STRATEGY_LIBRARY.keys())
        raise KeyError(f"Strategy '{name}' not found. Available: {available}")
    
    return STRATEGY_LIBRARY[name]


def list_strategies() -> list:
    """
    List all available strategy names.
    
    Returns:
        List of strategy names
    """
    return list(STRATEGY_LIBRARY.keys())


def save_strategy(config: StrategyConfig, filepath: str):
    """
    Save strategy config to JSON file.
    
    Args:
        config: StrategyConfig to save
        filepath: Path to save JSON file
    """
    with open(filepath, 'w') as f:
        f.write(config.to_json())


def load_strategy(filepath: str) -> StrategyConfig:
    """
    Load strategy config from JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        StrategyConfig instance
    """
    with open(filepath, 'r') as f:
        return StrategyConfig.from_json(f.read())
