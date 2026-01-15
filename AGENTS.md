# Agent Knowledge Base

Reusable patterns and gotchas for future development work.

---

## Position Conflict Detection

**Pattern:** Always query live Polymarket API before placing orders, never trust internal state alone.

**Why:** The Guardian's `self.open_positions` list can get out of sync with blockchain reality due to:
- Manual redemptions
- Failed order placements that weren't recorded
- State resets
- Multiple processes running

**Implementation:**
```python
# Query live API
resp = requests.get(
    "https://data-api.polymarket.com/positions",
    params={"user": EOA, "limit": 50},
    timeout=10
)

# Check for conflicts by crypto + direction
for pos in resp.json():
    if crypto.upper() in pos['title'].upper():
        # Extract direction from 'outcome' field ("Up" or "Down")
        # Check if same OR opposite direction (both are conflicts)
```

**Key Fields in Position Response:**
- `title`: Market question (contains crypto name)
- `outcome`: "Up" or "Down"
- `size`: Number of shares (ignore if < 0.01)
- `curPrice`: Current probability
- `conditionId`: Blockchain identifier

**Gotcha:** Cannot easily parse exact epoch timestamp from titles. Use crypto + direction matching instead.

---

## ML Bot + Agent System Coexistence

**Pattern:** When `USE_ML_BOT=true`, the ML path should completely skip agent system logic.

**Why:** Running both ML and agents can cause:
- Conflicting decisions
- Double position placements
- Negated trading edge

**Implementation:**
```python
if use_ml_bot and ML_BOT_AVAILABLE:
    # ML makes decision
    ...
    continue  # Skip to next crypto

elif agent_system and agent_system.enabled:
    # Add explicit guard
    if use_ml_bot and ML_BOT_AVAILABLE:
        log.warning("Skipping agent decision - ML mode active")
        continue
    # Agent logic here
```

**Gotcha:** Even if ML path does `continue`, add explicit guard in agent path for safety. Code can change, explicit is better than implicit.

---

## Guardian Risk Checks Priority Order

**Pattern:** Run checks in order of criticality:

1. **Live API position conflicts** (highest priority - prevents catastrophic losses)
2. **Correlation limits** (max same direction, total positions)
3. **Internal state checks** (epoch bets, crypto limits)
4. **Drawdown/mode checks** (circuit breakers)

**Why:** Most critical checks should fail fast before spending time on less critical ones.

**Implementation:**
```python
def can_open_position(self, crypto, epoch, direction):
    # 1. Check live API FIRST
    has_conflict, msg = self.check_live_position_conflicts(crypto, direction)
    if has_conflict:
        return False, msg

    # 2. Then check correlation
    can_corr, reason = self.check_correlation_limits(direction)
    if not can_corr:
        return False, reason

    # 3. Then internal state
    # ...
```

---

## Polymarket API Gotchas

**API Endpoints:**
- Positions: `https://data-api.polymarket.com/positions?user=WALLET`
- Markets: `https://gamma-api.polymarket.com/...`
- Orders: `https://clob.polymarket.com/...`

**Common Issues:**
- Status 400: Invalid wallet address or missing params
- Rate limits: ~100 req/min on CLOB API
- Timeout: Always use `timeout=10` parameter
- Position size rounding: Ignore positions < 0.01 shares

**Error Handling:**
```python
try:
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        log.warning(f"API error {resp.status_code}")
        return default_value  # Don't block on API errors
except Exception as e:
    log.error(f"API exception: {e}")
    return default_value
```

**Gotcha:** API failures should log warnings but NOT block trading (fail open, not closed).

---

## Testing Strategy

**Pattern:** Create simple test files to validate logic before deploying.

**Example:** `test_conflict_check.py` simulates API responses to test conflict detection:
```python
def test_conflict_detection():
    test_cases = [
        {"name": "No conflict", "positions": [], ...},
        {"name": "Same direction", "positions": [{...}], ...},
        ...
    ]
    for test in test_cases:
        result = check_conflict(test["positions"], ...)
        assert result == test["expected"]
```

