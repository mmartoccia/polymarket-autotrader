#!/usr/bin/env python3
"""
Analyze Agent Decision Patterns - Find Optimal Thresholds

This script analyzes recent bot decisions to identify:
1. Trades that were SKIPPED but should have been taken (correct direction, too low score)
2. Trades that were TAKEN but lost (incorrect direction, score too high)
3. Optimal threshold ranges based on actual market outcomes

Usage:
    python3 scripts/analyze_agent_decisions.py [--log-file bot.log] [--trades 100]
"""

import re
import argparse
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Optional, Tuple


class DecisionAnalyzer:
    """Analyzes bot decision patterns to optimize thresholds"""
    
    def __init__(self, log_file: str = "bot.log"):
        self.log_file = log_file
        self.decisions = []
        self.skipped_signals = []
        self.taken_trades = []
        
    def parse_log(self, max_lines: int = 5000):
        """Parse bot log for decision points"""
        print(f"Parsing {self.log_file} (last {max_lines} lines)...")
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()[-max_lines:]
        except FileNotFoundError:
            print(f"❌ Log file not found: {self.log_file}")
            print("This script needs to run on the VPS with access to bot.log")
            return False
            
        # Patterns to extract
        skip_pattern = re.compile(r'SKIP.*?confidence[:\s]+(\d+\.?\d*).*?consensus[:\s]+(\d+\.?\d*).*?direction[:\s]+(\w+)', re.IGNORECASE)
        signal_pattern = re.compile(r'SIGNAL.*?(\w+).*?confidence[:\s]+(\d+\.?\d*).*?weighted[:\s]+(\d+\.?\d*)', re.IGNORECASE)
        trade_pattern = re.compile(r'ORDER PLACED.*?(\w+).*?(\d+\.?\d*)', re.IGNORECASE)
        outcome_pattern = re.compile(r'(WIN|LOSS).*?(\w+).*?entry[:\s]+\$?(\d+\.?\d*)', re.IGNORECASE)
        
        for line in lines:
            # Extract skipped signals
            if 'SKIP' in line:
                match = skip_pattern.search(line)
                if match:
                    confidence, consensus, direction = match.groups()
                    self.skipped_signals.append({
                        'confidence': float(confidence),
                        'consensus': float(consensus),
                        'direction': direction,
                        'timestamp': self._extract_timestamp(line)
                    })
            
            # Extract signal decisions
            elif 'SIGNAL' in line and 'confidence' in line.lower():
                match = signal_pattern.search(line)
                if match:
                    direction, confidence, weighted = match.groups()
                    self.decisions.append({
                        'type': 'signal',
                        'direction': direction,
                        'confidence': float(confidence),
                        'weighted_score': float(weighted),
                        'timestamp': self._extract_timestamp(line)
                    })
                    
            # Extract trade outcomes
            elif any(x in line for x in ['WIN', 'LOSS']):
                match = outcome_pattern.search(line)
                if match:
                    outcome, direction, entry = match.groups()
                    self.taken_trades.append({
                        'outcome': outcome,
                        'direction': direction,
                        'entry_price': float(entry),
                        'timestamp': self._extract_timestamp(line)
                    })
        
        print(f"✅ Parsed {len(self.skipped_signals)} skipped signals")
        print(f"✅ Parsed {len(self.decisions)} signal decisions")
        print(f"✅ Parsed {len(self.taken_trades)} trade outcomes")
        return True
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line"""
        match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
        return match.group(1) if match else None
    
    def analyze_skipped_opportunities(self) -> Dict:
        """Analyze signals that were skipped to find missed opportunities"""
        print("\n" + "="*70)
        print("📊 SKIPPED SIGNAL ANALYSIS")
        print("="*70)
        
        if not self.skipped_signals:
            print("No skipped signals found in log")
            return {}
        
        # Group by confidence/consensus ranges
        ranges = {
            'very_low': {'confidence': (0.0, 0.50), 'consensus': (0.0, 0.60), 'count': 0},
            'low': {'confidence': (0.50, 0.65), 'consensus': (0.60, 0.75), 'count': 0},
            'medium': {'confidence': (0.65, 0.75), 'consensus': (0.75, 0.82), 'count': 0},
            'high': {'confidence': (0.75, 0.85), 'consensus': (0.82, 0.90), 'count': 0},
            'very_high': {'confidence': (0.85, 1.0), 'consensus': (0.90, 1.0), 'count': 0}
        }
        
        for signal in self.skipped_signals:
            for range_name, range_def in ranges.items():
                conf_min, conf_max = range_def['confidence']
                cons_min, cons_max = range_def['consensus']
                
                if (conf_min <= signal['confidence'] < conf_max and 
                    cons_min <= signal['consensus'] < cons_max):
                    range_def['count'] += 1
                    break
        
        print("\nSkipped signals by threshold range:")
        print(f"{'Range':<12} {'Confidence':<20} {'Consensus':<20} {'Count':>8}")
        print("-"*70)
        for range_name, range_def in ranges.items():
            print(f"{range_name:<12} "
                  f"{range_def['confidence'][0]:.2f}-{range_def['confidence'][1]:.2f}"
                  f"{'':<10} "
                  f"{range_def['consensus'][0]:.2f}-{range_def['consensus'][1]:.2f}"
                  f"{'':<10} "
                  f"{range_def['count']:>8}")
        
        # Show top skipped signals (closest to threshold)
        near_threshold = [s for s in self.skipped_signals 
                          if 0.70 <= s['consensus'] < 0.82]
        near_threshold.sort(key=lambda x: x['consensus'], reverse=True)
        
        print(f"\n🎯 Top 10 signals closest to threshold (0.82):")
        print(f"{'Direction':<10} {'Confidence':<12} {'Consensus':<12} {'Gap to 0.82'}")
        print("-"*70)
        for signal in near_threshold[:10]:
            gap = 0.82 - signal['consensus']
            print(f"{signal['direction']:<10} "
                  f"{signal['confidence']:<12.1%} "
                  f"{signal['consensus']:<12.1%} "
                  f"-{gap:.1%}")
        
        return {
            'total_skipped': len(self.skipped_signals),
            'near_threshold': len(near_threshold),
            'ranges': ranges
        }
    
    def suggest_optimal_thresholds(self) -> Dict:
        """Suggest optimal threshold adjustments"""
        print("\n" + "="*70)
        print("💡 THRESHOLD OPTIMIZATION SUGGESTIONS")
        print("="*70)
        
        near_threshold = [s for s in self.skipped_signals 
                          if 0.70 <= s['consensus'] < 0.82]
        
        if not near_threshold:
            print("✅ No signals close to threshold - current settings appear optimal")
            return {'recommendation': 'keep_current'}
        
        # Calculate average consensus of near-threshold signals
        avg_consensus = sum(s['consensus'] for s in near_threshold) / len(near_threshold)
        avg_confidence = sum(s['confidence'] for s in near_threshold) / len(near_threshold)
        
        print(f"\n📈 Signals near threshold (0.70-0.82):")
        print(f"   Count: {len(near_threshold)}")
        print(f"   Avg Consensus: {avg_consensus:.1%}")
        print(f"   Avg Confidence: {avg_confidence:.1%}")
        
        # Recommendations
        print("\n🎯 RECOMMENDATIONS:")
        
        if len(near_threshold) > 20:
            new_threshold = round(avg_consensus - 0.03, 2)
            print(f"\n1. **Lower CONSENSUS_THRESHOLD**: 0.82 → {new_threshold}")
            print(f"   Rationale: {len(near_threshold)} signals in 0.70-0.82 range")
            print(f"   Expected: +{len(near_threshold) // 2} trades/week")
            print(f"   Risk: Medium (need to validate direction accuracy)")
        
        if avg_confidence < 0.60:
            print(f"\n2. **Lower MIN_CONFIDENCE**: 0.65 → 0.60")
            print(f"   Rationale: Avg confidence of near-threshold signals is {avg_confidence:.1%}")
            print(f"   Expected: Better capture of medium-confidence opportunities")
        
        print("\n⚠️  CAUTION:")
        print("   - These are SUGGESTIONS based on signal volume only")
        print("   - MUST validate actual market outcomes (were skipped signals correct?)")
        print("   - Recommend shadow testing before production deployment")
        
        return {
            'recommendation': 'lower_thresholds',
            'suggested_consensus': new_threshold if len(near_threshold) > 20 else 0.82,
            'near_threshold_count': len(near_threshold),
            'avg_consensus': avg_consensus,
            'avg_confidence': avg_confidence
        }


def main():
    parser = argparse.ArgumentParser(description="Analyze bot decision patterns")
    parser.add_argument('--log-file', default='bot.log', 
                        help='Path to bot log file (default: bot.log)')
    parser.add_argument('--lines', type=int, default=5000,
                        help='Number of log lines to analyze (default: 5000)')
    
    args = parser.parse_args()
    
    print("="*70)
    print("🔍 AGENT DECISION PATTERN ANALYZER")
    print("="*70)
    print(f"Log file: {args.log_file}")
    print(f"Lines to analyze: {args.lines}")
    
    analyzer = DecisionAnalyzer(log_file=args.log_file)
    
    if not analyzer.parse_log(max_lines=args.lines):
        return 1
    
    # Analyze skipped opportunities
    analyzer.analyze_skipped_opportunities()
    
    # Suggest optimal thresholds
    analyzer.suggest_optimal_thresholds()
    
    print("\n" + "="*70)
    print("✅ Analysis complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review skipped signals to see if they would have been profitable")
    print("2. If yes, shadow test lower thresholds (e.g., 0.78-0.80)")
    print("3. Monitor win rate impact before production deployment")
    print("4. Use `PRD.md` to document threshold tuning experiments")
    
    return 0


if __name__ == '__main__':
    exit(main())
