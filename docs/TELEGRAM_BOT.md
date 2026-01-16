# Telegram Bot Documentation

## Overview

The Polymarket AutoTrader Telegram bot provides real-time notifications and mobile monitoring capabilities for the trading bot. It allows you to:

- Query bot status, balance, and positions via chat commands
- Receive instant notifications for trades, redemptions, and critical alerts
- Control the bot remotely (halt, resume, change mode)
- Get daily performance summaries automatically

## Setup

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow the prompts
3. Save the bot token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Save your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_AUTHORIZED_USER_ID=123456789
TELEGRAM_NOTIFICATIONS_ENABLED=true
```

### 3. Install Dependencies

```bash
source venv/bin/activate
pip install python-telegram-bot>=20.7
```

### 4. Run the Bot

**Development (local testing):**
```bash
python3 telegram_bot/telegram_notifier.py
```

**Production (VPS - systemd service):**
```bash
# Create service file
sudo nano /etc/systemd/system/telegram-bot.service
```

Service file content:
```ini
[Unit]
Description=Polymarket AutoTrader Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/polymarket-autotrader
Environment=PATH=/opt/polymarket-autotrader/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/polymarket-autotrader/venv/bin/python3 /opt/polymarket-autotrader/telegram_bot/telegram_notifier.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

### 5. Set Up Daily Summaries (Optional)

**Option 1: Cron Job (Recommended)**

Add to crontab:
```bash
crontab -e
```

Add this line:
```cron
59 23 * * * cd /opt/polymarket-autotrader && source venv/bin/activate && python3 telegram_bot/daily_summary_scheduler.py --now
```

**Option 2: Daemon Mode**

Run scheduler as background process:
```bash
nohup python3 telegram_bot/daily_summary_scheduler.py &
```

## Commands

### Query Commands

- `/start` - Welcome message and command list
- `/help` - Show all available commands
- `/balance` - Current balance, daily P&L, blockchain verification
- `/positions` - Active positions with win/loss status
- `/status` - Bot mode, enabled agents, recent activity
- `/stats` - Trading statistics (win rate, P&L, streaks)

### Control Commands

- `/halt` - Stop trading (requires confirmation)
- `/resume` - Resume trading (requires confirmation)
- `/mode <mode>` - Change trading mode (requires confirmation)
  - Supported modes: `normal`, `conservative`, `defensive`, `recovery`, `halted`

## Notifications

The bot sends automatic notifications for:

### Trade Notifications
Sent immediately after placing a trade:
```
🚀 NEW TRADE

SOL Down @ $0.13
Size: $8.50 (16 shares)
Confidence: 72%

Agents: Tech ✅, Sentiment ✅, Regime ✅
Strategy: Contrarian fade

🔗 View Market
```

### Redemption Notifications
Sent when positions are redeemed (wins or losses):
```
✅ REDEMPTION - WIN

SOL Down: 16 shares
P&L: $+8.45
Entry: $0.13 → Payout: $1.00

New Balance: $259.92
```

### Alert Notifications
Sent for critical events (drawdowns, performance issues):
```
🚨 CRITICAL ALERT

Win Rate Below Threshold

Win rate in last 20 trades: 42.0% (threshold: 50.0%)

Time: 2026-01-15 22:45 UTC

⚠️ Review recent trades and consider adjusting strategy
```

### Daily Summaries
Sent at 23:59 UTC daily:
```
📊 DAILY SUMMARY - Jan 15, 2026

P&L: $+244.67 (+3594.6%)
Trades: 3 (2W / 1L)
Win Rate: 66.7%

Balance: $6.80 → $251.47

Best: SOL Down +$8.45
Worst: BTC Up -$7.29

🎯 Shadow Leaders:
1. contrarian_focused: +$12.30
2. conservative: +$8.70
3. default: +$5.20

Tomorrow: Mode NORMAL, 7 agents active
```

## Security

### Authentication
- Only the authorized Telegram user ID can interact with the bot
- All unauthorized access attempts are logged and rejected
- No public commands - single user access only

### Credentials
- Never commit `.env` file to git
- Keep bot token secure (treat like a password)
- Store authorized user ID in environment variable

### Logging
All bot interactions are logged with:
- User ID and username
- Command executed
- Timestamp
- Response status

Logs are written to stdout and can be viewed with:
```bash
journalctl -u telegram-bot -f
```

## Error Handling

### Telegram API Errors
- Network failures are logged but don't crash the bot
- Automatic retry with exponential backoff for rate limits
- Graceful degradation (trading continues if Telegram is down)

### Trading Bot Integration
- Notifications run asynchronously (don't block trading)
- Failed notifications are logged but don't crash trading bot
- `TELEGRAM_NOTIFICATIONS_ENABLED` flag to disable if needed

### Common Issues

**Bot doesn't respond:**
- Check bot is running: `systemctl status telegram-bot`
- Verify token in `.env` is correct
- Check network connectivity to Telegram API

**Unauthorized message:**
- Verify your user ID matches `TELEGRAM_AUTHORIZED_USER_ID`
- Check `.env` is loaded correctly

**No notifications received:**
- Check `TELEGRAM_NOTIFICATIONS_ENABLED=true` in `.env`
- Verify trading bot has Telegram integration enabled
- Check logs for errors: `tail -f bot.log | grep -i telegram`

## Architecture

### File Structure
```
telegram_bot/
├── __init__.py
├── telegram_notifier.py       # Main bot, commands, notifications
├── message_formatter.py        # Format messages (balance, positions, etc.)
└── daily_summary_scheduler.py  # Scheduled daily summaries
```

### Dependencies
- `python-telegram-bot>=20.7` - Telegram bot API client
- `web3` - Blockchain balance verification
- `requests` - Polymarket API queries
- `sqlite3` - Trade statistics database

### Integration Points

**Trading Bot (`bot/momentum_bot_v12.py`):**
- Trade notifications after order placement
- Redemption notifications after wins/losses
- Imports from `telegram_bot.telegram_notifier`

**Alert System (`analytics/alert_system.py`):**
- Critical alert forwarding
- Imports from `telegram_bot.telegram_notifier`

**State File (`state/trading_state.json`):**
- Balance queries
- Mode changes
- Status queries

**Database (`simulation/trade_journal.db`):**
- Statistics queries
- Shadow strategy comparison

## Monitoring

### Bot Health
```bash
# Service status
systemctl status telegram-bot

# Recent logs
journalctl -u telegram-bot -n 50

# Live logs
journalctl -u telegram-bot -f
```

### Performance Metrics
- **Notification latency:** <2 seconds (trade/redemption)
- **Query response time:** <3 seconds (balance/positions)
- **Uptime target:** 99.9%
- **Impact on trading:** Zero (async notifications)

### Testing Notifications

Send test messages to verify setup:
```python
from telegram_bot.telegram_notifier import notify_alert

notify_alert(
    level='info',
    title='Test Alert',
    message='Testing Telegram notifications'
)
```

## Future Enhancements

Planned features (post-MVP):
- Voice message alerts (text-to-speech)
- Chart/graph images (balance history, P&L trends)
- Multiple authorized users (team access)
- Callback buttons for quick actions
- Natural language queries via Claude API
- Strategy comparison updates

## Support

For issues or questions:
- GitHub: https://github.com/mmartoccia/polymarket-autotrader
- Check logs: `journalctl -u telegram-bot -f`
- Review `CLAUDE.md` for bot context

## Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API
- [Polymarket API](https://docs.polymarket.com) - Position and market data
- [Web3.py](https://github.com/ethereum/web3.py) - Blockchain integration
