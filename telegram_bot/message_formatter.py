#!/usr/bin/env python3
"""
Message Formatter for Telegram Bot

Formats data from trading bot into Telegram messages.
"""

import os
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class MessageFormatter:
    """Formats trading data for Telegram messages."""

    def __init__(self):
        self.wallet = os.getenv('POLYMARKET_WALLET', '0x52dF6Dc5DE31DD844d9E432A0821BC86924C2237')
        self.state_file = '/opt/polymarket-autotrader/state/trading_state.json'
        self.db_path = '/opt/polymarket-autotrader/simulation/trade_journal.db'

        # Fallback to local paths if VPS paths don't exist
        if not os.path.exists(self.state_file):
            self.state_file = 'state/trading_state.json'
        if not os.path.exists(self.db_path):
            self.db_path = 'simulation/trade_journal.db'

    def get_usdc_balance(self) -> Optional[float]:
        """Get current USDC balance from blockchain."""
        try:
            rpc_url = 'https://polygon-rpc.com'
            usdc_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
            data = '0x70a08231000000000000000000000000' + self.wallet[2:].lower()

            response = requests.post(rpc_url, json={
                'jsonrpc': '2.0',
                'method': 'eth_call',
                'params': [{'to': usdc_address, 'data': data}, 'latest'],
                'id': 1
            }, timeout=10)

            balance_hex = response.json().get('result', '0x0')
            return int(balance_hex, 16) / 1e6
        except Exception:
            return None

    def get_bot_state(self) -> Optional[Dict]:
        """Read bot trading state."""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def get_current_crypto_price(self, crypto: str) -> Optional[float]:
        """Get current price for a crypto from Binance."""
        try:
            symbol_map = {
                'BTC': 'BTCUSDT',
                'ETH': 'ETHUSDT',
                'SOL': 'SOLUSDT',
                'XRP': 'XRPUSDT'
            }

            symbol = symbol_map.get(crypto)
            if not symbol:
                return None

            resp = requests.get(
                f'https://api.binance.com/api/v3/ticker/price',
                params={'symbol': symbol},
                timeout=3
            )

            if resp.status_code == 200:
                return float(resp.json()['price'])
        except Exception:
            pass

        return None

    def get_epoch_start_price(self, crypto_ticker: str, epoch_timestamp: int) -> Optional[float]:
        """Get crypto price at epoch start from Binance historical data."""
        try:
            symbol_map = {
                'BTC': 'BTCUSDT',
                'ETH': 'ETHUSDT',
                'SOL': 'SOLUSDT',
                'XRP': 'XRPUSDT'
            }

            symbol = symbol_map.get(crypto_ticker)
            if not symbol:
                return None

            start_time_ms = epoch_timestamp * 1000

            resp = requests.get(
                'https://api.binance.com/api/v3/klines',
                params={
                    'symbol': symbol,
                    'interval': '1m',
                    'startTime': start_time_ms,
                    'limit': 1
                },
                timeout=5
            )

            if resp.status_code == 200:
                klines = resp.json()
                if klines and len(klines) > 0:
                    return float(klines[0][1])  # Open price
        except Exception:
            pass

        return None

    def format_balance(self) -> str:
        """Format balance and P&L information."""
        state = self.get_bot_state()
        blockchain_balance = self.get_usdc_balance()

        if not state:
            return "❌ Could not read bot state file"

        current_balance = state.get('current_balance', 0)
        day_start = state.get('day_start_balance', 0)
        peak = state.get('peak_balance', 0)
        daily_pnl = state.get('daily_pnl', 0)

        # Calculate daily P&L percentage
        daily_pnl_pct = (daily_pnl / day_start * 100) if day_start > 0 else 0

        message = "💰 *BALANCE & P&L*\n\n"
        message += f"Current: `${current_balance:.2f}`\n"
        message += f"Day Start: `${day_start:.2f}`\n"
        message += f"Peak: `${peak:.2f}`\n\n"

        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
        message += f"{pnl_emoji} Daily P&L: `${daily_pnl:+.2f}` ({daily_pnl_pct:+.1f}%)\n\n"

        if blockchain_balance is not None:
            match_emoji = "✅" if abs(blockchain_balance - current_balance) < 0.01 else "⚠️"
            message += f"🔗 Blockchain: `${blockchain_balance:.2f}` {match_emoji}"
        else:
            message += "🔗 Blockchain: _Could not fetch_"

        return message

    def format_positions(self) -> str:
        """Format active positions information."""
        try:
            resp = requests.get(
                'https://data-api.polymarket.com/positions',
                params={'user': self.wallet, 'limit': 50},
                timeout=10
            )

            if resp.status_code != 200:
                return "❌ Could not fetch positions from API"

            positions = resp.json()

            # Filter for active positions (non-zero probability)
            active_positions = []
            for pos in positions:
                size = float(pos.get('size', 0))
                cur_price = float(pos.get('curPrice', 0))

                if size > 0 and cur_price > 0.001:  # Active position
                    active_positions.append(pos)

            if not active_positions:
                return "📭 *NO ACTIVE POSITIONS*\n\nNo positions currently held."

            message = f"📈 *ACTIVE POSITIONS* ({len(active_positions)})\n\n"

            total_value = 0
            total_max_payout = 0

            for i, pos in enumerate(active_positions[:10], 1):  # Limit to 10 for message size
                size = float(pos.get('size', 0))
                cur_price = float(pos.get('curPrice', 0))
                outcome = pos.get('outcome', 'Unknown')
                question = pos.get('title', 'Unknown Market')
                slug = pos.get('slug', '')

                current_value = size * cur_price
                max_payout = size * 1.0

                total_value += current_value
                total_max_payout += max_payout

                # Determine status emoji
                if cur_price >= 0.90:
                    status_emoji = "🟢"
                elif cur_price >= 0.50:
                    status_emoji = "🟡"
                elif cur_price >= 0.20:
                    status_emoji = "🟠"
                else:
                    status_emoji = "🔴"

                message += f"{status_emoji} *{outcome}*: {size:.0f} shares @ {cur_price*100:.1f}%\n"

                # Add price comparison if available
                if slug:
                    crypto_ticker = slug.split('-')[0].upper() if slug else None
                    direction = outcome

                    if crypto_ticker and '-' in slug:
                        slug_parts = slug.split('-')
                        if len(slug_parts) >= 4:
                            try:
                                epoch_timestamp = int(slug_parts[-1])
                                start_price = self.get_epoch_start_price(crypto_ticker, epoch_timestamp)
                                current_price = self.get_current_crypto_price(crypto_ticker)

                                if start_price and current_price:
                                    price_diff = current_price - start_price
                                    price_diff_pct = (price_diff / start_price) * 100

                                    is_winning = False
                                    if "Up" in direction and current_price > start_price:
                                        is_winning = True
                                    elif "Down" in direction and current_price < start_price:
                                        is_winning = True

                                    status_text = "✅ WINNING" if is_winning else "❌ LOSING"
                                    arrow = "↑" if price_diff > 0 else "↓"

                                    message += f"   {crypto_ticker}: ${start_price:.2f} → ${current_price:.2f} {arrow} ({price_diff_pct:+.2f}%) {status_text}\n"
                            except Exception:
                                pass

                message += f"   Value: `${current_value:.2f}` | Max: `${max_payout:.2f}`\n\n"

            # Summary
            unrealized_pnl = total_value - (total_max_payout - total_value)
            pnl_pct = (unrealized_pnl / total_value * 100) if total_value > 0 else 0

            message += "💰 *SUMMARY*\n"
            message += f"Total Value: `${total_value:.2f}`\n"
            message += f"If All Win: `${total_max_payout:.2f}`\n"
            message += f"Unrealized P&L: `${unrealized_pnl:+.2f}` ({pnl_pct:+.1f}%)"

            return message

        except Exception as e:
            return f"❌ Error fetching positions: {str(e)}"

    def format_status(self) -> str:
        """Format bot status information."""
        state = self.get_bot_state()

        if not state:
            return "❌ Could not read bot state file"

        mode = state.get('mode', 'unknown').upper()
        consecutive_wins = state.get('consecutive_wins', 0)
        consecutive_losses = state.get('consecutive_losses', 0)

        # Mode emoji
        mode_emoji = {
            'NORMAL': '🟢',
            'CONSERVATIVE': '🟡',
            'DEFENSIVE': '🟠',
            'RECOVERY': '🔴',
            'HALTED': '⛔'
        }.get(mode, '⚪')

        message = "🤖 *BOT STATUS*\n\n"
        message += f"Mode: {mode_emoji} *{mode}*\n\n"

        # Enabled agents (from config)
        enabled_agents = [
            'Tech', 'Sentiment', 'Regime', 'Candlestick',
            'TimePattern', 'OrderBook', 'FundingRate'
        ]
        message += f"Agents: {', '.join(enabled_agents)}\n"
        message += "(+ Risk, Gambler veto)\n\n"

        # Recent activity
        message += "*Recent Activity:*\n"

        # Get 24h trade count from database
        try:
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT COUNT(*)
                    FROM outcomes o
                    JOIN trades t ON o.trade_id = t.id
                    WHERE t.is_shadow = 0
                      AND datetime(o.created_at) >= datetime('now', '-1 day')
                ''')

                trades_24h = cursor.fetchone()[0]
                conn.close()

                message += f"• 24h trades: {trades_24h}\n"
        except Exception:
            message += f"• 24h trades: _Unknown_\n"

        message += f"• Streak: {consecutive_wins}W / {consecutive_losses}L\n"

        # Shadow strategies count
        message += f"• Shadow strategies: 30\n\n"

        # Last update time
        message += f"_Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC_"

        return message

    def format_statistics(self) -> str:
        """Format trading statistics."""
        try:
            if not os.path.exists(self.db_path):
                return "❌ Database not found"

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Overall stats - filter by live strategy (ml_live_*)
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN predicted_direction = actual_direction THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN predicted_direction != actual_direction THEN 1 ELSE 0 END) as losses,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM outcomes o
                JOIN trades t ON o.trade_id = t.id
                WHERE t.strategy LIKE 'ml_live%'
            ''')

            row = cursor.fetchone()
            total, wins, losses, total_pnl, avg_pnl, best_trade, worst_trade = row

            if total == 0 or total is None:
                conn.close()
                return "📊 TRADING STATISTICS\n\nNo trades recorded yet."

            win_rate = (wins / total * 100) if total > 0 else 0

            # Plain text formatting (no Markdown)
            message = "📊 TRADING STATISTICS (All-Time)\n\n"
            message += f"Total Trades: {total}\n"
            message += f"Wins: {wins} ({win_rate:.1f}%)\n"
            message += f"Losses: {losses} ({100-win_rate:.1f}%)\n\n"

            message += f"Total P&L: ${total_pnl:.2f}\n"
            message += f"Avg P&L/Trade: ${avg_pnl:.2f}\n\n"

            message += f"Best: ${best_trade:+.2f}\n"
            message += f"Worst: ${worst_trade:+.2f}\n\n"

            # Current streak
            state = self.get_bot_state()
            if state:
                consecutive_wins = state.get('consecutive_wins', 0)
                consecutive_losses = state.get('consecutive_losses', 0)

                if consecutive_wins > 0:
                    message += f"Current Streak: {consecutive_wins}W 🔥"
                elif consecutive_losses > 0:
                    message += f"Current Streak: {consecutive_losses}L ⚠️"
                else:
                    message += "Current Streak: None"

            conn.close()
            return message

        except Exception as e:
            return f"❌ Error fetching statistics: {str(e)}"
