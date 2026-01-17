#!/usr/bin/env python3
"""
US-TO-QUICK-001 Track 1 Monitoring Dashboard

Monitors the deployment of cheap entry focus strategy:
- Entry prices (target: avg < $0.15)
- Win rate (target: >= 58%)
- Trade count (target: 4-6 trades in 24h)
- Consensus threshold validation (0.82)

Usage:
    python3 scripts/track1_dashboard.py [--refresh 30] [--remote]

    --refresh N   Refresh every N seconds (default: 30)
    --remote      Fetch logs from VPS via SSH
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class Track1Dashboard:
    """Dashboard for monitoring US-TO-QUICK-001 deployment."""

    # Success criteria
    TARGET_AVG_ENTRY = 0.15      # Target: avg entry < $0.15
    TARGET_WIN_RATE = 0.58       # Target: WR >= 58%
    TARGET_MIN_TRADES = 4        # Target: at least 4 trades in 24h
    TARGET_MAX_TRADES = 10       # Expected: 4-10 trades/day with selective approach
    CONSENSUS_THRESHOLD = 0.82   # Expected threshold

    def __init__(self, log_path: str = "bot.log", remote: bool = False):
        self.log_path = log_path
        self.remote = remote
        self.ssh_cmd = "ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11"
        self.remote_log = "/opt/polymarket-autotrader/bot.log"
        self.remote_state = "/opt/polymarket-autotrader/state/trading_state.json"

        # Deployment timestamp (Jan 17, 2026 01:20 UTC)
        self.deployment_time = datetime(2026, 1, 17, 1, 20, 0, tzinfo=timezone.utc)

    def run_remote_cmd(self, cmd: str, use_shell_escape: bool = True) -> str:
        """Run command on remote VPS."""
        if use_shell_escape:
            # For simple commands, wrap in quotes
            full_cmd = f'{self.ssh_cmd} "{cmd}"'
        else:
            # For heredocs, pass command directly
            full_cmd = f'{self.ssh_cmd} {cmd}'
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            return f"Error: {e}"

    def get_log_content(self, lines: int = 500) -> str:
        """Get log content from local or remote."""
        if self.remote:
            return self.run_remote_cmd(f"tail -{lines} {self.remote_log}")
        else:
            try:
                with open(self.log_path, 'r') as f:
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:])
            except FileNotFoundError:
                return ""

    def get_trading_state(self) -> Dict:
        """Get current trading state."""
        if self.remote:
            output = self.run_remote_cmd(f"cat {self.remote_state}")
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {}
        else:
            state_path = Path(__file__).parent.parent / "state" / "trading_state.json"
            try:
                with open(state_path, 'r') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    def get_config_values(self) -> Dict:
        """Get current config values from VPS or locally."""
        if self.remote:
            # Use a here-doc approach to avoid quoting issues
            cmd = """'cd /opt/polymarket-autotrader && python3 << '"'"'PYEOF'"'"'
