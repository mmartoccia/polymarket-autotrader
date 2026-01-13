#!/bin/bash
# Polymarket AutoTrader - VPS Deployment Script

set -e  # Exit on error

echo "======================================"
echo "Polymarket AutoTrader Deployment"
echo "======================================"

# Check if we're in the right directory
if [ ! -f "bot/momentum_bot_v12.py" ]; then
    echo "Error: Must run from polymarket-autotrader root directory"
    exit 1
fi

# Show current version
echo ""
echo "Current version:"
git log -1 --oneline

# Pull latest changes
echo ""
echo "Pulling latest changes from GitHub..."
git pull origin main

# Show new version
echo ""
echo "New version:"
git log -1 --oneline

# Restart bot service
echo ""
echo "Restarting polymarket-bot service..."
sudo systemctl restart polymarket-bot

# Wait a moment for service to start
sleep 2

# Check service status
echo ""
echo "Service status:"
sudo systemctl status polymarket-bot --no-pager | head -10

# Show recent logs
echo ""
echo "Recent bot activity:"
tail -20 bot.log

echo ""
echo "======================================"
echo "Deployment complete!"
echo "======================================"
echo ""
echo "Monitor logs with: tail -f bot.log"
