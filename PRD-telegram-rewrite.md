# PRD: Telegram Bot Rewrite

## Introduction

Complete rewrite of the Telegram bot integration for Polymarket AutoTrader. The current implementation was built for `momentum_bot_v12.py` and has critical compatibility issues with the active `intra_epoch_bot.py`. This rewrite creates a unified, lightweight Telegram integration that works with the intra-epoch bot's architecture.

## Goals

- **Unified Integration** - Single Telegram module that works with intra_epoch_bot
- **Real-time Notifications** - Trade entries, outcomes, halts, and alerts
- **Query Commands** - Balance, positions, status, statistics on demand
- **Control Commands** - Halt, resume, force redeem with confirmation
- **Signal Visibility** - Surface pattern/magnitude/confluence data
- **Reliability** - No race conditions, proper error handling, non-blocking
- **Simplicity** - Minimal code, easy to maintain, no over-engineering

## Non-Goals

- Supporting momentum_bot_v12.py (deprecated)
- Complex interactive menus or inline keyboards
- Multiple user support (single authorized user only)
- Webhook mode (polling is sufficient for our volume)
- Database-backed message history
- Scheduled reports (daily summaries can be added later)

## Architecture

### Design Principles

1. **Single File** - All Telegram code in one module (`bot/telegram_handler.py`)
2. **Direct HTTP** - Use requests library, not python-telegram-bot SDK (simpler)
3. **Non-blocking** - Notifications run in background threads
4. **Fail-safe** - Telegram failures never crash the trading bot
5. **State Reading Only** - Telegram bot reads state, doesn't write (no race conditions)

### File Structure

```
bot/
├── intra_epoch_bot.py      # Main trading bot (imports telegram_handler)
└── telegram_handler.py     # NEW: All Telegram functionality
```

### Integration Pattern

```python
# In intra_epoch_bot.py
from telegram_handler import TelegramBot

# Initialize once at startup
telegram = TelegramBot()

# Send notifications (non-blocking)
telegram.notify_trade(crypto, direction, entry_price, size, pattern_accuracy, confluence)
telegram.notify_win(crypto, direction, profit, balance)
telegram.notify_loss(crypto, direction, loss, balance)
telegram.notify_halt(reason, balance)

# Query handlers run in background polling loop
telegram.start_polling()  # Called at bot startup
```

---

## User Stories

### US-TG-001: Core Telegram Handler Module

**Description:** Create the base Telegram handler with authentication and messaging.

