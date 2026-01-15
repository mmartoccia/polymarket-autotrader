#!/usr/bin/env python3
"""
Historical Data Miner

Mines historical 15-minute epoch outcomes from exchange APIs (Binance, Kraken).
Can backfill weeks/months of data quickly instead of waiting for real-time collection.

Uses OHLC (candlestick) data from exchanges to determine if each 15-minute
period was Up (close > open) or Down (close < open).
"""

import sys
from pathlib import Path
import time
import requests
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

sys.path.append(str(Path(__file__).parent.parent))

from analysis.historical_dataset import HistoricalDataset


class ExchangeDataMiner:
    """Mines historical OHLC data from exchanges."""

    BINANCE_SYMBOLS = {
        'btc': 'BTCUSDT',
        'eth': 'ETHUSDT',
        'sol': 'SOLUSDT',
        'xrp': 'XRPUSDT'
    }

    KRAKEN_SYMBOLS = {
        'btc': 'XBTUSD',
        'eth': 'ETHUSD',
        'sol': 'SOLUSD',
        'xrp': 'XRPUSD'
    }

    def get_binance_klines(self, symbol: str, start_time: int, end_time: int) -> List[dict]:
        """
        Get historical klines (candlesticks) from Binance.

        Args:
            symbol: Binance symbol (e.g., BTCUSDT)
            start_time: Start timestamp (milliseconds)
            end_time: End timestamp (milliseconds)

        Returns:
            List of kline dicts with open, close, high, low, volume
        """
        url = 'https://api.binance.com/api/v3/klines'

        all_klines = []
        current_start = start_time

        # Binance limits to 1000 candles per request
        # 15-min candles: 1000 candles = ~10 days
        while current_start < end_time:
            params = {
                'symbol': symbol,
                'interval': '15m',
                'startTime': current_start,
                'endTime': min(current_start + (1000 * 15 * 60 * 1000), end_time),
                'limit': 1000
            }

            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if not data:
                    break

                # Parse klines
                for kline in data:
                    all_klines.append({
                        'timestamp': kline[0] // 1000,  # Convert to seconds
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })

                # Move to next batch
                current_start = data[-1][0] + (15 * 60 * 1000)  # Last timestamp + 15 min

                # Rate limiting
                time.sleep(0.1)

            except Exception as e:
                print(f"  ⚠️  Binance API error: {e}")
                break

        return all_klines

    def get_kraken_ohlc(self, symbol: str, start_time: int) -> List[dict]:
        """
        Get historical OHLC from Kraken.

        Args:
            symbol: Kraken pair (e.g., XBTUSD)
            start_time: Start timestamp (seconds)

        Returns:
            List of OHLC dicts
        """
        url = 'https://api.kraken.com/0/public/OHLC'

        all_candles = []
        current_start = start_time

        # Kraken returns up to 720 candles
        for _ in range(100):  # Safety limit
            params = {
                'pair': symbol,
                'interval': 15,  # 15 minutes
                'since': current_start
            }

            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if data.get('error'):
                    print(f"  ⚠️  Kraken API error: {data['error']}")
                    break

                result = data.get('result', {})
                pair_key = list(result.keys())[0] if result else None

                if not pair_key or pair_key == 'last':
                    break

                candles = result[pair_key]

                for candle in candles:
                    all_candles.append({
                        'timestamp': int(candle[0]),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[6])
                    })

                # Check if we got all data
                last_timestamp = result.get('last', 0)
                if last_timestamp == current_start or len(candles) < 720:
                    break

                current_start = last_timestamp

                # Rate limiting
                time.sleep(1)

            except Exception as e:
                print(f"  ⚠️  Kraken API error: {e}")
                break

        return all_candles

    def mine_historical_data(self, crypto: str, days: int, exchange: str = 'binance') -> List[Tuple]:
        """
        Mine historical epoch outcomes for a crypto.

        Returns list of (epoch, direction, open, close, change_pct) tuples.
        """
        end_time = int(time.time())
        start_time = end_time - (days * 24 * 3600)

        print(f"\nMining {crypto.upper()} from {exchange.upper()}:")
        print(f"  Period: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d')}")
        print(f"  Expected epochs: {days * 96}")

        if exchange == 'binance':
            symbol = self.BINANCE_SYMBOLS.get(crypto)
            if not symbol:
                print(f"  ⚠️  {crypto} not supported on Binance")
                return []

            # Binance uses milliseconds
            klines = self.get_binance_klines(symbol, start_time * 1000, end_time * 1000)

        elif exchange == 'kraken':
            symbol = self.KRAKEN_SYMBOLS.get(crypto)
            if not symbol:
                print(f"  ⚠️  {crypto} not supported on Kraken")
                return []

            klines = self.get_kraken_ohlc(symbol, start_time)

        else:
            print(f"  ⚠️  Unknown exchange: {exchange}")
            return []

        print(f"  Retrieved {len(klines)} candles")

        # Convert to epoch outcomes
        outcomes = []
        for kline in klines:
            epoch = (kline['timestamp'] // 900) * 900  # Round to 15-min epoch
            direction = 'Up' if kline['close'] >= kline['open'] else 'Down'
            change_pct = ((kline['close'] - kline['open']) / kline['open']) * 100
            change_abs = kline['close'] - kline['open']

            outcomes.append((
                epoch,
                direction,
                kline['open'],
                kline['close'],
                change_pct,
                change_abs
            ))

        return outcomes


def mine_and_store(cryptos: List[str], days: int, exchange: str = 'binance'):
    """
    Mine historical data for multiple cryptos and store in dataset.

    Args:
        cryptos: List of crypto symbols (btc, eth, sol, xrp)
        days: Number of days to mine
        exchange: Exchange to use (binance or kraken)
    """
    print("="*100)
    print(f"HISTORICAL DATA MINING - {exchange.upper()}")
    print("="*100)
    print(f"Mining {days} days of data for {len(cryptos)} cryptos")
    print()

    miner = ExchangeDataMiner()
    dataset = HistoricalDataset()

    total_stored = 0

    for crypto in cryptos:
        outcomes = miner.mine_historical_data(crypto, days, exchange)

        if not outcomes:
            continue

        stored = 0
        skipped = 0

        for epoch, direction, open_price, close_price, change_pct, change_abs in outcomes:
            success = dataset.store_outcome(
                crypto=crypto,
                epoch=epoch,
                direction=direction,
                start_price=open_price,
                end_price=close_price,
                change_pct=change_pct,
                change_abs=change_abs
            )

            if success:
                stored += 1
            else:
                skipped += 1

            if (stored + skipped) % 500 == 0:
                print(f"  Progress: {stored} stored, {skipped} skipped", end='\r')

        print(f"  ✅ {crypto.upper()}: {stored} new epochs stored ({skipped} already existed)")
        total_stored += stored

    dataset.close()

    print()
    print("="*100)
    print(f"✅ MINING COMPLETE: {total_stored} total epochs stored")
    print()

    # Show updated stats
    print("Updated dataset statistics:")
    print("-"*100)
    dataset = HistoricalDataset()
    for crypto in cryptos:
        earliest, latest, total = dataset.get_date_range(crypto)
        if total > 0:
            print(f"  {crypto.upper()}: {total} epochs ({earliest} to {latest}, {total/96:.1f} days)")
    dataset.close()
    print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Mine historical epoch data from exchanges')
    parser.add_argument('--days', type=int, required=True, help='Number of days to mine')
    parser.add_argument('--crypto', type=str, help='Single crypto (btc, eth, sol, xrp)')
    parser.add_argument('--all', action='store_true', help='All cryptos')
    parser.add_argument('--exchange', type=str, default='binance', choices=['binance', 'kraken'],
                       help='Exchange to use (default: binance)')

    args = parser.parse_args()

    if args.all:
        cryptos = ['btc', 'eth', 'sol', 'xrp']
    elif args.crypto:
        cryptos = [args.crypto.lower()]
    else:
        print("Specify --crypto <name> or --all")
        return

    mine_and_store(cryptos, args.days, args.exchange)

    print("💡 Next steps:")
    print("  1. Run time-of-day analysis: python3 analysis/time_of_day_analysis.py --all --days 7")
    print("  2. Test mean reversion: python3 analysis/mean_reversion_strategy.py --all")
    print("  3. Compare patterns across time periods")


if __name__ == '__main__':
    main()
