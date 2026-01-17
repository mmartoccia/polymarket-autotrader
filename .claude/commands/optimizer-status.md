Check Optimizer status, view history, and manage the hourly auto-tuning system.

**Optimizer** is an hourly performance review system that auto-adjusts bot parameters within safe bounds.

## Default Behavior (No Arguments)

Show last review results and current parameter values:

1. Read `optimizer/state/last_review.json` for most recent review
2. Read `optimizer/optimizer_config.json` for tunable parameter bounds
3. Display:
   - Last review timestamp and status
   - Analysis summary (trades, win rate, skip distribution)
   - Any adjustments made
   - Current parameter values from config

## Subcommands

### `history`
Show last 20 adjustments from the audit log:
1. Read `optimizer/history/adjustments.txt`
2. Display entries in reverse chronological order (newest first)
3. Each entry shows: timestamp, parameter, old -> new value, reason

### `bounds`
Display current tuning bounds from config:
1. Read `optimizer/optimizer_config.json`
2. For each tunable parameter, show:
   - File it's in (bot/intra_epoch_bot.py or config/agent_config.py)
   - Current value
   - Min/Max bounds
   - Step size
3. Also show protected parameters (never auto-adjusted)

### `run`
Manually trigger optimizer in dry-run mode (preview changes):
1. Run: `python3 optimizer/optimizer.py --dry-run`
2. Display the analysis, proposed adjustments, and what would be changed
3. No actual changes are applied

### `run --apply`
Manually trigger optimizer with changes applied:
1. Confirm with user before proceeding (this modifies config files!)
2. Run: `python3 optimizer/optimizer.py`
3. Display what changes were applied
4. Changes take effect on next bot trade cycle

## VPS Access

The optimizer runs on VPS, so use SSH to access state files:

```bash
# Read last review
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cat /opt/polymarket-autotrader/optimizer/state/last_review.json | python3 -m json.tool"

# Read adjustment history
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "tail -20 /opt/polymarket-autotrader/optimizer/history/adjustments.txt"

# Check cron status
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "crontab -l | grep optimizer"

# Run optimizer (dry-run)
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cd /opt/polymarket-autotrader && /opt/polymarket-autotrader/venv/bin/python3 optimizer/optimizer.py --dry-run"

# Run optimizer (apply changes)
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11 "cd /opt/polymarket-autotrader && /opt/polymarket-autotrader/venv/bin/python3 optimizer/optimizer.py"
```

## Tunable Parameters

| Parameter | File | Bounds | Step |
|-----------|------|--------|------|
| MAX_ENTRY_PRICE_CAP | bot/intra_epoch_bot.py | 0.35-0.65 | 0.05 |
| MIN_PATTERN_ACCURACY | bot/intra_epoch_bot.py | 0.65-0.80 | 0.01 |
| CONSENSUS_THRESHOLD | config/agent_config.py | 0.30-0.55 | 0.05 |
| MIN_CONFIDENCE | config/agent_config.py | 0.35-0.65 | 0.05 |
| EDGE_BUFFER | bot/intra_epoch_bot.py | 0.02-0.10 | 0.01 |

## Protected Parameters (Never Auto-Adjusted)

- RISK_MAX_DRAWDOWN
- RISK_DAILY_LOSS_LIMIT
- RISK_POSITION_TIERS
- Agent enable/disable flags

## Cron Schedule

Optimizer runs hourly at minute 0 via cron:
- Entry: `0 * * * * cd /opt/polymarket-autotrader && /opt/polymarket-autotrader/venv/bin/python3 optimizer/optimizer.py >> optimizer/cron.log 2>&1`
- Install: `./optimizer/install_cron.sh`
- Uninstall: `./optimizer/uninstall_cron.sh`