**Acceptance Criteria:**
- [x] Create `bot/telegram_handler.py` with `TelegramBot` class
- [x] Load config from env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED`
- [x] Implement `send_message(text, parse_mode='HTML', silent=False)` method
- [x] Implement `is_authorized(user_id)` check against `TELEGRAM_CHAT_ID`
- [x] All sends wrapped in try/except with logging (never raise)
- [x] Messages sent in background thread (non-blocking)
- [x] Startup log shows "Telegram: ENABLED" or "Telegram: DISABLED"

---

### US-TG-002: Trade Entry Notifications

**Description:** Notify when a new trade is placed with full signal context.

**Acceptance Criteria:**
- [x] Implement `notify_trade(crypto, direction, entry_price, size, accuracy, magnitude_pct, confluence_count, is_averaging=False)`
- [x] Format message with:
  - Action emoji: "🎯 NEW TRADE" or "📈 AVERAGING"
  - Crypto and direction in bold
  - Entry price and size
  - Pattern accuracy with magnitude boost breakdown
  - Confluence status (e.g., "3/3 exchanges agree")
- [x] Example format:
  ```
  🎯 NEW TRADE
  <b>BTC Down</b>
  Entry: $0.45 | Size: $5.00
  Accuracy: 77% (74% + 3% magnitude)
  Confluence: 3/3 exchanges agree
  ```
- [x] Call from main loop when trade is placed

---

### US-TG-003: Trade Outcome Notifications

**Description:** Notify when trades resolve as wins or losses.

**Acceptance Criteria:**
- [x] Implement `notify_win(crypto, direction, profit, balance, win_rate)`
- [x] Implement `notify_loss(crypto, direction, loss, balance, win_rate)`
- [x] Win format:
  ```
  ✅ WIN
  <b>BTC Down</b>
  Profit: +$3.22
  Balance: $62.45 | Win Rate: 65%
  ```
- [x] Loss format:
  ```
  ❌ LOSS
  <b>ETH Up</b>
  Loss: -$5.00
  Balance: $57.45 | Win Rate: 62%
  ```
- [x] Call from `resolve_completed_positions()` after outcome determined

---

### US-TG-004: Halt and Alert Notifications

**Description:** Critical alerts when bot halts or encounters issues.

**Acceptance Criteria:**
- [x] Implement `notify_halt(reason, balance, drawdown_pct=None)`
- [x] Implement `notify_alert(message, level='warning')` where level is 'info', 'warning', 'critical'
- [x] Implement `notify_resumed(balance, drawdown_pct)`
- [x] Halt format:
  ```
  🚨 BOT HALTED
  <b>Reason:</b> Drawdown exceeded 30%
  Drawdown: 32.5%
  Balance: $45.00
  ```
- [x] Alert uses emoji based on level: ℹ️ info, ⚠️ warning, 🚨 critical
- [x] Call notify_halt from risk check functions
- [x] Call notify_resumed from auto-resume logic

---

### US-TG-005: Redemption Notifications

**Description:** Notify when positions are redeemed.

**Acceptance Criteria:**
- [ ] Implement `notify_redemption(count, total_value)`
- [ ] Format:
  ```
  💰 REDEEMED
  Positions: 3
  Value: $12.45
  ```
- [ ] Only notify if count > 0 and value > $1
- [ ] Call from AutoRedeemer after successful redemption

---

### US-TG-006: Startup Notification

**Description:** Notify when bot starts with current state.

**Acceptance Criteria:**
- [ ] Implement `notify_startup(balance, peak, trades, wins, losses)`
- [ ] Format:
  ```
  🤖 BOT STARTED
  Balance: $58.65
  Peak: $72.00 | Drawdown: 18.5%
  Record: 15W/8L (65.2%)
  Trading window: minutes 3-10
  ```
- [ ] Call from `run_bot()` after initialization
- [ ] Include granular signals status if enabled

---

### US-TG-007: Command Polling Loop

**Description:** Background polling for Telegram commands.

**Acceptance Criteria:**
- [ ] Implement `start_polling()` method that runs in daemon thread
- [ ] Poll `getUpdates` API every 2 seconds
- [ ] Track `update_id` offset to avoid processing same message twice
- [ ] Parse commands starting with `/`
- [ ] Ignore messages from unauthorized users (log warning)
- [ ] Graceful shutdown on bot exit
- [ ] Commands processed: `/balance`, `/positions`, `/status`, `/stats`, `/halt`, `/resume`, `/help`

---

### US-TG-008: Query Commands - Balance and Positions

**Description:** Commands to check current balance and open positions.

**Acceptance Criteria:**
- [ ] Implement `/balance` command handler
- [ ] `/balance` response:
  ```
  💰 BALANCE
  Current: $58.65
  Peak: $72.00 | Drawdown: 18.5%
  Daily P&L: +$4.20
  ```
- [ ] Implement `/positions` command handler
- [ ] `/positions` response (with positions):
  ```
  📊 POSITIONS (2 open)

  BTC Down @ $0.45
  Size: $5.00 | Epoch: 14:30

  ETH Up @ $0.32
  Size: $5.00 | Epoch: 14:30
  ```
- [ ] `/positions` response (no positions): "No open positions"
- [ ] Read state from `state/intra_epoch_state.json`

---

### US-TG-009: Query Commands - Status and Stats

**Description:** Commands to check bot status and trading statistics.

**Acceptance Criteria:**
- [ ] Implement `/status` command handler
- [ ] `/status` response:
  ```
  🤖 STATUS
  Mode: Trading (not halted)
  Current Epoch: 14:30 UTC
  Time in Epoch: 5:23
  Trading Window: OPEN (min 3-10)
  Positions: 2 open
  ```
- [ ] Implement `/stats` command handler
- [ ] `/stats` response:
  ```
  📈 STATISTICS
  Total Trades: 31
  Wins: 15 | Losses: 8
  Win Rate: 65.2%
  Best: +$4.50 | Worst: -$5.00
  ```
- [ ] Implement `/help` command with list of available commands

---

### US-TG-010: Control Commands - Halt and Resume

**Description:** Commands to halt and resume trading.

**Acceptance Criteria:**
- [ ] Implement `/halt` command handler
- [ ] `/halt` sets `state.halted = True` and `state.halt_reason = "Manual halt via Telegram"`
- [ ] Response: "🛑 Trading HALTED. Use /resume to restart."
- [ ] Implement `/resume` command handler
- [ ] `/resume` checks drawdown - if > 30%, refuse with message
- [ ] `/resume` sets `state.halted = False` and clears halt_reason
- [ ] Response: "✅ Trading RESUMED. Balance: $XX.XX"
- [ ] State changes saved immediately via `state.save()`
- [ ] Use file locking (`fcntl`) when writing state to prevent corruption

---

### US-TG-011: Signal Skip Summaries (Optional Enhancement)

**Description:** Periodic summary of why signals were skipped.

**Acceptance Criteria:**
- [ ] Implement `/signals` command handler
- [ ] Query `state/intra_signals.db` for current epoch's signals
- [ ] Response:
  ```
  📊 SIGNALS (Epoch 14:30)
  Analyzed: 4 cryptos

  BTC: Down 74% - SKIP (no confluence)
  ETH: weak pattern (3↑2↓)
  SOL: weak pattern (2↑3↓)
  XRP: Down 77% - SKIP (entry $0.85 > max)
  ```
- [ ] Show decision reason for each crypto

---

## Technical Specifications

### Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_user_id
TELEGRAM_ENABLED=true
```

