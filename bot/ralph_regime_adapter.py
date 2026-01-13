#!/usr/bin/env python3
"""
Ralph Wiggum Loop for Market Regime Adaptation
Continuously monitors market conditions and adapts bot parameters
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime
from market_regime_detector import MarketRegimeDetector, get_current_prices

OVERRIDE_FILE = "/opt/polymarket-autotrader/state/ralph_overrides.json"
STATE_FILE = "/opt/polymarket-autotrader/state/ralph_regime_state.json"
LOG_FILE = "/opt/polymarket-autotrader/ralph_regime.log"

class RalphRegimeAdapter:
    """Ralph loop for adaptive parameter tuning based on market regime."""

    def __init__(self):
        self.detector = MarketRegimeDetector(lookback_windows=20)
        self.current_regime = None
        self.current_params = None
        self.iteration = 0
        self.load_state()

    def load_state(self):
        """Load previous state if exists."""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                self.iteration = state.get('iteration', 0)
                self.current_regime = state.get('regime')
                self.current_params = state.get('params')

    def save_state(self):
        """Save current state."""
        state = {
            'iteration': self.iteration,
            'regime': self.current_regime,
            'params': self.current_params,
            'last_update': datetime.now().isoformat()
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)

    def log(self, message):
        """Log to file and console."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)

        with open(LOG_FILE, 'a') as f:
            f.write(log_msg + '\n')

    def collect_price_data(self, samples=20):
        """Collect price data for regime detection."""
        self.log(f"Collecting {samples} price samples...")

        for i in range(samples):
            prices = get_current_prices()

            if prices:
                for crypto, price in prices.items():
                    self.detector.update_prices(crypto, price)

                if i % 5 == 0:
                    self.log(f"  Sample {i+1}/{samples}: BTC=${prices.get('btc', 0):,.2f}")

            time.sleep(5)  # 5 seconds between samples

    def detect_regime_change(self) -> tuple:
        """Detect current regime and check if it changed."""
        regime = self.detector.detect_regime()
        new_regime = regime['regime']
        changed = new_regime != self.current_regime

        return regime, changed

    def apply_parameters(self, params: dict):
        """Apply parameters by writing override file (bot will reload on restart)."""
        self.log("Writing parameter overrides...")

        # Write overrides to JSON file
        with open(OVERRIDE_FILE, 'w') as f:
            json.dump(params, f, indent=2)

        self.log(f"  Written {len(params)} parameters to override file")

    def restart_bot(self):
        """Restart the trading bot service."""
        self.log("Restarting bot with new parameters...")

        result = subprocess.run(
            ["systemctl", "restart", "polymarket-bot"],
            capture_output=True
        )

        if result.returncode == 0:
            self.log("  ✅ Bot restarted successfully")
        else:
            self.log(f"  ⚠️  Restart failed: {result.stderr.decode()}")

        time.sleep(5)  # Give bot time to start

    def check_performance(self) -> dict:
        """Check bot performance metrics."""
        try:
            with open("/opt/polymarket-autotrader/state/trading_state.json", 'r') as f:
                state = json.load(f)

            return {
                'balance': state.get('current_balance', 0),
                'daily_pnl': state.get('daily_pnl', 0),
                'mode': state.get('mode', 'unknown'),
                'trades': state.get('total_trades', 0)
            }
        except:
            return {}

    def run_iteration(self):
        """Run one Ralph iteration."""
        self.iteration += 1

        self.log("=" * 60)
        self.log(f"RALPH REGIME ADAPTATION - ITERATION {self.iteration}")
        self.log("=" * 60)

        # 1. Collect fresh price data
        self.collect_price_data(samples=15)

        # 2. Detect regime
        regime, changed = self.detect_regime_change()

        self.log(f"\nCurrent Regime: {regime['regime']}")
        self.log(f"Volatility: {regime['volatility']:.4f}")
        self.log(f"Confidence: {regime['confidence']:.1%}")

        # 3. Show crypto details
        self.log("\nCrypto Analysis:")
        for crypto, details in regime['crypto_details'].items():
            self.log(f"  {crypto.upper()}: {details['trend']} "
                    f"(vol: {details['volatility']:.4f})")

        # 4. Check if regime changed
        if changed:
            self.log(f"\n🔄 REGIME CHANGE DETECTED!")
            self.log(f"   {self.current_regime} → {regime['regime']}")

            # Get new parameters
            params = self.detector.recommend_parameters(regime)

            self.log(f"\nNew Strategy: {params['strategy_focus']}")
            self.log("New Parameters:")
            for key, value in params.items():
                if key != 'strategy_focus':
                    old_val = self.current_params.get(key, 'N/A') if self.current_params else 'N/A'
                    self.log(f"  {key}: {old_val} → {value}")

            # Apply and restart
            self.apply_parameters(params)
            self.restart_bot()

            self.current_regime = regime['regime']
            self.current_params = params

        else:
            self.log(f"\n✓ Regime unchanged: {regime['regime']}")
            self.log("  No parameter adjustments needed")

        # 5. Check performance
        perf = self.check_performance()
        if perf:
            self.log(f"\nBot Performance:")
            self.log(f"  Balance: ${perf['balance']:.2f}")
            self.log(f"  Daily P&L: ${perf['daily_pnl']:+.2f}")
            self.log(f"  Mode: {perf['mode']}")
            self.log(f"  Trades: {perf['trades']}")

        # 6. Save state
        self.save_state()

        self.log("\nIteration complete. Waiting 5 minutes before next check...")
        self.log("=" * 60)

    def run(self):
        """Main Ralph loop."""
        self.log("🔄 Ralph Regime Adapter Started")
        self.log("Monitoring market conditions and adapting parameters...")
        self.log("")

        while True:
            try:
                self.run_iteration()
                time.sleep(300)  # 5 minutes between iterations

            except KeyboardInterrupt:
                self.log("\n⏹️  Ralph loop stopped by user")
                break
            except Exception as e:
                self.log(f"❌ Error in iteration: {e}")
                time.sleep(60)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         RALPH WIGGUM - REGIME ADAPTATION LOOP                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Continuously monitors market conditions:                    ║
║  • Bull, Bear, Volatile, Sideways                           ║
║                                                              ║
║  Automatically adapts trading parameters:                    ║
║  • Signal strength thresholds                               ║
║  • Contrarian entry limits                                  ║
║  • Strategy focus (momentum vs mean reversion)              ║
║                                                              ║
║  The bot stays optimal in changing markets!                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    adapter = RalphRegimeAdapter()
    adapter.run()