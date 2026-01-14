#!/usr/bin/env python3
"""
Outcome Fetcher - Get actual market outcomes for completed epochs

Fetches real price data from exchanges to determine if price went Up or Down
during a completed 15-minute epoch. This replaces random outcomes with actual
market results for shadow trading performance analysis.
"""

import sys
import time
import requests
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

sys.path.append(str(Path(__file__).parent.parent))

# Exchange symbols (same as main bot)
EXCHANGE_SYMBOLS = {
    'btc': {
        'binance': 'BTCUSDT',
        'kraken': 'XXBTZUSD',
        'coinbase': 'BTC-USD'
    },
    'eth': {
        'binance': 'ETHUSDT',
        'kraken': 'XETHZUSD',
        'coinbase': 'ETH-USD'
    },
    'sol': {
        'binance': 'SOLUSDT',
        'kraken': 'SOLUSD',
        'coinbase': 'SOL-USD'
    },
    'xrp': {
        'binance': 'XRPUSDT',
        'kraken': 'XXRPZUSD',
        'coinbase': 'XRP-USD'
    }
}


@dataclass
class EpochOutcome:
    """Result of epoch analysis."""
    crypto: str
    epoch: int
    start_price: float
    end_price: float
    direction: str  # "Up" or "Down"
    change_pct: float
    sources_used: int


class OutcomeFetcher:
    """
    Fetches actual market outcomes for completed epochs.

    Uses Binance, Kraken, and Coinbase historical kline/OHLC data to determine
    the actual price direction during a 15-minute epoch.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; PolymarketBot/1.0)'
        })

    def get_epoch_outcome(self, crypto: str, epoch: int) -> Optional[EpochOutcome]:
        """
        Get actual market outcome for a completed epoch.

        Args:
            crypto: Cryptocurrency (btc, eth, sol, xrp)
            epoch: Epoch timestamp (start of 15-minute window)

        Returns:
            EpochOutcome with actual direction, or None if can't determine
        """
        # Verify epoch has ended
        current_time = int(time.time())
        if current_time < (epoch + 900):
            return None  # Epoch hasn't ended yet

        # Try each exchange in order of reliability
        start_price = None
        end_price = None
        sources = 0

        # Try Binance first (most reliable)
        binance_result = self._get_binance_epoch_prices(crypto, epoch)
        if binance_result:
            start_price, end_price = binance_result
            sources += 1

        # Fallback to Kraken if Binance fails
        if not start_price:
            kraken_result = self._get_kraken_epoch_prices(crypto, epoch)
            if kraken_result:
                start_price, end_price = kraken_result
                sources += 1

        # Fallback to current price comparison (less accurate but better than nothing)
        if not start_price:
            coinbase_result = self._get_coinbase_epoch_prices(crypto, epoch)
            if coinbase_result:
                start_price, end_price = coinbase_result
                sources += 1

        if not start_price or not end_price:
            return None

        # Determine direction
        change_pct = ((end_price - start_price) / start_price) * 100
        direction = "Up" if end_price > start_price else "Down"

        return EpochOutcome(
            crypto=crypto,
            epoch=epoch,
            start_price=start_price,
            end_price=end_price,
            direction=direction,
            change_pct=change_pct,
            sources_used=sources
        )

    def _get_binance_epoch_prices(self, crypto: str, epoch: int) -> Optional[tuple]:
        """
        Fetch epoch prices from Binance klines.

        Returns:
            (start_price, end_price) or None
        """
        try:
            symbol = EXCHANGE_SYMBOLS[crypto]['binance']

            # Binance klines: [open_time, open, high, low, close, volume, ...]
            # We want the 15-minute kline that contains our epoch
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': '15m',
                'startTime': epoch * 1000,  # Convert to milliseconds
                'endTime': (epoch + 900) * 1000,
                'limit': 1
            }

            resp = self.session.get(url, params=params, timeout=5)
            resp.raise_for_status()

            klines = resp.json()
            if not klines:
                return None

            kline = klines[0]
            open_price = float(kline[1])  # Open
            close_price = float(kline[4])  # Close

            return (open_price, close_price)

        except Exception as e:
            return None

    def _get_kraken_epoch_prices(self, crypto: str, epoch: int) -> Optional[tuple]:
        """
        Fetch epoch prices from Kraken OHLC.

        Returns:
            (start_price, end_price) or None
        """
        try:
            symbol = EXCHANGE_SYMBOLS[crypto]['kraken']

            # Kraken OHLC: [time, open, high, low, close, vwap, volume, count]
            url = f"https://api.kraken.com/0/public/OHLC"
            params = {
                'pair': symbol,
                'interval': 15,  # 15-minute candles
                'since': epoch
            }

            resp = self.session.get(url, params=params, timeout=5)
            resp.raise_for_status()

            data = resp.json()
            if data.get('error'):
                return None

            # Result is a dict with pair name as key
            for pair_name, ohlc_data in data.get('result', {}).items():
                if pair_name == 'last':
                    continue

                # Find the candle that matches our epoch
                for candle in ohlc_data:
                    candle_time = int(candle[0])
                    if candle_time == epoch:
                        open_price = float(candle[1])
                        close_price = float(candle[4])
                        return (open_price, close_price)

            return None

        except Exception as e:
            return None

    def _get_coinbase_epoch_prices(self, crypto: str, epoch: int) -> Optional[tuple]:
        """
        Fetch epoch prices from Coinbase (fallback - less reliable for historical).

        Returns:
            (start_price, end_price) or None
        """
        try:
            symbol = EXCHANGE_SYMBOLS[crypto]['coinbase']

            # Coinbase candles endpoint
            # GET /products/{product_id}/candles
            url = f"https://api.coinbase.com/v2/prices/{symbol}/spot"

            # Note: Coinbase's free API doesn't provide historical candles easily
            # This is just a placeholder - in practice, you'd need Pro API or similar
            # For now, return None to indicate we can't fetch from Coinbase
            return None

        except Exception as e:
            return None

    def batch_get_outcomes(self, epochs: list) -> Dict[tuple, EpochOutcome]:
        """
        Fetch outcomes for multiple epochs efficiently.

        Args:
            epochs: List of (crypto, epoch) tuples

        Returns:
            Dict mapping (crypto, epoch) -> EpochOutcome
        """
        results = {}

        for crypto, epoch in epochs:
            outcome = self.get_epoch_outcome(crypto, epoch)
            if outcome:
                results[(crypto, epoch)] = outcome

        return results


def main():
    """Test outcome fetcher."""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch actual market outcome for an epoch')
    parser.add_argument('crypto', choices=['btc', 'eth', 'sol', 'xrp'], help='Cryptocurrency')
    parser.add_argument('epoch', type=int, help='Epoch timestamp')

    args = parser.parse_args()

    fetcher = OutcomeFetcher()
    outcome = fetcher.get_epoch_outcome(args.crypto, args.epoch)

    if outcome:
        print(f"\nEpoch Outcome for {outcome.crypto.upper()}")
        print(f"Epoch: {outcome.epoch}")
        print(f"Start: ${outcome.start_price:,.2f}")
        print(f"End:   ${outcome.end_price:,.2f}")
        print(f"Change: {outcome.change_pct:+.3f}%")
        print(f"Direction: {outcome.direction}")
        print(f"Sources: {outcome.sources_used}")
    else:
        print(f"Could not determine outcome for {args.crypto} epoch {args.epoch}")
        print("(Epoch may not have ended yet, or data unavailable)")


if __name__ == '__main__':
    main()