### Message Formatting

- Use HTML parse mode for formatting
- `<b>bold</b>` for emphasis
- Keep messages concise (under 300 chars typical)
- Use line breaks for readability
- Consistent emoji usage per message type

### Error Handling

```python
def send_message(self, text: str) -> bool:
    if not self.enabled:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")
        return False
```

### Thread Safety

- Notifications sent from background threads
- Command polling in dedicated daemon thread
- State reads use copy to avoid mutation during read
- State writes use `fcntl.flock()` for file locking

### State File Access

Read from: `state/intra_epoch_state.json`
```json
{
  "current_balance": 58.65,
  "peak_balance": 72.00,
  "daily_pnl": 4.20,
  "total_trades": 31,
  "total_wins": 15,
  "total_losses": 8,
  "positions": {...},
  "halted": false,
  "halt_reason": null
}
```

---

## Migration Plan

1. **Create new module** - `bot/telegram_handler.py`
2. **Update intra_epoch_bot.py** - Import and use new TelegramBot class
3. **Remove old integration** - Delete local `send_telegram()`, `notify_trade()`, etc.
4. **Test locally** - Verify all notifications and commands work
5. **Deploy to VPS** - Replace old telegram_bot service
6. **Archive old module** - Move `telegram_bot/` to `telegram_bot_deprecated/`

---

## Success Metrics

- All notifications delivered within 2 seconds
- Zero crashes due to Telegram failures
- Commands respond within 1 second
- 100% of trades/outcomes notified
- Clean separation between trading logic and notifications

---

## Implementation Order

1. **US-TG-001** - Core handler (required for everything)
2. **US-TG-002** - Trade notifications (most important)
3. **US-TG-003** - Outcome notifications
4. **US-TG-004** - Halt/alert notifications
5. **US-TG-006** - Startup notification
6. **US-TG-005** - Redemption notifications
7. **US-TG-007** - Command polling loop
8. **US-TG-008** - Balance/positions commands
9. **US-TG-009** - Status/stats commands
10. **US-TG-010** - Halt/resume commands
11. **US-TG-011** - Signal summaries (optional)

---

## Estimated Effort

- Core notifications (US-TG-001 to US-TG-006): ~200 lines
- Command polling (US-TG-007 to US-TG-010): ~150 lines
- Integration updates: ~50 lines removed, ~20 lines added
- **Total new code: ~350 lines** (vs 2,534 lines in old module)
