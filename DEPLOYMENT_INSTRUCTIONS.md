# Deployment Instructions - Dual-Track Threshold Optimization

## Track 1: Quick Win (DEPLOYED - Monitoring Phase)

**Status:** ✅ Code committed and pushed to main

**What was changed:**
- MAX_ENTRY: 0.20 → 0.12
- EARLY_MAX_ENTRY: 0.20 → 0.12  
- LATE_MAX_ENTRY: 0.25 → 0.15
- CONTRARIAN_MAX: 0.15 → 0.10

**Expected impact:**
- Avg entry: $0.19 → $0.12
- Monthly profit: $46 → $55 (+20%)

### VPS Deployment

```bash
# SSH to VPS
ssh root@216.238.85.11

# Navigate to bot directory
cd /opt/polymarket-autotrader

# Pull latest changes
git pull origin main

# Restart bot
systemctl restart polymarket-bot

# Verify bot started
systemctl status polymarket-bot

# Watch logs
tail -f bot.log | grep -E "ORDER PLACED|entry|SKIP"
```

### Monitoring (24 hours)

**Check every 6 hours:**

```bash
# Monitor entry prices
ssh root@216.238.85.11 "tail -100 /opt/polymarket-autotrader/bot.log | grep 'ORDER PLACED' | grep -oP 'entry.*?\$[\d.]+' | tail -10"

# Check trade count
ssh root@216.238.85.11 "grep -c 'ORDER PLACED' /opt/polymarket-autotrader/bot.log"

# Check win/loss ratio
ssh root@216.238.85.11 "echo 'Wins:' && grep -c 'WIN' /opt/polymarket-autotrader/bot.log && echo 'Losses:' && grep -c 'LOSS' /opt/polymarket-autotrader/bot.log"
```

**Success criteria (24 hours):**
- ✅ Avg entry < $0.15
- ✅ Win rate ≥ 58%
- ✅ At least 4-6 trades placed
- ✅ No errors or halts

**If successful:** Proceed to Track 2 (lower consensus threshold)

**If unsuccessful (avg entry still high):** 
- May need different market conditions
- Consider reverting temporarily

---

## Track 2: Full PRD (Ready to Execute)

**Status:** ⏳ Ready to run via Ralph or manual execution

**What it does:**
1. Analyzes agent vote accuracy
2. Reweights agents based on performance
3. Shadow tests 5 threshold variants (0.75, 0.78, 0.80, conditionals)
4. Collects 50+ trades per variant (4-6 hours)
5. Statistical analysis to find winner
6. Deploys optimal configuration

**Timeline:** 8-10 hours total

### Option A: Execute via Ralph

```bash
./ralph.sh PRD-threshold-optimization.md 20 2
```

### Option B: Manual execution (recommended for control)

See `PRD-threshold-optimization.md` for step-by-step user stories.

---

## Monitoring Dashboard

Created monitoring tools:

1. **Fee Optimization Analysis**
   ```bash
   python3 scripts/research/fee_optimization_analysis.py
   ```
   - Shows breakeven WR at each entry price
   - Calculates expected profit

2. **Agent Accuracy Analysis** (requires VPS logs)
   ```bash
   python3 scripts/analyze_agent_accuracy.py --source bot.log
   ```
   - Per-agent vote accuracy
   - Recommended weight adjustments

3. **Research Team Consultation**
   ```bash
   python3 scripts/consult_research_team.py --skipped 70 --current-wr 0.58
   ```
   - Simulates 9-persona research team
   - Multi-perspective recommendations

---

## Rollback Procedures

### Track 1 Rollback (if avg entry doesn't drop)

```bash
git revert 09db93f
git push origin main
ssh root@216.238.85.11 "cd /opt/polymarket-autotrader && git pull && systemctl restart polymarket-bot"
```

### Track 2 Rollback (if WR drops below 56%)

```bash
git revert <commit-hash-from-track-2>
git push origin main
# Deploy as above
```

---

## Next Phase (After 24h validation)

If Track 1 successful, deploy Track 2 Quick Win:

**US-TO-QUICK-002: Lower Consensus Threshold**

```python
# config/agent_config.py
CONSENSUS_THRESHOLD = 0.78  # Down from 0.82
MIN_CONFIDENCE = 0.60       # Down from 0.65
```

Expected: +20-30% more trades, +30-50% total profit improvement

---

**Deployment Date:** 2026-01-16 19:45 UTC
**Deployed By:** Claude (Autonomous)
**Monitoring Period:** 24-48 hours
**Next Review:** 2026-01-17 19:45 UTC
