# Polymarket Historian Setup Guide

## Quick Start

### 1. Verify Installation

The historian plugin is already installed. Check it:

```bash
ls -la .claude/plugins/polymarket-historian/
```

You should see:
- `commands/` - Plugin commands
- `scripts/` - Python analysis scripts
- `data/` - Will be created on first run
- `README.md` - Full documentation
- `PROFITABILITY_LOOP.md` - Loop documentation

### 2. Set Environment Variables

The historian needs access to your VPS:

```bash
# Add to .env or export manually
export VPS_IP="216.238.85.11"
export SSH_KEY="~/.ssh/polymarket_vultr"
export POLYMARKET_WALLET="0x52dF6Dc5DE31DD844d9E432A0821BC86924C2237"
```

### 3. Test Data Collection

Collect your first snapshot:

```bash
python3 .claude/plugins/polymarket-historian/scripts/collect_snapshot.py
```

Expected output:
```
======================================================================
POLYMARKET HISTORIAN - DATA COLLECTION
======================================================================

Collecting snapshot...

SNAPSHOT SUMMARY:
  Timestamp: 2026-01-14T10:45:00Z
  Balance: $39.41
  Active Positions: 4
  Recent Trades: 12
  Mode: RECOVERY

✅ Snapshot saved: .claude/plugins/polymarket-historian/data/snapshots/2026-01-14_10-45-00.json
✅ Daily aggregate updated: .claude/plugins/polymarket-historian/data/daily/2026-01-14.json
```

### 4. Analyze Patterns (After ~50 Trades)

Once you have data:

```bash
python3 .claude/plugins/polymarket-historian/scripts/analyze_patterns.py
```

Expected output:
```
======================================================================
POLYMARKET HISTORIAN - PATTERN ANALYSIS
======================================================================

Loading snapshots...
  Loaded 24 snapshots

Extracting trades...
  Found 53 trades

Analyzing patterns...
  ✅ Patterns saved
  ✅ Recommendations saved
  ✅ Report saved

ANALYSIS COMPLETE
Total Trades: 53
Strategies Identified: 4
Recommendations: 3

📄 Full report: .claude/plugins/polymarket-historian/data/insights/latest_report.md

TOP RECOMMENDATIONS:
  1. Increase SOL late position multiplier by 20%
  2. Reduce BTC position sizes by 30% or disable temporarily
  3. Enable time-of-day multipliers (boost 2am-6am UTC)
```

### 5. Start Endless Profitability Loop

**Option A: Foreground (for testing)**
```bash
python3 .claude/plugins/polymarket-historian/scripts/profitability_loop.py --once
```

**Option B: Background (production)**
```bash
# Start loop
nohup python3 .claude/plugins/polymarket-historian/scripts/profitability_loop.py > historian_loop.log 2>&1 &

# Save PID
echo $! > historian_loop.pid

# View logs
tail -f historian_loop.log
```

**Option C: VPS Service (recommended)**

Create systemd service on VPS:

```bash
# SSH to VPS
ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11

# Create service file
cat > /etc/systemd/system/polymarket-historian.service << 'EOF'
[Unit]
Description=Polymarket Historian - Profitability Loop
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/polymarket-autotrader
Environment="PATH=/opt/polymarket-autotrader/venv/bin"
ExecStart=/opt/polymarket-autotrader/venv/bin/python3 .claude/plugins/polymarket-historian/scripts/profitability_loop.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl enable polymarket-historian
systemctl start polymarket-historian

# Check status
systemctl status polymarket-historian
```

## Using with Claude Code

### Available Commands

Once the plugin is installed, you can use:

```bash
# Collect snapshot
/historian-collect

# Analyze patterns
/historian-patterns

# Start endless loop
/historian-loop

# Check loop status
/historian-loop --status

# Run single cycle (testing)
/historian-loop --once
```

### Auto-Collection Hook

The historian can auto-collect data after certain actions.

Create post-task hook (optional):

```bash
cat > .claude/plugins/polymarket-historian/hooks/post-task-collect.sh << 'EOF'
#!/bin/bash
# Auto-collect data after task completion

echo "📊 Auto-collecting trading data..."
python3 .claude/plugins/polymarket-historian/scripts/collect_snapshot.py
EOF

chmod +x .claude/plugins/polymarket-historian/hooks/post-task-collect.sh
```

Now data will be collected automatically after every `/commit`, `/deploy`, or Task completion.

## Monitoring

### View Loop Status