**Why:** Live testing with real money is expensive. Unit tests catch bugs before deployment.

**Gotcha:** Test both positive cases (should detect conflict) AND negative cases (should allow trade).

---

## Code Organization

**Pattern:** This codebase uses single-file architecture for the main bot.

- `bot/momentum_bot_v12.py` - Main trading bot (1600+ lines)
- Classes defined in order: Guardian, StopLoss, AutoRedeemer, FutureWindow, etc.
- Config constants at top (lines 1-200)
- Main loop at bottom (lines 2000+)

**Why:** Simplifies deployment - single file to copy to VPS.

**Gotcha:** When adding new classes, insert them BEFORE the main loop, not after.

---

## Logging Best Practices

**Pattern:** Use structured logging with clear context:

```python
log.info(f"🤖 [ML Bot] {crypto.upper()} decision: {'TRADE' if should_trade else 'SKIP'}")
log.warning(f"  [{crypto.upper()}] BLOCKED: {reason}")
log.error(f"CRITICAL CONFLICT: {crypto} {direction} vs existing {existing_direction}")
```

**Why:** Makes debugging in production logs much easier.

**Emoji Guide:**
- 🤖 ML Bot decisions
- 🎯 Agent system decisions
- ✅ Successful actions
- ❌ Errors
- ⚠️ Warnings
- 🔄 State changes

**Gotcha:** Always include crypto name in brackets `[BTC]` for easy grep filtering.

---

## VPS Deployment

**Pattern:** Use `scripts/deploy.sh` for deployment:
```bash
ssh root@VPS_IP "cd /opt/polymarket-autotrader && ./scripts/deploy.sh"
```

**Steps in deploy.sh:**
1. Git pull latest
2. Install/update dependencies
3. Restart systemd service

**Gotcha:** Always test changes locally first. VPS is trading with real money.

**Rollback:**
```bash
ssh root@VPS_IP
cd /opt/polymarket-autotrader
git reset --hard HEAD~1  # Rollback one commit
systemctl restart polymarket-bot
```

---

## State Management

**Pattern:** Bot state persists in `state/trading_state.json`:
```json
{
  "current_balance": 176.78,
  "peak_balance": 242.44,
  "mode": "normal",
  "consecutive_losses": 0,
  ...
}
```

**Critical Fields:**
- `peak_balance`: Used for drawdown calculation (may need manual reset)
- `mode`: Trading mode (normal/conservative/defensive/recovery/halted)
- `consecutive_losses`: Affects position sizing

**Gotcha:** If peak_balance gets too high (includes unrealized positions), bot may halt prematurely. Reset manually:
```python
import json
with open('state/trading_state.json', 'r+') as f:
    state = json.load(f)
    state['peak_balance'] = state['current_balance']
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
```

---

## Database Schema (Shadow Trading)

**Pattern:** ML trades logged to `simulation/trade_journal.db` (SQLite):

**Tables:**
- `strategies` - Strategy configurations
- `decisions` - Every decision (trade or skip)
- `trades` - Executed trades
- `outcomes` - Resolved results
- `agent_votes` - Individual agent votes
- `performance` - Aggregated metrics

**Usage:**
```bash
sqlite3 simulation/trade_journal.db "SELECT * FROM trades WHERE strategy = 'ml_live_ml_random_forest'"
```

**Gotcha:** Database writes can fail silently. Always check `success` return value and log failures.

---

## Common Mistakes to Avoid

1. **Don't trust internal state** - Always query live API for positions
2. **Don't fall back to agents** - When ML is enabled, skip on ML failure
3. **Don't block on API errors** - Log and continue, don't halt trading
4. **Don't forget to commit state** - Changes to trading_state.json should persist
5. **Don't test on VPS** - Always test locally first
6. **Don't commit .env** - Keep credentials in .env (gitignored)
7. **Don't ignore conflicts** - Check for BOTH same and opposite direction

---

**Last Updated:** January 15, 2026
**Maintained by:** Development Team
