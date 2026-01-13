# State Directory

This directory holds bot state files that are **NOT tracked in git**.

## Files (gitignored)

- `trading_state.json` - Current trading state (balance, mode, consecutive wins/losses, etc.)
- `timeframe_trades.json` - Historical trades for timeframe analysis
- `*.json` - Any other state files

## Important

⚠️ **These files are local to each deployment** (your laptop, VPS, etc.)

- Do NOT commit state files to git
- Each environment maintains its own state
- State persists across bot restarts
- Backup state files before major updates

## Resetting State

If you need to reset the bot state:

```bash
# Backup first
cp state/trading_state.json state/trading_state.json.backup

# Reset (bot will create fresh state on next run)
rm state/trading_state.json
```

## Initial State

On first run, the bot creates default state:
- `day_start_balance`: Current USDC balance
- `peak_balance`: Same as start balance
- `mode`: "normal"
- All counters reset to 0
