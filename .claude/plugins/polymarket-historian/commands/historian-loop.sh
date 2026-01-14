#!/bin/bash
# Start the endless profitability loop

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "🚀 Starting Endless Profitability Loop..."
echo ""
echo "This will:"
echo "  1. Collect trade data every 15 minutes"
echo "  2. Analyze patterns every hour"
echo "  3. Auto-implement improvements every 6 hours"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 scripts/profitability_loop.py "$@"
