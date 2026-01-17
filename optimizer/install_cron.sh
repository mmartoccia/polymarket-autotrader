#!/bin/bash
#
# install_cron.sh - Install Optimizer hourly cron job on VPS
#
# This script sets up an hourly cron job that runs the Optimizer system.
# The Optimizer analyzes trading performance and auto-tunes parameters.
#
# Usage:
#   ./optimizer/install_cron.sh
#
# The cron job will run at the top of every hour (XX:00).
# Output is logged to optimizer/cron.log.
#
# Requirements:
#   - Must be run on the VPS (not locally)
#   - Python venv must exist at /opt/polymarket-autotrader/venv
#   - Optimizer module must be present at /opt/polymarket-autotrader/optimizer
#

set -e

# Configuration
BOT_DIR="/opt/polymarket-autotrader"
PYTHON_PATH="$BOT_DIR/venv/bin/python3"
OPTIMIZER_SCRIPT="$BOT_DIR/optimizer/optimizer.py"
LOG_FILE="$BOT_DIR/optimizer/cron.log"
CRON_SCHEDULE="0 * * * *"  # Every hour at minute 0

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Optimizer Cron Job Installer"
echo "========================================"

# Check if running on VPS
if [ ! -d "$BOT_DIR" ]; then
    echo -e "${RED}ERROR: Bot directory not found at $BOT_DIR${NC}"
    echo "This script must be run on the VPS, not locally."
    exit 1
fi

# Check Python venv exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${RED}ERROR: Python venv not found at $PYTHON_PATH${NC}"
    echo "Please ensure the virtual environment is set up."
    exit 1
fi

# Check optimizer script exists
if [ ! -f "$OPTIMIZER_SCRIPT" ]; then
    echo -e "${RED}ERROR: Optimizer script not found at $OPTIMIZER_SCRIPT${NC}"
    echo "Please ensure the optimizer module is deployed."
    exit 1
fi

# Define the cron command
CRON_COMMAND="cd $BOT_DIR && $PYTHON_PATH optimizer/optimizer.py >> optimizer/cron.log 2>&1"
CRON_ENTRY="$CRON_SCHEDULE $CRON_COMMAND"

# Check if cron entry already exists
EXISTING=$(crontab -l 2>/dev/null | grep -F "optimizer/optimizer.py" || true)

if [ -n "$EXISTING" ]; then
    echo -e "${YELLOW}WARNING: Optimizer cron entry already exists:${NC}"
    echo "  $EXISTING"
    echo ""
    read -p "Do you want to replace it? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove existing entry
        crontab -l 2>/dev/null | grep -v -F "optimizer/optimizer.py" | crontab -
        echo "Removed existing entry."
    else
        echo "Installation cancelled."
        exit 0
    fi
fi

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo -e "${GREEN}SUCCESS: Cron job installed!${NC}"
echo ""
echo "Details:"
echo "  Schedule: Every hour at minute 0 (XX:00)"
echo "  Command:  $PYTHON_PATH optimizer/optimizer.py"
echo "  Log file: $LOG_FILE"
echo ""

# Verify installation
echo "Verifying installation..."
VERIFY=$(crontab -l 2>/dev/null | grep -F "optimizer/optimizer.py" || true)
if [ -n "$VERIFY" ]; then
    echo -e "${GREEN}✓ Cron entry verified:${NC}"
    echo "  $VERIFY"
else
    echo -e "${RED}✗ Cron entry not found - installation may have failed${NC}"
    exit 1
fi

# Create/touch log file to ensure it exists
touch "$LOG_FILE"
echo ""
echo "Log file created at: $LOG_FILE"

# Show current crontab
echo ""
echo "Current crontab:"
echo "----------------------------------------"
crontab -l 2>/dev/null || echo "(empty)"
echo "----------------------------------------"

echo ""
echo "The optimizer will run at the next hour mark."
echo "To test immediately, run:"
echo "  cd $BOT_DIR && $PYTHON_PATH optimizer/optimizer.py --dry-run"
echo ""
echo "To view logs:"
echo "  tail -f $LOG_FILE"
