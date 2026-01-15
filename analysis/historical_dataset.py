#!/usr/bin/env python3
"""
Historical Epoch Dataset Builder

Stores daily epoch outcomes in a SQLite database for long-term pattern analysis.
Runs as a cron job to continuously collect data.
"""

import sys
from pathlib import Path
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict

sys.path.append(str(Path(__file__).parent.parent))

from simulation.outcome_fetcher import OutcomeFetcher


class HistoricalDataset:
    """Manages historical epoch outcome storage."""

    def __init__(self, db_path: str = 'analysis/epoch_history.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create database schema."""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS epoch_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crypto TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                date TEXT NOT NULL,
                hour INTEGER NOT NULL,
                direction TEXT NOT NULL,
                start_price REAL NOT NULL,
                end_price REAL NOT NULL,
                change_pct REAL NOT NULL,
                change_abs REAL NOT NULL,
                timestamp REAL NOT NULL,
                UNIQUE(crypto, epoch)
            )
        ''')

        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_crypto_date
            ON epoch_outcomes(crypto, date)
        ''')

        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_crypto_epoch
            ON epoch_outcomes(crypto, epoch)
        ''')

        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_date
            ON epoch_outcomes(date)
        ''')

        self.conn.commit()

    def store_outcome(self, crypto: str, epoch: int, direction: str,
                     start_price: float, end_price: float,
                     change_pct: float, change_abs: float):
        """Store a single epoch outcome."""
        dt = datetime.fromtimestamp(epoch)
        date_str = dt.strftime('%Y-%m-%d')
        hour = dt.hour

        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO epoch_outcomes
                (crypto, epoch, date, hour, direction, start_price, end_price,
                 change_pct, change_abs, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (crypto, epoch, date_str, hour, direction, start_price,
                  end_price, change_pct, change_abs, time.time()))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Already exists
            return False

    def get_daily_stats(self, crypto: str, date: str) -> Dict:
        """Get up/down stats for a specific day."""
        rows = self.conn.execute('''
            SELECT direction, COUNT(*) as count
            FROM epoch_outcomes
            WHERE crypto = ? AND date = ?
            GROUP BY direction
        ''', (crypto, date)).fetchall()

        stats = {'ups': 0, 'downs': 0, 'total': 0}
        for row in rows:
            if row['direction'] == 'Up':
                stats['ups'] = row['count']
            else:
                stats['downs'] = row['count']
        stats['total'] = stats['ups'] + stats['downs']
        stats['up_pct'] = (stats['ups'] / stats['total'] * 100) if stats['total'] > 0 else 0

        return stats

    def get_hourly_patterns(self, crypto: str, days: int = 7) -> Dict[int, Dict]:
        """Get up/down patterns by hour of day."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        rows = self.conn.execute('''
            SELECT hour, direction, COUNT(*) as count
            FROM epoch_outcomes
            WHERE crypto = ? AND date >= ?
            GROUP BY hour, direction
            ORDER BY hour
        ''', (crypto, cutoff_date)).fetchall()

        hourly = {}
        for row in rows:
            hour = row['hour']
            if hour not in hourly:
                hourly[hour] = {'ups': 0, 'downs': 0, 'total': 0}

            if row['direction'] == 'Up':
                hourly[hour]['ups'] = row['count']
            else:
                hourly[hour]['downs'] = row['count']
            hourly[hour]['total'] = hourly[hour]['ups'] + hourly[hour]['downs']

        return hourly

    def get_date_range(self, crypto: str) -> tuple:
        """Get earliest and latest dates in dataset."""
        row = self.conn.execute('''
            SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(*) as total
            FROM epoch_outcomes
            WHERE crypto = ?
        ''', (crypto,)).fetchone()

        return (row['earliest'], row['latest'], row['total'])

    def backfill_history(self, crypto: str, days: int = 7, verbose: bool = True):
        """Backfill historical data for a crypto."""
        fetcher = OutcomeFetcher()

        # Calculate epoch range
        current_time = int(time.time())
        current_epoch = (current_time // 900) * 900
        start_epoch = current_epoch - (96 * 900 * days)  # 96 epochs per day

        if verbose:
            print(f"Backfilling {crypto.upper()} history:")
            print(f"  From: {datetime.fromtimestamp(start_epoch).strftime('%Y-%m-%d %H:%M')}")
            print(f"  To:   {datetime.fromtimestamp(current_epoch).strftime('%Y-%m-%d %H:%M')}")
            print(f"  Expected epochs: {(current_epoch - start_epoch) // 900}")
            print()

        epoch = start_epoch
        stored = 0
        skipped = 0
        errors = 0

        while epoch <= current_epoch:
            try:
                result = fetcher.get_epoch_outcome(crypto, epoch)

                if result:
                    success = self.store_outcome(
                        crypto=crypto,
                        epoch=epoch,
                        direction=result.direction,
                        start_price=result.start_price,
                        end_price=result.end_price,
                        change_pct=result.change_pct,
                        change_abs=result.end_price - result.start_price
                    )

                    if success:
                        stored += 1
                    else:
                        skipped += 1

                    if verbose and (stored + skipped) % 20 == 0:
                        print(f"  Progress: {stored} stored, {skipped} skipped, {errors} errors", end='\r')
                else:
                    errors += 1

            except Exception as e:
                errors += 1
                if errors > 50:
                    if verbose:
                        print(f"\n  ⚠️  Too many errors ({errors}), stopping backfill")
                    break

            epoch += 900

        if verbose:
            print(f"\n  ✅ Complete: {stored} new outcomes stored, {skipped} already existed")

        return stored, skipped, errors

    def close(self):
        """Close database connection."""
        self.conn.close()


def update_all_cryptos(cryptos: List[str] = ['btc', 'eth', 'sol', 'xrp'],
                       lookback_hours: int = 24):
    """
    Update historical dataset for all cryptos.
    Designed to run as a cron job (every hour or every 15 minutes).
    """
    print("="*80)
    print("HISTORICAL DATASET UPDATE")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cryptos: {', '.join([c.upper() for c in cryptos])}")
    print(f"Lookback: {lookback_hours} hours")
    print()

    dataset = HistoricalDataset()

    for crypto in cryptos:
        print(f"Updating {crypto.upper()}...")
        days = lookback_hours / 24
        stored, skipped, errors = dataset.backfill_history(crypto, days=days, verbose=False)

        # Get current dataset info
        earliest, latest, total = dataset.get_date_range(crypto)

        print(f"  {crypto.upper()}: +{stored} new | {total} total | {earliest} to {latest}")

    dataset.close()
    print()
    print("="*80)
    print("Update complete!")
    print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Manage historical epoch dataset')
    parser.add_argument('--backfill', type=int, help='Backfill N days of history')
    parser.add_argument('--crypto', type=str, help='Single crypto (btc, eth, sol, xrp)')
    parser.add_argument('--all', action='store_true', help='All cryptos')
    parser.add_argument('--update', action='store_true', help='Update recent data (for cron)')
    parser.add_argument('--stats', action='store_true', help='Show dataset statistics')

    args = parser.parse_args()

    if args.update:
        # Update mode (for cron job)
        update_all_cryptos(lookback_hours=24)

    elif args.backfill:
        # Backfill mode
        dataset = HistoricalDataset()

        if args.all:
            cryptos = ['btc', 'eth', 'sol', 'xrp']
        elif args.crypto:
            cryptos = [args.crypto.lower()]
        else:
            print("Specify --crypto <name> or --all")
            return

        for crypto in cryptos:
            print(f"\nBackfilling {crypto.upper()}...")
            dataset.backfill_history(crypto, days=args.backfill)

        dataset.close()

    elif args.stats:
        # Show statistics
        dataset = HistoricalDataset()

        print("="*80)
        print("HISTORICAL DATASET STATISTICS")
        print("="*80)
        print()

        for crypto in ['btc', 'eth', 'sol', 'xrp']:
            earliest, latest, total = dataset.get_date_range(crypto)

            if total > 0:
                print(f"{crypto.upper()}:")
                print(f"  Total epochs: {total}")
                print(f"  Date range: {earliest} to {latest}")
                print(f"  Coverage: {total / 96:.1f} days")
                print()
            else:
                print(f"{crypto.upper()}: No data")
                print()

        dataset.close()

    else:
        print("Usage:")
        print("  --backfill N --crypto btc    # Backfill N days for BTC")
        print("  --backfill N --all           # Backfill N days for all cryptos")
        print("  --update                     # Update recent data (for cron)")
        print("  --stats                      # Show dataset statistics")


if __name__ == '__main__':
    main()