import json
import sys
sys.path.insert(0, ".")
from config import agent_config as cfg
print("CONFIG_JSON:" + json.dumps({
    "consensus": cfg.CONSENSUS_THRESHOLD,
    "min_conf": cfg.MIN_CONFIDENCE,
    "max_entry": cfg.MAX_ENTRY,
    "early_max": cfg.EARLY_MAX_ENTRY,
    "late_max": cfg.LATE_MAX_ENTRY,
    "contrarian_max": cfg.SENTIMENT_CONTRARIAN_MAX_ENTRY,
    "mode": cfg.CURRENT_MODE
}))
PYEOF'"""
            output = self.run_remote_cmd(cmd, use_shell_escape=False)
            try:
                # Find the JSON line with our marker
                for line in output.strip().split('\n'):
                    if line.startswith('CONFIG_JSON:'):
                        return json.loads(line.replace('CONFIG_JSON:', ''))
                return {}
            except json.JSONDecodeError:
                return {}
        else:
            # Try to load config locally
            try:
                from config import agent_config as cfg
                return {
                    'consensus': cfg.CONSENSUS_THRESHOLD,
                    'min_conf': cfg.MIN_CONFIDENCE,
                    'max_entry': cfg.MAX_ENTRY,
                    'early_max': cfg.EARLY_MAX_ENTRY,
                    'late_max': cfg.LATE_MAX_ENTRY,
                    'contrarian_max': cfg.SENTIMENT_CONTRARIAN_MAX_ENTRY,
                    'mode': cfg.CURRENT_MODE
                }
            except ImportError:
                return {}

    def parse_trades_since_deployment(self, log_content: str) -> List[Dict]:
        """Parse trades from log since deployment."""
        trades = []

        # Pattern for ORDER PLACED with entry price
        # Example: ORDER PLACED: matched ... entry $0.12
        order_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*ORDER PLACED.*?(\w+).*?entry.*?\$?([\d.]+)'

        for match in re.finditer(order_pattern, log_content, re.IGNORECASE):
            timestamp_str, status, entry_price = match.groups()
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                if timestamp >= self.deployment_time:
                    trades.append({
                        'timestamp': timestamp,
                        'status': status,
                        'entry_price': float(entry_price)
                    })
            except (ValueError, TypeError):
                continue

        return trades

    def parse_wins_losses_since_deployment(self, log_content: str) -> Tuple[int, int]:
        """Count wins and losses since deployment."""
        wins = 0
        losses = 0

        # Pattern for WIN/LOSS outcomes
        win_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\bWIN\b'
        loss_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\bLOSS\b'

        for match in re.finditer(win_pattern, log_content):
            try:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                if timestamp >= self.deployment_time:
                    wins += 1
            except ValueError:
                continue

        for match in re.finditer(loss_pattern, log_content):
            try:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                if timestamp >= self.deployment_time:
                    losses += 1
            except ValueError:
                continue

        return wins, losses

    def parse_skipped_signals(self, log_content: str) -> Dict:
        """Parse skipped signals and reasons."""
        skipped = {
            'consensus_too_weak': 0,
            'entry_too_high': 0,
            'other': 0,
            'recent_scores': []
        }

        # Count consensus rejections
        consensus_pattern = r'Consensus too weak to trade \(([\d.]+) < ([\d.]+)\)'
        for match in re.finditer(consensus_pattern, log_content):
            score, threshold = match.groups()
            skipped['consensus_too_weak'] += 1
            if len(skipped['recent_scores']) < 20:
                skipped['recent_scores'].append(float(score))

        # Count entry price rejections
        entry_pattern = r'entry.*too high|price.*exceeded|skip.*entry'
        skipped['entry_too_high'] = len(re.findall(entry_pattern, log_content, re.IGNORECASE))

        return skipped

    def calculate_metrics(self, trades: List[Dict], wins: int, losses: int) -> Dict:
        """Calculate key performance metrics."""
        total_trades = len(trades)
        total_resolved = wins + losses

        metrics = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'total_resolved': total_resolved,
            'win_rate': wins / total_resolved if total_resolved > 0 else 0,
            'avg_entry': 0,
            'min_entry': 0,
            'max_entry': 0,
            'entry_prices': [],
            'hours_since_deployment': 0
        }

        if trades:
            entry_prices = [t['entry_price'] for t in trades]
            metrics['entry_prices'] = entry_prices
            metrics['avg_entry'] = sum(entry_prices) / len(entry_prices)
            metrics['min_entry'] = min(entry_prices)
            metrics['max_entry'] = max(entry_prices)

        # Calculate hours since deployment
        now = datetime.now(timezone.utc)
        delta = now - self.deployment_time
        metrics['hours_since_deployment'] = delta.total_seconds() / 3600

        return metrics

    def check_success_criteria(self, metrics: Dict) -> Dict[str, Tuple[bool, str]]:
        """Check if success criteria are met."""
        criteria = {}

        # Avg entry < $0.15
        if metrics['total_trades'] > 0:
            passed = metrics['avg_entry'] < self.TARGET_AVG_ENTRY
            criteria['avg_entry'] = (
                passed,
                f"${metrics['avg_entry']:.3f} {'<' if passed else '>='} ${self.TARGET_AVG_ENTRY}"
            )
        else:
            criteria['avg_entry'] = (None, "No trades yet")

        # Win rate >= 58%
        if metrics['total_resolved'] > 0:
            passed = metrics['win_rate'] >= self.TARGET_WIN_RATE
            criteria['win_rate'] = (
                passed,
                f"{metrics['win_rate']:.1%} {'>=' if passed else '<'} {self.TARGET_WIN_RATE:.0%}"
            )
        else:
            criteria['win_rate'] = (None, "No resolved trades yet")

        # At least 4 trades in 24h
        hours = metrics['hours_since_deployment']
        if hours >= 24:
            passed = metrics['total_trades'] >= self.TARGET_MIN_TRADES
            criteria['trade_count'] = (
                passed,
                f"{metrics['total_trades']} trades {'>=' if passed else '<'} {self.TARGET_MIN_TRADES} (in {hours:.1f}h)"
            )
        else:
            # Pro-rate expectation
            expected_min = (hours / 24) * self.TARGET_MIN_TRADES
            on_track = metrics['total_trades'] >= expected_min * 0.5  # 50% buffer for early
            criteria['trade_count'] = (
                on_track,
                f"{metrics['total_trades']} trades ({hours:.1f}h elapsed, need {self.TARGET_MIN_TRADES} in 24h)"
            )

        return criteria

    def render_dashboard(self):
        """Render the dashboard to terminal."""
        # Clear screen
        print("\033[2J\033[H", end="")

        # Get data
        log_content = self.get_log_content(2000)
        state = self.get_trading_state()
        config = self.get_config_values()

        trades = self.parse_trades_since_deployment(log_content)
        wins, losses = self.parse_wins_losses_since_deployment(log_content)
        skipped = self.parse_skipped_signals(log_content)
        metrics = self.calculate_metrics(trades, wins, losses)
        criteria = self.check_success_criteria(metrics)

        # Header
        print("=" * 70)
        print("        🎯 US-TO-QUICK-001 TRACK 1 MONITORING DASHBOARD 🎯")
        print("=" * 70)
        print(f"  Deployment: {self.deployment_time.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  Elapsed: {metrics['hours_since_deployment']:.1f} hours / 24 hours")
        print(f"  Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 70)

        # Config verification
        print("\n📋 CONFIGURATION")
        print("-" * 70)
        if config:
            mode_ok = config.get('mode') == 'conservative'
            consensus_ok = config.get('consensus') == 0.82
            entry_ok = config.get('max_entry', 1) <= 0.15

            print(f"  Mode: {config.get('mode', 'unknown'):<15} {'✅' if mode_ok else '❌'}")
            print(f"  Consensus Threshold: {config.get('consensus', 0):<8} {'✅' if consensus_ok else '❌'} (target: 0.82)")
            print(f"  Max Entry: ${config.get('max_entry', 0):<13.2f} {'✅' if entry_ok else '❌'} (target: ≤$0.15)")
            print(f"  Early Max: ${config.get('early_max', 0):.2f}")
            print(f"  Contrarian Max: ${config.get('contrarian_max', 0):.2f}")
        else:
            print("  ⚠️  Could not fetch config (run with --remote)")

        # Balance & State
        print("\n💰 ACCOUNT STATUS")
        print("-" * 70)
        if state:
            balance = state.get('current_balance', 0)
            peak = state.get('peak_balance', 0)
            mode = state.get('mode', 'unknown')
            drawdown = ((peak - balance) / peak * 100) if peak > 0 else 0

            print(f"  Balance: ${balance:.2f}")
            print(f"  Peak: ${peak:.2f}")
            print(f"  Drawdown: {drawdown:.1f}% {'⚠️' if drawdown > 25 else '✅'}")
            print(f"  Mode: {mode}")
        else:
            print("  ⚠️  Could not fetch state")

        # Success Criteria
        print("\n🎯 SUCCESS CRITERIA (24-hour validation)")
        print("-" * 70)
        for name, (passed, detail) in criteria.items():
            if passed is None:
                status = "⏳"
            elif passed:
                status = "✅"
            else:
                status = "❌"
            print(f"  {status} {name.replace('_', ' ').title()}: {detail}")

        # Trade Metrics
        print("\n📊 TRADE METRICS (since deployment)")
        print("-" * 70)
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Resolved: {metrics['total_resolved']} ({metrics['wins']}W / {metrics['losses']}L)")

        if metrics['total_resolved'] > 0:
            wr_color = '\033[92m' if metrics['win_rate'] >= 0.58 else '\033[91m'
            print(f"  Win Rate: {wr_color}{metrics['win_rate']:.1%}\033[0m")

        if metrics['entry_prices']:
            avg_color = '\033[92m' if metrics['avg_entry'] < 0.15 else '\033[91m'
            print(f"\n  Entry Prices:")
            print(f"    Average: {avg_color}${metrics['avg_entry']:.3f}\033[0m (target: <$0.15)")
            print(f"    Min: ${metrics['min_entry']:.3f}")
            print(f"    Max: ${metrics['max_entry']:.3f}")

            # Entry price distribution
            if len(metrics['entry_prices']) >= 3:
                print(f"\n  Recent entries: ", end="")
                for price in metrics['entry_prices'][-5:]:
                    color = '\033[92m' if price < 0.15 else '\033[93m' if price < 0.20 else '\033[91m'
                    print(f"{color}${price:.2f}\033[0m ", end="")
                print()

        # Signal Analysis
        print("\n📡 SIGNAL ANALYSIS (recent)")
        print("-" * 70)
        print(f"  Skipped (consensus too weak): {skipped['consensus_too_weak']}")
        print(f"  Skipped (entry too high): {skipped['entry_too_high']}")

        if skipped['recent_scores']:
            avg_score = sum(skipped['recent_scores']) / len(skipped['recent_scores'])
            max_score = max(skipped['recent_scores'])
            print(f"\n  Recent consensus scores (rejected):")
            print(f"    Average: {avg_score:.3f}")
            print(f"    Highest: {max_score:.3f} (need ≥0.82)")

            # Score distribution
            below_50 = sum(1 for s in skipped['recent_scores'] if s < 0.50)
            below_70 = sum(1 for s in skipped['recent_scores'] if 0.50 <= s < 0.70)
            below_82 = sum(1 for s in skipped['recent_scores'] if 0.70 <= s < 0.82)
            print(f"    Distribution: <0.50: {below_50}, 0.50-0.70: {below_70}, 0.70-0.82: {below_82}")

        # Progress bar
        print("\n⏱️  VALIDATION PROGRESS")
        print("-" * 70)
        progress = min(metrics['hours_since_deployment'] / 24, 1.0)
        bar_width = 50
        filled = int(bar_width * progress)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"  [{bar}] {progress:.0%}")

        remaining = max(0, 24 - metrics['hours_since_deployment'])
        print(f"  {remaining:.1f} hours remaining")

        # Overall status
        print("\n" + "=" * 70)
        all_passed = all(v[0] for v in criteria.values() if v[0] is not None)
        any_failed = any(v[0] is False for v in criteria.values())

        if metrics['hours_since_deployment'] >= 24:
            if all_passed:
                print("  🎉 TRACK 1 VALIDATION: PASSED - Ready for Track 2!")
            elif any_failed:
                print("  ❌ TRACK 1 VALIDATION: FAILED - Review needed")
            else:
                print("  ⏳ TRACK 1 VALIDATION: INCOMPLETE - Need more data")
        else:
            if any_failed:
                print("  ⚠️  STATUS: Some criteria failing - monitoring...")
            else:
                print("  ✅ STATUS: On track - monitoring continues...")
        print("=" * 70)

        # Footer
        print(f"\n  Press Ctrl+C to exit | Refreshing every {args.refresh}s")

    def run(self, refresh_interval: int = 30):
        """Run the dashboard with auto-refresh."""
        try:
            while True:
                self.render_dashboard()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")


def main():
    global args
    parser = argparse.ArgumentParser(description="US-TO-QUICK-001 Track 1 Monitoring Dashboard")
    parser.add_argument('--refresh', type=int, default=30, help='Refresh interval in seconds')
    parser.add_argument('--remote', action='store_true', help='Fetch logs from VPS via SSH')
    parser.add_argument('--once', action='store_true', help='Run once and exit (no refresh)')
    args = parser.parse_args()

    dashboard = Track1Dashboard(remote=args.remote)

    if args.once:
        dashboard.render_dashboard()
    else:
        dashboard.run(refresh_interval=args.refresh)


if __name__ == '__main__':
    main()