```bash
# Check if running
ps aux | grep profitability_loop

# View logs
tail -f historian_loop.log

# View loop state
cat .claude/plugins/polymarket-historian/data/loop_state.json
```

### View Latest Insights

```bash
# Latest analysis
cat .claude/plugins/polymarket-historian/data/insights/latest_report.md

# Latest recommendations
cat .claude/plugins/polymarket-historian/data/patterns/recommendations.json | jq .

# Recent improvements
cat .claude/plugins/polymarket-historian/data/improvements/*.json | jq .
```

### Check Data Collection

```bash
# Count snapshots
ls .claude/plugins/polymarket-historian/data/snapshots/ | wc -l

# View latest snapshot
cat .claude/plugins/polymarket-historian/data/snapshots/*.json | tail -1 | jq .

# View daily summary
cat .claude/plugins/polymarket-historian/data/daily/$(date +%Y-%m-%d).json | jq .summary
```

## Troubleshooting

### No snapshots collected

**Problem:** `historian-collect` fails with connection error

**Solution:**
1. Check VPS is accessible: `ssh -i ~/.ssh/polymarket_vultr root@216.238.85.11`
2. Verify environment variables are set
3. Check bot is running: `systemctl status polymarket-bot`

### Not enough trades for analysis

**Problem:** `historian-patterns` says "Not enough trades"

**Solution:**
- Wait for more trades (need ~50 for meaningful analysis)
- Let bot trade for 12-24 hours
- Check bot is actually placing trades (not halted)

### Loop not making improvements

**Problem:** Loop runs but no improvements generated

**Possible causes:**
1. Not enough data yet (need 50+ trades)
2. Win rate too low (<55%) - safety check
3. Already made 3 improvements today (daily limit)
4. No patterns with high confidence (20+ trades)

**Solution:** Let it collect more data. First improvement typically after 24-48 hours.

### Improvements not taking effect

**Problem:** Loop implements change but bot behavior unchanged

**Solution:**
1. Check `state/ralph_overrides.json` was updated
2. Restart bot: `systemctl restart polymarket-bot`
3. Verify bot loads overrides: `grep "Ralph overrides" bot.log`

## Data Retention

### Automatic Cleanup

By default, the historian keeps:
- All daily aggregates (indefinitely)
- Last 7 days of snapshots
- All improvement records

### Manual Cleanup

```bash
# Remove old snapshots (keep last 7 days)
find .claude/plugins/polymarket-historian/data/snapshots/ -type f -mtime +7 -delete

# Archive old data
tar -czf historian_archive_$(date +%Y%m).tar.gz .claude/plugins/polymarket-historian/data/
```

## Performance Impact

**CPU:** Minimal (~1-2% during collection/analysis)
**Memory:** ~50MB for data, ~100MB during analysis
**Disk:** ~1MB per day of snapshots (~30MB per month)
**Network:** Negligible (SSH + API calls every 15 min)

The historian is designed to run alongside the bot without impacting trading performance.

## Safety

### What the Historian Changes

**SAFE (Auto-implemented):**
- Writes to `state/ralph_overrides.json`
- Adjusts position sizing multipliers
- Changes entry/exit thresholds
- Enables/disables specific strategies

**NEVER TOUCHES:**
- Core bot code (`momentum_bot_v12.py`)
- Agent code (`agents/*.py`)
- Wallet private key
- Critical safety limits (MAX_DRAWDOWN, etc.)

### Rollback

To undo all improvements:

```bash
# Remove overrides
rm state/ralph_overrides.json

# Restart bot
systemctl restart polymarket-bot
```

Bot will revert to baseline configuration.

### Emergency Stop

To stop the historian completely:

```bash
# Kill loop
pkill -f profitability_loop

# Or with PID file
kill $(cat historian_loop.pid)

# Remove overrides
rm state/ralph_overrides.json

# Restart bot
systemctl restart polymarket-bot
```

## Next Steps

After setup:

1. ✅ Let data collect for 24 hours
2. ✅ Review first analysis report
3. ✅ Start profitability loop
4. ✅ Monitor improvements for 7 days
5. ✅ Review monthly report
6. ✅ Adjust safety parameters if needed

**The historian learns over time. The longer it runs, the better it gets.**

## Support

For issues or questions:
- Check README.md for detailed documentation
- Check PROFITABILITY_LOOP.md for loop details
- Review logs: `historian_loop.log`
- File issue in GitHub repo

---

**Remember:** The historian is a tool for data-driven optimization. Always review recommendations before implementing major strategy changes manually.
