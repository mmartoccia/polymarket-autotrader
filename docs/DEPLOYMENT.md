# Polymarket AutoTrader - VPS Deployment Guide

Deploy the trading bot to a VPS for 24/7 automated trading.

## Why VPS Deployment?

- **24/7 Uptime** - Never miss trading opportunities
- **Low Latency** - Faster market data and order execution
- **Reliability** - Dedicated resources, no local computer needed
- **Monitoring** - Run bot + dashboard simultaneously

## Server Requirements

**Minimum Specs:**
- 1 CPU core
- 1GB RAM
- 10GB storage
- Ubuntu 22.04 LTS or newer
- Stable internet connection

**Recommended Providers:**
- Vultr ($6/month) - Current deployment
- DigitalOcean ($6/month)
- Linode ($5/month)
- AWS Lightsail ($5/month)

## Initial VPS Setup

### 1. Connect to VPS

```bash
ssh root@YOUR_VPS_IP
```

### 2. Update System

```bash
apt update && apt upgrade -y
```

### 3. Install Dependencies

```bash
# Install Python 3.11+
apt install -y python3 python3-pip python3-venv git

# Verify version
python3 --version  # Should be 3.11+
```

### 4. Clone Repository

```bash
cd /opt
git clone https://github.com/mmartoccia/polymarket-autotrader.git
cd polymarket-autotrader
```

### 5. Setup Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6. Configure Environment

```bash
# Copy template
cp config/.env.example .env

# Edit with your credentials
nano .env
```

Add your wallet:
```env
POLYMARKET_WALLET=0xYourWalletAddress
POLYMARKET_PRIVATE_KEY=0xYourPrivateKey
```

⚠️ **Security:**
- Use a dedicated trading wallet
- Set file permissions: `chmod 600 .env`
- Never commit `.env` to git

### 7. Test Bot

```bash
# Run bot manually to verify setup
source venv/bin/activate
python3 bot/momentum_bot_v12.py
```

Press `Ctrl+C` to stop after verifying it starts correctly.

## Systemd Service Setup

### 1. Create Service File

```bash
nano /etc/systemd/system/polymarket-bot.service
```

Add this content:
```ini
[Unit]
Description=Polymarket AutoTrader
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/polymarket-autotrader
Environment="PATH=/opt/polymarket-autotrader/venv/bin"
ExecStart=/opt/polymarket-autotrader/venv/bin/python3 /opt/polymarket-autotrader/bot/momentum_bot_v12.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/polymarket-autotrader/bot.log
StandardError=append:/opt/polymarket-autotrader/bot.log

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start Service

```bash
# Reload systemd
systemctl daemon-reload

# Enable service (start on boot)
systemctl enable polymarket-bot

# Start service
systemctl start polymarket-bot

# Check status
systemctl status polymarket-bot
```

### 3. View Logs

```bash
# Live logs
tail -f /opt/polymarket-autotrader/bot.log

# Recent activity
tail -50 /opt/polymarket-autotrader/bot.log

# Systemd journal
journalctl -u polymarket-bot -f
```

## Deployment Workflow

### Update Bot on VPS

When you make changes locally and push to GitHub:

```bash
# SSH to VPS
ssh root@YOUR_VPS_IP

# Navigate to repo
cd /opt/polymarket-autotrader

# Run deployment script
./scripts/deploy.sh
```

The deploy script will:
1. Pull latest changes from GitHub
2. Restart the bot service
3. Show recent logs

### Manual Deployment

If deploy script fails:

```bash
# Pull changes
git pull origin main

# Restart service
systemctl restart polymarket-bot

# Check status
systemctl status polymarket-bot

# View logs
tail -f bot.log
```

## Monitoring

### Dashboard Access

Run dashboard in a screen session:

```bash
# Create screen session
screen -S dashboard

# Activate venv and run dashboard
cd /opt/polymarket-autotrader
source venv/bin/activate
python3 dashboard/live_dashboard.py

