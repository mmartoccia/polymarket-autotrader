#!/bin/bash
#
# uninstall_cron.sh - Remove Optimizer hourly cron job from VPS
#
# This script removes the hourly cron job that runs the Optimizer system.
# Use this to temporarily or permanently disable hourly optimization.
#
# Usage:
#   ./optimizer/uninstall_cron.sh
#
# Note: This does not delete log files or state - only removes the cron entry.
#

set -e

# Configuration
BOT_DIR="/opt/polymarket-autotrader"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Optimizer Cron Job Uninstaller"
echo "========================================"

# Check if cron entry exists
EXISTING=$(crontab -l 2>/dev/null | grep -F "optimizer/optimizer.py" || true)

if [ -z "$EXISTING" ]; then
    echo -e "${YELLOW}No optimizer cron entry found.${NC}"
    echo ""
    echo "Current crontab:"
    echo "----------------------------------------"
    crontab -l 2>/dev/null || echo "(empty)"
    echo "----------------------------------------"
    exit 0
fi

echo "Found existing cron entry:"
echo "  $EXISTING"
echo ""

read -p "Are you sure you want to remove this cron job? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Remove the cron entry
crontab -l 2>/dev/null | grep -v -F "optimizer/optimizer.py" | crontab -

echo -e "${GREEN}SUCCESS: Cron job removed!${NC}"
echo ""

# Verify removal
VERIFY=$(crontab -l 2>/dev/null | grep -F "optimizer/optimizer.py" || true)
if [ -z "$VERIFY" ]; then
    echo -e "${GREEN}✓ Cron entry removed successfully${NC}"
else
    echo -e "${RED}✗ Cron entry still present - removal may have failed${NC}"
    exit 1
fi

echo ""
echo "Current crontab:"
echo "----------------------------------------"
crontab -l 2>/dev/null || echo "(empty)"
echo "----------------------------------------"

echo ""
echo "The optimizer will no longer run automatically."
echo ""
echo "To reinstall later, run:"
echo "  ./optimizer/install_cron.sh"
echo ""
echo "To run manually:"
echo "  cd $BOT_DIR && $BOT_DIR/venv/bin/python3 optimizer/optimizer.py"
