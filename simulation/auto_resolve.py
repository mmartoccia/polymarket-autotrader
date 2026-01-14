#!/usr/bin/env python3
"""
Auto-Resolve Shadow Positions

Background script that runs alongside the bot to automatically resolve
shadow trading positions using real exchange data.

Runs every 60 seconds, checks for positions older than 17 minutes,
fetches real outcomes from Binance/Kraken, and logs results to database.
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from simulation.strategy_configs import STRATEGY_LIBRARY
from simulation.orchestrator import SimulationOrchestrator
from simulation.outcome_fetcher import OutcomeFetcher
from config import agent_config

def main():
    print("="*60)
    print("Shadow Trading Auto-Resolver")
    print("="*60)
    print()
    print("This script runs alongside the bot to automatically")
    print("resolve shadow trading positions using real market data.")
    print()
    print("Press Ctrl+C to stop")
    print("="*60)
    print()

    fetcher = OutcomeFetcher()

    while True:
        try:
            # Load orchestrator (this will restore positions from database)
            strategies = [
                STRATEGY_LIBRARY[name]
                for name in agent_config.SHADOW_STRATEGIES
                if name in STRATEGY_LIBRARY
            ]

            orch = SimulationOrchestrator(
                strategies,
                db_path=agent_config.SHADOW_DB_PATH,
                starting_balance=agent_config.SHADOW_STARTING_BALANCE
            )

            # Check all positions
            current_time = int(time.time())
            resolved_count = 0

            for name, strat in orch.strategies.items():
                for position_key, pos in list(strat.positions.items()):
                    crypto, epoch = position_key
                    age_sec = current_time - epoch

                    # Resolve if older than 17 minutes (1020 seconds)
                    if age_sec > 1020:
                        try:
                            outcome_result = fetcher.get_epoch_outcome(crypto, epoch)

                            if outcome_result:
                                orch.on_epoch_resolution(crypto, epoch, outcome_result.direction)
                                result_emoji = "✅" if pos.direction == outcome_result.direction else "❌"
                                print(f"{result_emoji} [{name}] {crypto.upper()} epoch {epoch}: {outcome_result.direction} "
                                      f"(${outcome_result.start_price:.0f} -> ${outcome_result.end_price:.0f}, {outcome_result.change_pct:+.2f}%)")
                                resolved_count += 1
                            else:
                                print(f"⚠️  [{name}] {crypto.upper()} epoch {epoch}: Could not fetch outcome (data unavailable)")

                        except Exception as e:
                            print(f"❌ Error resolving {name} {crypto} epoch {epoch}: {e}")

            if resolved_count > 0:
                print(f"\n✅ Resolved {resolved_count} positions this cycle")
            else:
                print("✓ No positions ready to resolve")

            orch.close()

        except Exception as e:
            print(f"❌ Error in resolution cycle: {e}")
            import traceback
            traceback.print_exc()

        # Wait 60 seconds before next check
        print(f"\nWaiting 60 seconds... (next check at {time.strftime('%H:%M:%S', time.localtime(time.time() + 60))})")
        time.sleep(60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("Auto-resolver stopped")
        print("="*60)
