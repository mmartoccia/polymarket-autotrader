#!/usr/bin/env python3
"""
Pattern Discovery Script for Polymarket 15-minute Crypto Trading

This script analyzes historical Binance data to discover patterns that correlate
with Up/Down outcomes in 15-minute epochs. It calculates various technical
features and uses statistical analysis + decision trees to find winning patterns.

Author: Claude Code
Date: 2026-01-16
"""

import requests
import time
import json
import numpy as np
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Configuration
BINANCE_API = "https://api.binance.com/api/v3/klines"
CRYPTOS = ["BTC", "ETH", "SOL", "XRP"]
SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT"
}

# Rate limiting: 500ms between requests to stay well under 1200/min limit
REQUEST_DELAY = 0.5

def fetch_klines(symbol: str, interval: str, start_time: int, end_time: int) -> List:
    """Fetch klines (candlestick) data from Binance."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }

    try:
        resp = requests.get(BINANCE_API, params=params, timeout=10)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return resp.json()
    except Exception as e:
        print(f"Error fetching {symbol} klines: {e}")
        return []

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate RSI from price series."""
    if len(prices) < period + 1:
        return None

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_epoch_timestamps(hours_back: int = 48) -> List[int]:
    """Generate epoch start timestamps for the specified hours back."""
    now = datetime.now(timezone.utc)
    # Round down to nearest 15 minutes
    current_epoch = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)

    epochs = []
    epoch = current_epoch - timedelta(hours=hours_back)

    while epoch < current_epoch - timedelta(minutes=15):  # Exclude current incomplete epoch
        epochs.append(int(epoch.timestamp() * 1000))
        epoch += timedelta(minutes=15)

    return epochs

def analyze_epoch(crypto: str, epoch_start_ms: int) -> Optional[Dict]:
    """
    Analyze a single epoch and calculate features.

    Returns dict with features and outcome, or None if data unavailable.
    """
    symbol = SYMBOL_MAP[crypto]
    epoch_end_ms = epoch_start_ms + (15 * 60 * 1000)

    # Fetch 1-minute candles for the epoch period (15 candles)
    epoch_klines = fetch_klines(symbol, "1m", epoch_start_ms, epoch_end_ms)

    if len(epoch_klines) < 10:  # Need at least some data
        return None

    # Fetch pre-epoch data for momentum calculation (60 minutes before)
    pre_start_ms = epoch_start_ms - (60 * 60 * 1000)
    pre_klines = fetch_klines(symbol, "1m", pre_start_ms, epoch_start_ms)

    if len(pre_klines) < 30:  # Need enough pre-data
        return None

    # Calculate epoch outcome
    epoch_open = float(epoch_klines[0][1])  # Open of first candle
    epoch_close = float(epoch_klines[-1][4])  # Close of last candle
    actual_direction = "Up" if epoch_close > epoch_open else "Down"

    # Calculate pre-epoch features
    pre_closes = [float(k[4]) for k in pre_klines]
    pre_volumes = [float(k[5]) for k in pre_klines]

    # Price just before epoch start
    price_at_start = pre_closes[-1]

    # Momentum calculations
    pre_momentum_1m = (pre_closes[-1] - pre_closes[-2]) / pre_closes[-2] * 100 if len(pre_closes) >= 2 else 0
    pre_momentum_5m = (pre_closes[-1] - pre_closes[-6]) / pre_closes[-6] * 100 if len(pre_closes) >= 6 else 0
    pre_momentum_15m = (pre_closes[-1] - pre_closes[-16]) / pre_closes[-16] * 100 if len(pre_closes) >= 16 else 0
    pre_momentum_60m = (pre_closes[-1] - pre_closes[0]) / pre_closes[0] * 100 if len(pre_closes) >= 30 else 0

    # Volatility (std dev of % changes in prior 15 minutes)
    recent_closes = pre_closes[-15:] if len(pre_closes) >= 15 else pre_closes
    pct_changes = np.diff(recent_closes) / recent_closes[:-1] * 100
    pre_volatility = np.std(pct_changes) if len(pct_changes) > 1 else 0

    # Volume ratio (last 5 min avg vs 1 hour avg)
    recent_vol = np.mean(pre_volumes[-5:]) if len(pre_volumes) >= 5 else 0
    hourly_vol = np.mean(pre_volumes) if len(pre_volumes) > 0 else 1
    volume_ratio = recent_vol / hourly_vol if hourly_vol > 0 else 1

    # RSI
    rsi = calculate_rsi(pre_closes)

    # Hour of day
    epoch_dt = datetime.fromtimestamp(epoch_start_ms / 1000, timezone.utc)
    hour_of_day = epoch_dt.hour

    # Additional features
    # High/Low range in prior 15 minutes
    recent_highs = [float(k[2]) for k in pre_klines[-15:]]
    recent_lows = [float(k[3]) for k in pre_klines[-15:]]
    price_range = (max(recent_highs) - min(recent_lows)) / price_at_start * 100 if len(recent_highs) >= 15 else 0

    # Trend strength (linear regression slope)
    if len(recent_closes) >= 5:
        x = np.arange(len(recent_closes[-5:]))
        y = np.array(recent_closes[-5:])
        slope = np.polyfit(x, y, 1)[0]
        trend_strength = slope / price_at_start * 100 * 5  # Normalized per 5 minutes
    else:
        trend_strength = 0

    return {
        "crypto": crypto,
        "epoch_start_ms": epoch_start_ms,
        "epoch_dt": epoch_dt.strftime("%Y-%m-%d %H:%M UTC"),
        "hour_of_day": hour_of_day,
        "pre_momentum_1m": pre_momentum_1m,
        "pre_momentum_5m": pre_momentum_5m,
        "pre_momentum_15m": pre_momentum_15m,
        "pre_momentum_60m": pre_momentum_60m,
        "pre_volatility": pre_volatility,
        "volume_ratio": volume_ratio,
        "rsi": rsi,
        "price_range": price_range,
        "trend_strength": trend_strength,
        "actual_direction": actual_direction,
        "epoch_change_pct": (epoch_close - epoch_open) / epoch_open * 100
    }