# Detach: Ctrl+A, then D
# Reattach: screen -r dashboard
```

### SSH from Local Machine

Monitor dashboard from your laptop:

```bash
ssh root@YOUR_VPS_IP "cd /opt/polymarket-autotrader && python3 dashboard/live_dashboard.py"
```

### Service Management

```bash
# Start bot
systemctl start polymarket-bot

# Stop bot
systemctl stop polymarket-bot

# Restart bot
systemctl restart polymarket-bot

# Check status
systemctl status polymarket-bot

# View logs
journalctl -u polymarket-bot -n 50
```

## Maintenance

### Update Dependencies

```bash
cd /opt/polymarket-autotrader
source venv/bin/activate
pip install --upgrade -r requirements.txt
systemctl restart polymarket-bot
```

### Backup State

```bash
# Create backup
cp state/trading_state.json state/backup_$(date +%Y%m%d).json

# Restore backup
cp state/backup_20260113.json state/trading_state.json
systemctl restart polymarket-bot
```

### Reset State

If bot gets stuck in HALTED mode:

```bash
# Backup current state
cp state/trading_state.json state/backup.json

# Reset peak_balance to current balance
python3 << 'EOF'
import json

with open('state/trading_state.json', 'r') as f:
    state = json.load(f)

# Reset peak to current
state['peak_balance'] = state['current_balance']

with open('state/trading_state.json', 'w') as f:
    json.dump(state, f, indent=2)

print(f"Peak reset to ${state['peak_balance']:.2f}")
EOF

# Restart bot
systemctl restart polymarket-bot
```

## Security Best Practices

### Firewall Setup

```bash
# Install UFW
apt install -y ufw

# Allow SSH
ufw allow 22/tcp

# Enable firewall
ufw enable
```

### SSH Key Authentication

```bash
# On your local machine, create SSH key
ssh-keygen -t ed25519 -C "polymarket-vps"

# Copy to VPS
ssh-copy-id root@YOUR_VPS_IP

# Disable password authentication
nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
systemctl restart sshd
```

### File Permissions

```bash
cd /opt/polymarket-autotrader

# Protect environment file
chmod 600 .env

# Protect state directory
chmod 700 state/
```

## Troubleshooting

### Bot Not Starting

```bash
# Check service status
systemctl status polymarket-bot

# View full logs
journalctl -u polymarket-bot -n 100

# Check for errors
tail -100 bot.log | grep -i error
```

### Connection Issues

```bash
# Test API connectivity
curl https://clob.polymarket.com

# Test Polygon RPC
curl -X POST https://polygon-rpc.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### Service Won't Restart

```bash
# Kill any hung processes
pkill -f momentum_bot_v12.py

# Clear stale PID files if any
rm -f /var/run/polymarket-bot.pid

# Restart service
systemctl restart polymarket-bot
```

## Rollback

If an update breaks the bot:

```bash
cd /opt/polymarket-autotrader

# View commit history
git log --oneline -10

# Rollback to previous version
git checkout HEAD~1

# Restart bot
systemctl restart polymarket-bot

# If works, stay on this version
# If not, roll forward: git checkout main
```

## Monitoring Alerts (Optional)

### Email on Halt

Add to systemd service:

```ini
[Service]
OnFailure=email-alert@%n.service
```

Create email service (requires mail setup).

### Uptime Monitoring

Use external monitoring:
- UptimeRobot (free)
- Pingdom
- Healthchecks.io

Monitor bot by checking log timestamps.

## Cost Estimates

**Monthly Costs:**
- VPS: $5-10/month
- Gas fees: ~$0.10-0.20 per trade
- Total: ~$10-15/month

**Break-even:** Bot needs ~$15/month profit to cover costs.

At current performance (+$154/day), costs are negligible.

## Next Steps

1. Deploy to VPS using this guide
2. Monitor for 24 hours
3. Set up automatic backups
4. Configure alerting
5. Review and optimize strategy parameters

## Support

- Issues: https://github.com/mmartoccia/polymarket-autotrader/issues
- Always test changes locally before deploying to VPS
- Keep state backups before major updates
