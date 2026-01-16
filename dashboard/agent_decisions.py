#!/usr/bin/env python3
"""
Agent Decision Dashboard - Real-time agent voting and decision tracking

Shows:
- Recent agent votes by crypto (BTC, ETH, SOL, XRP)
- Vote aggregation summaries
- Decision trends over time
- Individual agent reasoning
"""

import re
import subprocess
import time
import os
from datetime import datetime
from collections import defaultdict, deque

REFRESH_INTERVAL = 5  # seconds
LOG_FILE = "/opt/polymarket-autotrader/bot.log"
HISTORY_SIZE = 50  # Keep last 50 decisions per crypto

# Set TERM immediately to prevent errors
if 'TERM' not in os.environ:
    os.environ['TERM'] = 'xterm-256color'


class AgentDecisionTracker:
    """Track and display agent decisions over time"""

    def __init__(self):
        self.decisions = {
            'BTC': deque(maxlen=HISTORY_SIZE),
            'ETH': deque(maxlen=HISTORY_SIZE),
            'SOL': deque(maxlen=HISTORY_SIZE),
            'XRP': deque(maxlen=HISTORY_SIZE)
        }
        self.last_position = 0  # File position for incremental reading

    def parse_log_entry(self, lines, start_idx):
        """Parse a single decision entry from log lines"""
        decision = {}

        # Look for crypto context - appears AFTER vote aggregation in "[BTC] Agent Decision" line
        for i in range(start_idx, min(len(lines), start_idx+30)):
            # Check for "[BTC] Agent Decision" pattern (comes after aggregation box)
            agent_decision = re.search(r'\[(\w+)\] Agent Decision', lines[i])
            if agent_decision:
                decision['crypto'] = agent_decision.group(1)
                break

        # Also look backward for "Making decision for BTC epoch" (comes before)
        if 'crypto' not in decision:
            for i in range(max(0, start_idx-15), start_idx):
                crypto_match = re.search(r'Making decision for (\w+) epoch', lines[i])
                if crypto_match:
                    decision['crypto'] = crypto_match.group(1)
                    break

        # Look for crypto symbol
        for line in lines[start_idx:start_idx+30]:
            # Extract timestamp
            timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match and 'timestamp' not in decision:
                decision['timestamp'] = timestamp_match.group(1)

            # Agent votes WITHIN aggregation box (e.g., "⬆️ OrderBookAgent - C:0.51 Q:1.00")
            agent_in_box = re.search(r'[⬆️⬇️➡️]\s+(\w+Agent)\s+-\s+C:([\d.]+)\s+Q:([\d.]+)', line)
            if agent_in_box:
                agent_name = agent_in_box.group(1)
                confidence = float(agent_in_box.group(2))
                quality = float(agent_in_box.group(3))

                if 'agents' not in decision:
                    decision['agents'] = []

                # Determine direction from emoji
                if '⬆️' in line:
                    direction = 'Up'
                elif '⬇️' in line:
                    direction = 'Down'
                else:
                    direction = 'Neutral'

                decision['agents'].append({
                    'name': agent_name,
                    'direction': direction,
                    'confidence': confidence,
                    'quality': quality
                })

            # Vote aggregation summary
            if 'VOTE AGGREGATION SUMMARY' in line:
                # Parse the summary box
                for i in range(20):
                    if start_idx + i >= len(lines):
                        break
                    summary_line = lines[start_idx + i]

                    # Direction
                    dir_match = re.search(r'Direction:\s+(\w+)', summary_line)
                    if dir_match:
                        decision['final_direction'] = dir_match.group(1)

                    # Weighted Score
                    score_match = re.search(r'Weighted Score:\s+([\d.]+)', summary_line)
                    if score_match:
                        decision['weighted_score'] = float(score_match.group(1))

                    # Confidence
                    conf_match = re.search(r'Confidence:\s+([\d.]+)%', summary_line)
                    if conf_match:
                        decision['final_confidence'] = float(conf_match.group(1))

                    # Quality
                    qual_match = re.search(r'Quality:\s+([\d.]+)%', summary_line)
                    if qual_match:
                        decision['quality'] = float(qual_match.group(1))

                    # Vote breakdown
                    votes_match = re.search(r'Up:\s+(\d+) \| Down:\s+(\d+) \| Neutral:\s+(\d+)', summary_line)
                    if votes_match:
                        decision['vote_breakdown'] = {
                            'up': int(votes_match.group(1)),
                            'down': int(votes_match.group(2)),
                            'neutral': int(votes_match.group(3))
                        }

                    # Participating agents count
                    part_match = re.search(r'Participating Agents \((\d+)\)', summary_line)
                    if part_match:
                        decision['participating_agents'] = int(part_match.group(1))

                    # Agreement rate
                    agree_match = re.search(r'Agreement Rate:\s+([\d.]+)%', summary_line)
                    if agree_match:
                        decision['agreement_rate'] = float(agree_match.group(1))

                    # Threshold met
                    threshold_match = re.search(r'Threshold:\s+([\d.]+)\s+([✅❌])', summary_line)
                    if threshold_match:
                        decision['threshold'] = float(threshold_match.group(1))
                        decision['threshold_met'] = threshold_match.group(2) == '✅'

            # Final decision
            should_trade = re.search(r'Should Trade:\s+(True|False)', line)
            if should_trade:
                decision['should_trade'] = should_trade.group(1) == 'True'

            # Skip reason
            skip_reason = re.search(r'AGENTS SKIP:\s+(.+)', line)
            if skip_reason:
                decision['skip_reason'] = skip_reason.group(1)

        return decision if decision else None

    def update_from_log(self):
        """Read new log entries and update decision history"""
        try:
            # Use tail to get recent lines efficiently
            result = subprocess.run(
                ['ssh', '-i', os.path.expanduser('~/.ssh/polymarket_vultr'),
                 'root@216.238.85.11', f'tail -500 {LOG_FILE}'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return

            lines = result.stdout.split('\n')

            # Find decision entries
            for i, line in enumerate(lines):
                if 'VOTE AGGREGATION SUMMARY' in line:
                    decision = self.parse_log_entry(lines, i)  # Start at the aggregation box
                    if decision and 'crypto' in decision:
                        crypto = decision['crypto']
                        # Only add if it's newer than our last entry
                        if (not self.decisions[crypto] or
                            decision.get('timestamp', '') > self.decisions[crypto][-1].get('timestamp', '')):
                            self.decisions[crypto].append(decision)

        except Exception as e:
            pass  # Fail silently

    def get_recent_decisions(self, crypto, count=10):
        """Get most recent decisions for a crypto"""
        decisions = list(self.decisions[crypto])
        return decisions[-count:] if decisions else []

    def get_trend_summary(self, crypto):
        """Get trend summary for last 10 decisions"""
        recent = self.get_recent_decisions(crypto, 10)
        if not recent:
            return None

        directions = [d.get('final_direction', 'Neutral') for d in recent]
        confidences = [d.get('final_confidence', 0) for d in recent]

        up_count = directions.count('Up')
        down_count = directions.count('Down')
        neutral_count = directions.count('Neutral')

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            'total': len(recent),
            'up': up_count,
            'down': down_count,
            'neutral': neutral_count,
            'avg_confidence': avg_confidence,
            'trend': 'Bullish' if up_count > down_count else 'Bearish' if down_count > up_count else 'Neutral'
        }


def clear_screen():
    """Clear terminal screen"""
    try:
        os.system('clear' if os.name == 'posix' else 'cls')
    except:
        print('\n' * 50)


def render_decision(decision, crypto):
    """Render a single decision"""
    timestamp = decision.get('timestamp', 'Unknown')
    direction = decision.get('final_direction', 'Unknown')
    confidence = decision.get('final_confidence', 0)
    weighted_score = decision.get('weighted_score', 0)
    should_trade = decision.get('should_trade', False)
    skip_reason = decision.get('skip_reason', '')

    # Direction emoji
    if direction == 'Up':
        dir_emoji = '⬆️ '
        dir_color = '\033[92m'  # Green
    elif direction == 'Down':
        dir_emoji = '⬇️ '
        dir_color = '\033[91m'  # Red
    else:
        dir_emoji = '➡️ '
        dir_color = '\033[93m'  # Yellow

    reset_color = '\033[0m'

    # Trade decision
    trade_emoji = '✅' if should_trade else '⏭️ '

    print(f"  {timestamp} | {crypto} | {dir_emoji}{dir_color}{direction:8}{reset_color} | "
          f"Conf: {confidence:5.1f}% | Score: {weighted_score:.3f} | {trade_emoji}")

    # Show agent votes
    agents = decision.get('agents', [])
    if agents:
        for agent in agents:
            agent_dir = agent['direction']
            agent_conf = agent['confidence']
            agent_qual = agent.get('quality', 0)

            # Agent direction emoji
            if agent_dir == 'Up':
                agent_emoji = '↑'
            elif agent_dir == 'Down':
                agent_emoji = '↓'
            else:
                agent_emoji = '→'

            print(f"    {agent_emoji} {agent['name']:20} @ {agent_conf:4.0%} confidence | {agent_qual:4.0%} quality")

    # Show skip reason if not trading
    if not should_trade and skip_reason:
        print(f"    ⚠️  {skip_reason}")

    print()


def render_dashboard(tracker):
    """Render the agent decision dashboard"""
    clear_screen()

    # Header
    print("=" * 100)
    print(" " * 35 + "🤖 AGENT DECISION TRACKER")
    print("=" * 100)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | 🔄 Refreshing every {REFRESH_INTERVAL}s")
    print()

    # Show recent decisions for each crypto
    for crypto in ['BTC', 'ETH', 'SOL', 'XRP']:
        print(f"{'─' * 100}")
        print(f"💰 {crypto} - RECENT DECISIONS (Last 5)")
        print(f"{'─' * 100}")

        recent = tracker.get_recent_decisions(crypto, 5)

        if recent:
            for decision in recent:
                render_decision(decision, crypto)
        else:
            print("  No recent decisions")
            print()

        # Show trend summary
        trend = tracker.get_trend_summary(crypto)
        if trend:
            trend_emoji = '📈' if trend['trend'] == 'Bullish' else '📉' if trend['trend'] == 'Bearish' else '➡️'
            print(f"  {trend_emoji} Last 10 Decisions: {trend['up']} Up | {trend['down']} Down | "
                  f"{trend['neutral']} Neutral | Avg Conf: {trend['avg_confidence']:.1f}% | "
                  f"Trend: {trend['trend']}")
            print()

    print("=" * 100)
    print("💡 Press Ctrl+C to exit | Tracking agent votes and consensus decisions")
    print("=" * 100)


def main():
    """Main loop"""
    print("Starting agent decision tracker...")
    print("Reading from VPS logs...")
    time.sleep(2)

    tracker = AgentDecisionTracker()

    try:
        while True:
            tracker.update_from_log()
            render_dashboard(tracker)
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        clear_screen()
        print("\n👋 Agent decision tracker stopped. Goodbye!")
        print()


if __name__ == "__main__":
    main()