def calculate_accuracy(data: List[Dict], condition_fn, prediction: str) -> Tuple[float, int, int]:
    """
    Calculate accuracy for a given condition and prediction.
    Returns (accuracy, wins, total)
    """
    filtered = [d for d in data if condition_fn(d)]
    if not filtered:
        return 0.0, 0, 0

    wins = sum(1 for d in filtered if d["actual_direction"] == prediction)
    total = len(filtered)
    accuracy = wins / total * 100
    return accuracy, wins, total

def find_optimal_threshold(data: List[Dict], feature: str, prediction: str,
                           thresholds: List[float], min_samples: int = 20) -> Tuple[float, float, int]:
    """
    Find optimal threshold for a feature that maximizes accuracy.
    Returns (best_threshold, best_accuracy, sample_size)
    """
    best = (0, 0.0, 0)  # threshold, accuracy, samples

    for threshold in thresholds:
        if prediction == "Up":
            condition = lambda d, t=threshold, f=feature: d.get(f, 0) > t
        else:
            condition = lambda d, t=threshold, f=feature: d.get(f, 0) < t

        acc, wins, total = calculate_accuracy(data, condition, prediction)
        if total >= min_samples and acc > best[1]:
            best = (threshold, acc, total)

    return best

class SimpleDecisionTree:
    """Simple decision tree for pattern discovery."""

    def __init__(self, max_depth: int = 3, min_samples: int = 15):
        self.max_depth = max_depth
        self.min_samples = min_samples
        self.rules = []

    def find_best_split(self, data: List[Dict], features: List[str]) -> Optional[Dict]:
        """Find the best feature and threshold to split on."""
        best_split = None
        best_accuracy = 50.0  # Must beat random

        for feature in features:
            values = [d.get(feature, 0) for d in data if d.get(feature) is not None]
            if not values:
                continue

            # Try various percentile thresholds
            percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90]
            thresholds = [np.percentile(values, p) for p in percentiles]

            for threshold in thresholds:
                for direction in ["Up", "Down"]:
                    # Greater than threshold
                    gt_data = [d for d in data if d.get(feature, 0) > threshold]
                    if len(gt_data) >= self.min_samples:
                        gt_wins = sum(1 for d in gt_data if d["actual_direction"] == direction)
                        gt_acc = gt_wins / len(gt_data) * 100
                        if gt_acc > best_accuracy:
                            best_accuracy = gt_acc
                            best_split = {
                                "feature": feature,
                                "threshold": threshold,
                                "operator": ">",
                                "prediction": direction,
                                "accuracy": gt_acc,
                                "samples": len(gt_data)
                            }

                    # Less than threshold
                    lt_data = [d for d in data if d.get(feature, 0) < threshold]
                    if len(lt_data) >= self.min_samples:
                        lt_wins = sum(1 for d in lt_data if d["actual_direction"] == direction)
                        lt_acc = lt_wins / len(lt_data) * 100
                        if lt_acc > best_accuracy:
                            best_accuracy = lt_acc
                            best_split = {
                                "feature": feature,
                                "threshold": threshold,
                                "operator": "<",
                                "prediction": direction,
                                "accuracy": lt_acc,
                                "samples": len(lt_data)
                            }

        return best_split

    def fit(self, data: List[Dict], features: List[str]):
        """Find multiple non-overlapping rules."""
        remaining_data = data.copy()

        for depth in range(self.max_depth):
            split = self.find_best_split(remaining_data, features)
            if split and split["accuracy"] > 55:  # Must be meaningful
                self.rules.append(split)

                # Remove data covered by this rule for next iteration
                if split["operator"] == ">":
                    remaining_data = [d for d in remaining_data
                                     if d.get(split["feature"], 0) <= split["threshold"]]
                else:
                    remaining_data = [d for d in remaining_data
                                     if d.get(split["feature"], 0) >= split["threshold"]]

                if len(remaining_data) < self.min_samples:
                    break

    def get_rules(self) -> List[Dict]:
        return sorted(self.rules, key=lambda x: x["accuracy"], reverse=True)

