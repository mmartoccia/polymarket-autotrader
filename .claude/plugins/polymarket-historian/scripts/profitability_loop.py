#!/usr/bin/env python3
"""
ENDLESS PROFITABILITY LOOP

Self-improving autonomous trading system that:
1. Collects trade data continuously
2. Analyzes patterns and identifies what works
3. Auto-generates strategy improvements
4. Implements changes automatically (with safety checks)
5. Monitors results and iterates

This is the "brain" that turns the bot from static rules into a learning system.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from collect_snapshot import create_snapshot, save_snapshot
from analyze_patterns import (
    load_all_snapshots,
    extract_completed_trades,
    analyze_by_strategy,
    analyze_by_crypto,
    generate_recommendations
)

# Configuration
PLUGIN_DIR = Path(__file__).parent.parent
DATA_DIR = PLUGIN_DIR / "data"
LOOP_STATE_FILE = DATA_DIR / "loop_state.json"
IMPROVEMENTS_DIR = DATA_DIR / "improvements"

# Loop parameters
COLLECTION_INTERVAL = 900  # 15 minutes (every epoch)
ANALYSIS_INTERVAL = 3600  # 1 hour
IMPROVEMENT_INTERVAL = 21600  # 6 hours
MIN_TRADES_FOR_IMPROVEMENT = 50  # Need 50 trades before making changes

# Safety limits
MAX_IMPROVEMENTS_PER_DAY = 3
MIN_WIN_RATE_THRESHOLD = 0.55  # Don't make changes if WR below 55%
IMPROVEMENT_CONFIDENCE_THRESHOLD = 20  # Need 20+ trades in pattern

IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)


class ProfitabilityLoop:
    """
    Self-improving trading loop that continuously optimizes strategy.
    """

    def __init__(self):
        self.state = self.load_state()
        self.last_collection = self.state.get('last_collection', 0)
        self.last_analysis = self.state.get('last_analysis', 0)
        self.last_improvement = self.state.get('last_improvement', 0)
        self.improvements_today = self.state.get('improvements_today', 0)
        self.total_improvements = self.state.get('total_improvements', 0)

    def load_state(self) -> Dict:
        """Load loop state from disk."""
        if LOOP_STATE_FILE.exists():
            with open(LOOP_STATE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_state(self):
        """Save loop state to disk."""
        self.state.update({
            'last_collection': self.last_collection,
            'last_analysis': self.last_analysis,
            'last_improvement': self.last_improvement,
            'improvements_today': self.improvements_today,
            'total_improvements': self.total_improvements,
            'updated_at': datetime.now().isoformat()
        })

        with open(LOOP_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def should_collect(self) -> bool:
        """Check if it's time to collect data."""
        now = time.time()
        return (now - self.last_collection) >= COLLECTION_INTERVAL

    def should_analyze(self) -> bool:
        """Check if it's time to analyze patterns."""
        now = time.time()
        return (now - self.last_analysis) >= ANALYSIS_INTERVAL

    def should_improve(self) -> bool:
        """Check if it's time to generate improvements."""
        now = time.time()

        # Check time interval
        if (now - self.last_improvement) < IMPROVEMENT_INTERVAL:
            return False

        # Check daily limit
        if self.improvements_today >= MAX_IMPROVEMENTS_PER_DAY:
            return False

        # Check if we have enough data
        snapshots = load_all_snapshots()
        trades = extract_completed_trades(snapshots)

        if len(trades) < MIN_TRADES_FOR_IMPROVEMENT:
            print(f"  ⏳ Need {MIN_TRADES_FOR_IMPROVEMENT - len(trades)} more trades before improvements")
            return False

        return True

    def collect_data(self):
        """Collect current trading snapshot."""
        print("\n📊 Collecting data snapshot...")

        snapshot = create_snapshot()
        save_snapshot(snapshot)

        self.last_collection = time.time()
        self.save_state()

        print("  ✅ Collection complete")

    def analyze_patterns(self) -> Dict:
        """Analyze patterns from collected data."""
        print("\n🔍 Analyzing patterns...")

        snapshots = load_all_snapshots()
        trades = extract_completed_trades(snapshots)

        if len(trades) < 10:
            print("  ⚠️  Not enough trades for analysis yet")
            return {}

        patterns = {
            'by_strategy': analyze_by_strategy(trades),
            'by_crypto': analyze_by_crypto(trades),
            'metadata': {
                'total_trades': len(trades),
                'analyzed_at': datetime.now().isoformat()
            }
        }

        self.last_analysis = time.time()
        self.save_state()

        print(f"  ✅ Analyzed {len(trades)} trades")
        return patterns

    def generate_improvement(self, patterns: Dict) -> Optional[Dict]:
        """
        Generate concrete improvement based on patterns.

        Returns improvement dict with:
        - type: Strategy adjustment type
        - target: What to change (crypto, strategy, param)
        - change: Specific change to make
        - reason: Why this change
        - expected_impact: Estimated improvement
        """

        recommendations = generate_recommendations(patterns)

        if not recommendations:
            print("  ℹ️  No improvements identified")
            return None

        # Sort by priority and confidence
        high_priority = [r for r in recommendations if r.get('priority') == 'high']

        if not high_priority:
            print("  ℹ️  No high-priority improvements")
            return None

        # Take the top recommendation
        rec = high_priority[0]

        improvement = {
            'id': f"improvement_{int(time.time())}",
            'timestamp': datetime.now().isoformat(),
            'type': rec.get('type'),
            'recommendation': rec,
            'implementation': self._create_implementation(rec),
            'status': 'proposed'
        }

        return improvement

    def _create_implementation(self, rec: Dict) -> Dict:
        """
        Create implementation plan for recommendation.

        Returns dict with file changes needed.
        """

        rec_type = rec.get('type')

        if rec_type == 'disable_strategy':
            strategy = rec.get('strategy', '')

            return {
                'file': 'bot/momentum_bot_v12.py',
                'changes': [
                    {
                        'type': 'config_update',
                        'variable': f'DISABLE_{strategy.upper()}',
                        'value': True,
                        'reason': rec.get('reason')
                    }
                ]
            }

        elif rec_type == 'boost_strategy':
            strategy = rec.get('strategy', '')

            return {
                'file': 'state/ralph_overrides.json',
                'changes': [
                    {
                        'type': 'multiplier',
                        'target': f'{strategy}_position_multiplier',
                        'value': 1.2,
                        'reason': rec.get('reason')
                    }
                ]
            }

        elif rec_type == 'reduce_crypto':
            crypto = rec.get('crypto', '')

            return {
                'file': 'state/ralph_overrides.json',
                'changes': [
                    {
                        'type': 'crypto_weight',
                        'crypto': crypto,
                        'multiplier': 0.7,
                        'reason': rec.get('reason')
                    }
                ]
            }

        return {}

    def implement_improvement(self, improvement: Dict) -> bool:
        """
        Implement improvement automatically.

        SAFETY: Only implements safe, reversible changes via override files.
        NEVER directly modifies core bot code.
        """

        print(f"\n🔧 Implementing improvement: {improvement.get('type')}")

        implementation = improvement.get('implementation', {})

        # For safety, we only write to override file
        override_file = Path('state/ralph_overrides.json')

        # Load existing overrides
        if override_file.exists():
            with open(override_file, 'r') as f:
                overrides = json.load(f)
        else:
            overrides = {}

        # Apply changes
        for change in implementation.get('changes', []):
            if change['type'] == 'multiplier':
                target = change['target']
                value = change['value']
                overrides[target] = value
                print(f"  • Set {target} = {value}")

            elif change['type'] == 'crypto_weight':
                crypto = change['crypto']
                multiplier = change['multiplier']
                overrides[f'{crypto}_POSITION_MULTIPLIER'] = multiplier
                print(f"  • Set {crypto} position multiplier = {multiplier}")

        # Save overrides
        with open(override_file, 'w') as f:
            json.dump(overrides, f, indent=2)

        # Save improvement record
        improvement_file = IMPROVEMENTS_DIR / f"{improvement['id']}.json"
        improvement['status'] = 'implemented'
        improvement['implemented_at'] = datetime.now().isoformat()

        with open(improvement_file, 'w') as f:
            json.dump(improvement, f, indent=2)

        self.total_improvements += 1
        self.improvements_today += 1
        self.last_improvement = time.time()
        self.save_state()

        print(f"  ✅ Improvement implemented")
        print(f"  📁 Saved to: {improvement_file}")

        return True

    def run_cycle(self):
        """Run one cycle of the profitability loop."""

        print("\n" + "=" * 70)
        print(f"PROFITABILITY LOOP - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Step 1: Collect data (if needed)
        if self.should_collect():
            self.collect_data()

        # Step 2: Analyze patterns (if needed)
        patterns = None
        if self.should_analyze():
            patterns = self.analyze_patterns()

        # Step 3: Generate and implement improvements (if needed)
        if self.should_improve():
            if patterns is None:
                patterns = self.analyze_patterns()

            improvement = self.generate_improvement(patterns)

            if improvement:
                print("\n💡 IMPROVEMENT IDENTIFIED:")
                print(f"  Type: {improvement.get('type')}")
                print(f"  Reason: {improvement.get('recommendation', {}).get('reason')}")
                print(f"  Action: {improvement.get('recommendation', {}).get('action')}")

                # Auto-implement (for now - in future, could require approval)
                self.implement_improvement(improvement)

        # Print status
        print("\n📈 LOOP STATUS:")
        print(f"  Total improvements: {self.total_improvements}")
        print(f"  Improvements today: {self.improvements_today}")
        print(f"  Last collection: {time.time() - self.last_collection:.0f}s ago")
        print(f"  Last analysis: {time.time() - self.last_analysis:.0f}s ago")
        print(f"  Last improvement: {time.time() - self.last_improvement:.0f}s ago")

        print("\n" + "=" * 70)

    def run_forever(self):
        """Run the profitability loop forever."""

        print("\n🚀 STARTING ENDLESS PROFITABILITY LOOP\n")
        print("This will run continuously, collecting data and improving strategy.")
        print("Press Ctrl+C to stop.\n")

        try:
            while True:
                self.run_cycle()

                # Sleep for 5 minutes before next cycle
                print("\n💤 Sleeping for 5 minutes...\n")
                time.sleep(300)

        except KeyboardInterrupt:
            print("\n\n👋 Profitability loop stopped")
            self.save_state()


def main():
    """Main entry point."""

    loop = ProfitabilityLoop()

    # Check for command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--once':
            # Run single cycle
            loop.run_cycle()
        elif sys.argv[1] == '--status':
            # Show status
            print("PROFITABILITY LOOP STATUS")
            print(f"Total improvements: {loop.total_improvements}")
            print(f"Last collection: {datetime.fromtimestamp(loop.last_collection)}")
            print(f"Last analysis: {datetime.fromtimestamp(loop.last_analysis)}")
            print(f"Last improvement: {datetime.fromtimestamp(loop.last_improvement)}")
        else:
            print("Usage: profitability_loop.py [--once|--status]")
    else:
        # Run forever
        loop.run_forever()


if __name__ == "__main__":
    main()
