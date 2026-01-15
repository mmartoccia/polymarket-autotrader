#!/bin/bash
#
# Cron job to update historical epoch dataset
# Runs every hour to collect recent epoch outcomes
#
# Add to crontab:
#   0 * * * * /opt/polymarket-autotrader/analysis/cron_update_dataset.sh >> /opt/polymarket-autotrader/analysis/dataset_update.log 2>&1
#

cd /opt/polymarket-autotrader
source venv/bin/activate

python3 analysis/historical_dataset.py --update

# Optional: Generate daily summary report at midnight
HOUR=$(date +%H)
if [ "$HOUR" == "00" ]; then
    echo "Generating daily summary..."
    python3 analysis/time_of_day_analysis.py --all --days 7
    python3 analysis/mean_reversion_strategy.py --all
fi