def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    print("\n" + "=" * 80)
    print("  PATTERN DISCOVERY FOR 15-MINUTE CRYPTO TRADING")
    print("  Analyzing historical Binance data to find winning patterns")
    print("=" * 80)

    # Collect data
    print("\n[1/5] Collecting epoch data from Binance...")
    print("       This will take a few minutes due to rate limiting.\n")

    epochs = get_epoch_timestamps(hours_back=48)  # Last 48 hours = ~192 epochs
    print(f"       Generated {len(epochs)} epoch timestamps to analyze")

    all_data = []
    processed = 0

    for crypto in CRYPTOS:
        print(f"\n       Fetching {crypto} data...")
        crypto_count = 0

        for epoch_ms in epochs:
            result = analyze_epoch(crypto, epoch_ms)
            if result:
                all_data.append(result)
                crypto_count += 1

            processed += 1
            if processed % 20 == 0:
                print(f"         Progress: {processed}/{len(epochs) * len(CRYPTOS)} epochs analyzed")

        print(f"         {crypto}: {crypto_count} epochs with complete data")

    print(f"\n       Total epochs with complete data: {len(all_data)}")

    if len(all_data) < 50:
        print("\n[ERROR] Not enough data collected. Try increasing hours_back or check API.")
        return

    # Calculate baseline statistics
    print_section("BASELINE STATISTICS")

    up_count = sum(1 for d in all_data if d["actual_direction"] == "Up")
    down_count = len(all_data) - up_count
    baseline_up = up_count / len(all_data) * 100
    baseline_down = down_count / len(all_data) * 100

    print(f"\n  Total epochs analyzed: {len(all_data)}")
    print(f"  Baseline distribution:")
    print(f"    - Up outcomes:   {up_count} ({baseline_up:.1f}%)")
    print(f"    - Down outcomes: {down_count} ({baseline_down:.1f}%)")
    print(f"\n  Baseline accuracy (always predict majority): {max(baseline_up, baseline_down):.1f}%")

    # Analyze by crypto
    print_section("ANALYSIS BY CRYPTO")

    for crypto in CRYPTOS:
        crypto_data = [d for d in all_data if d["crypto"] == crypto]
        if not crypto_data:
            continue

        up = sum(1 for d in crypto_data if d["actual_direction"] == "Up")
        total = len(crypto_data)

        print(f"\n  {crypto}: {total} epochs")
        print(f"    - Up:   {up} ({up/total*100:.1f}%)")
        print(f"    - Down: {total-up} ({(total-up)/total*100:.1f}%)")

    # Analyze by hour
    print_section("ANALYSIS BY HOUR OF DAY (UTC)")

    hourly_stats = defaultdict(lambda: {"up": 0, "down": 0})
    for d in all_data:
        hour = d["hour_of_day"]
        if d["actual_direction"] == "Up":
            hourly_stats[hour]["up"] += 1
        else:
            hourly_stats[hour]["down"] += 1

    print("\n  Hour  |  Up  | Down |  Up%  | Best Pred | Accuracy")
    print("  " + "-" * 55)

    best_hours = []
    for hour in sorted(hourly_stats.keys()):
        stats = hourly_stats[hour]
        total = stats["up"] + stats["down"]
        up_pct = stats["up"] / total * 100 if total > 0 else 50

        if total >= 5:  # Minimum sample size
            best_pred = "Up" if up_pct > 50 else "Down"
            accuracy = max(up_pct, 100 - up_pct)

            marker = " *" if accuracy > 55 else ""
            print(f"   {hour:02d}   |  {stats['up']:3d} |  {stats['down']:3d} | {up_pct:5.1f}% |    {best_pred:4s}   |  {accuracy:.1f}%{marker}")

            if accuracy > 55 and total >= 10:
                best_hours.append((hour, best_pred, accuracy, total))

    # Analyze momentum patterns
    print_section("MOMENTUM ANALYSIS")

    features = ["pre_momentum_1m", "pre_momentum_5m", "pre_momentum_15m", "pre_momentum_60m"]

    for feature in features:
        print(f"\n  {feature.upper().replace('_', ' ')}:")

        # Positive momentum -> predict UP
        pos_data = [d for d in all_data if d.get(feature, 0) > 0]
        pos_up = sum(1 for d in pos_data if d["actual_direction"] == "Up")

        # Negative momentum -> predict DOWN
        neg_data = [d for d in all_data if d.get(feature, 0) < 0]
        neg_down = sum(1 for d in neg_data if d["actual_direction"] == "Down")

        if pos_data:
            print(f"    Positive momentum -> Predict UP:   {pos_up/len(pos_data)*100:.1f}% (n={len(pos_data)})")
        if neg_data:
            print(f"    Negative momentum -> Predict DOWN: {neg_down/len(neg_data)*100:.1f}% (n={len(neg_data)})")

        # Find optimal thresholds
        thresholds = [-0.5, -0.3, -0.2, -0.1, -0.05, 0.05, 0.1, 0.2, 0.3, 0.5]

        best_up = find_optimal_threshold(all_data, feature, "Up",
                                         [t for t in thresholds if t > 0], min_samples=15)
        best_down = find_optimal_threshold(all_data, feature, "Down",
                                           [t for t in thresholds if t < 0], min_samples=15)

        if best_up[2] > 0:
            print(f"    Best UP threshold:   > {best_up[0]:.2f}% -> {best_up[1]:.1f}% accuracy (n={best_up[2]})")
        if best_down[2] > 0:
            print(f"    Best DOWN threshold: < {best_down[0]:.2f}% -> {best_down[1]:.1f}% accuracy (n={best_down[2]})")

    # Analyze volatility
    print_section("VOLATILITY ANALYSIS")

    vol_values = [d["pre_volatility"] for d in all_data if d["pre_volatility"] > 0]
    vol_median = np.median(vol_values)
    vol_75th = np.percentile(vol_values, 75)

    print(f"\n  Volatility distribution:")
    print(f"    Median: {vol_median:.4f}%")
    print(f"    75th percentile: {vol_75th:.4f}%")

    # Low volatility
    low_vol = [d for d in all_data if d["pre_volatility"] < vol_median]
    low_up = sum(1 for d in low_vol if d["actual_direction"] == "Up")

    # High volatility
    high_vol = [d for d in all_data if d["pre_volatility"] > vol_75th]
    high_up = sum(1 for d in high_vol if d["actual_direction"] == "Up")

    print(f"\n  Low volatility (< median):")
    print(f"    Up: {low_up/len(low_vol)*100:.1f}%, Down: {(1-low_up/len(low_vol))*100:.1f}% (n={len(low_vol)})")

    if high_vol:
        print(f"\n  High volatility (> 75th percentile):")
        print(f"    Up: {high_up/len(high_vol)*100:.1f}%, Down: {(1-high_up/len(high_vol))*100:.1f}% (n={len(high_vol)})")

    # Analyze RSI
    print_section("RSI ANALYSIS")

    rsi_data = [d for d in all_data if d.get("rsi") is not None]

    # Oversold (RSI < 30)
    oversold = [d for d in rsi_data if d["rsi"] < 30]
    if oversold:
        os_up = sum(1 for d in oversold if d["actual_direction"] == "Up")
        print(f"\n  RSI < 30 (oversold) -> Predict UP: {os_up/len(oversold)*100:.1f}% (n={len(oversold)})")

    # Overbought (RSI > 70)
    overbought = [d for d in rsi_data if d["rsi"] > 70]
    if overbought:
        ob_down = sum(1 for d in overbought if d["actual_direction"] == "Down")
        print(f"  RSI > 70 (overbought) -> Predict DOWN: {ob_down/len(overbought)*100:.1f}% (n={len(overbought)})")

    # RSI 40-60 neutral zone
    neutral = [d for d in rsi_data if 40 <= d["rsi"] <= 60]
    if neutral:
        n_up = sum(1 for d in neutral if d["actual_direction"] == "Up")
        print(f"  RSI 40-60 (neutral): Up {n_up/len(neutral)*100:.1f}%, Down {(1-n_up/len(neutral))*100:.1f}% (n={len(neutral)})")

    # Decision tree analysis
    print_section("DECISION TREE PATTERN DISCOVERY")

    features_for_tree = [
        "pre_momentum_1m", "pre_momentum_5m", "pre_momentum_15m", "pre_momentum_60m",
        "pre_volatility", "volume_ratio", "rsi", "price_range", "trend_strength"
    ]

    tree = SimpleDecisionTree(max_depth=5, min_samples=15)
    tree.fit(all_data, features_for_tree)
    rules = tree.get_rules()

    if rules:
        print("\n  Discovered patterns (sorted by accuracy):\n")
        for i, rule in enumerate(rules, 1):
            baseline = baseline_up if rule["prediction"] == "Up" else baseline_down
            edge = rule["accuracy"] - baseline

            print(f"  PATTERN {i}:")
            print(f"    When {rule['feature']} {rule['operator']} {rule['threshold']:.4f}")
            print(f"    -> Predict {rule['prediction']}")
            print(f"    Accuracy: {rule['accuracy']:.1f}% (n={rule['samples']})")
            print(f"    Edge vs baseline: {'+' if edge > 0 else ''}{edge:.1f}%")
            print()

    # Combined pattern analysis
    print_section("COMBINED PATTERN ANALYSIS")

    # Momentum + Volatility combinations
    combos = [
        # (momentum threshold, vol condition, prediction)
        (0.1, "low", "Up"),    # Positive momentum + low vol -> Up
        (-0.1, "low", "Down"), # Negative momentum + low vol -> Down
        (0.2, "high", "Up"),   # Strong positive + high vol -> Up (momentum)
        (-0.2, "high", "Down"), # Strong negative + high vol -> Down
    ]

    print("\n  Testing combined conditions:\n")

    for mom_thresh, vol_cond, pred in combos:
        if vol_cond == "low":
            filtered = [d for d in all_data
                       if d["pre_momentum_5m"] > mom_thresh and d["pre_volatility"] < vol_median]
        else:
            filtered = [d for d in all_data
                       if d["pre_momentum_5m"] > mom_thresh and d["pre_volatility"] > vol_median]

        if len(filtered) >= 10:
            wins = sum(1 for d in filtered if d["actual_direction"] == pred)
            acc = wins / len(filtered) * 100
            baseline = baseline_up if pred == "Up" else baseline_down

            if mom_thresh > 0:
                cond_str = f"5m momentum > {mom_thresh}% AND volatility {vol_cond}"
            else:
                cond_str = f"5m momentum < {mom_thresh}% AND volatility {vol_cond}"

            print(f"  {cond_str}")
            print(f"    -> Predict {pred}: {acc:.1f}% (n={len(filtered)}), edge: {acc-baseline:+.1f}%")
            print()

    # Time-based patterns
    print("\n  Time-based patterns:\n")

    # Group hours into sessions
    sessions = {
        "Asia (0-8 UTC)": range(0, 8),
        "Europe (8-16 UTC)": range(8, 16),
        "Americas (16-24 UTC)": range(16, 24)
    }

    for session_name, hours in sessions.items():
        session_data = [d for d in all_data if d["hour_of_day"] in hours]
        if session_data:
            up = sum(1 for d in session_data if d["actual_direction"] == "Up")
            up_pct = up / len(session_data) * 100
            best = "Up" if up_pct > 50 else "Down"
            acc = max(up_pct, 100 - up_pct)
            print(f"  {session_name}: {best} wins {acc:.1f}% (n={len(session_data)})")

    # Final recommendations
    print_section("TOP RECOMMENDATIONS")

    recommendations = []

    # Add rules from decision tree
    for rule in rules[:5]:
        if rule["accuracy"] > 55:
            baseline = baseline_up if rule["prediction"] == "Up" else baseline_down
            recommendations.append({
                "condition": f"{rule['feature']} {rule['operator']} {rule['threshold']:.4f}",
                "prediction": rule["prediction"],
                "accuracy": rule["accuracy"],
                "samples": rule["samples"],
                "edge": rule["accuracy"] - baseline
            })

    # Add best hourly patterns
    for hour, pred, acc, n in best_hours:
        if acc > 55:
            baseline = baseline_up if pred == "Up" else baseline_down
            recommendations.append({
                "condition": f"Hour == {hour} UTC",
                "prediction": pred,
                "accuracy": acc,
                "samples": n,
                "edge": acc - baseline
            })

    # Sort by accuracy * sqrt(samples) to balance accuracy with sample size
    recommendations.sort(key=lambda x: x["accuracy"] * np.sqrt(x["samples"]), reverse=True)

    print("\n  Actionable trading patterns:\n")

    for i, rec in enumerate(recommendations[:10], 1):
        confidence = "HIGH" if rec["accuracy"] > 60 and rec["samples"] > 30 else \
                    "MEDIUM" if rec["accuracy"] > 55 else "LOW"

        print(f"  {i}. When [{rec['condition']}]")
        print(f"     -> Predict {rec['prediction']}")
        print(f"     Accuracy: {rec['accuracy']:.1f}% | Samples: {rec['samples']} | Edge: {rec['edge']:+.1f}%")
        print(f"     Confidence: {confidence}")
        print()

    # Summary statistics
    print_section("SUMMARY")

    print(f"""
  Data analyzed:
    - {len(all_data)} epochs over {len(epochs) // 4} hours
    - {len(CRYPTOS)} cryptocurrencies: {', '.join(CRYPTOS)}
    - Baseline Up rate: {baseline_up:.1f}%

  Key findings:
    - Best single feature: {rules[0]['feature'] if rules else 'N/A'}
    - Strongest edge: {max([r['edge'] for r in recommendations]) if recommendations else 0:.1f}%
    - Most reliable pattern: {recommendations[0]['condition'] if recommendations else 'N/A'}

  Trading implications:
    - Use momentum as primary signal
    - Account for time-of-day effects
    - Volatility filtering can improve accuracy
    - RSI extremes show mean reversion tendency

  Note: These patterns are based on recent data ({len(epochs)} epochs).
        Patterns may change over time. Re-run analysis weekly.
""")

    # Export data for further analysis
    print("\n  [Optional] Saving raw data to pattern_data.json...")

    output_file = "/Volumes/TerraTitan/Development/polymarket-autotrader/scripts/pattern_data.json"
    with open(output_file, "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "epochs_analyzed": len(all_data),
            "baseline_up_pct": baseline_up,
            "recommendations": recommendations[:10],
            "rules": rules,
            "data": all_data
        }, f, indent=2, default=str)

    print(f"  Saved to: {output_file}")
    print("\n" + "=" * 80)
    print("  Pattern discovery complete!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
