#!/usr/bin/env python3
"""
US-RC-001: Parse and validate trade log completeness

Persona: Dr. Kenji Nakamoto (Data Forensics Specialist)
Context: "I need to ensure the data is trustworthy before anyone analyzes it.
         Missing trades or corrupted entries invalidate all downstream research."

This script parses bot.log and extracts trade information to validate completeness.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict


@dataclass
class Trade:
    """Represents a single trade from the logs."""
    timestamp: str
    crypto: str
    direction: str
    entry_price: float
    shares: float
    outcome: Optional[str] = None  # WIN, LOSS, or None if incomplete
    epoch_id: Optional[str] = None

    def is_complete(self) -> bool:
        """Check if trade has all required fields including outcome."""
        return self.outcome is not None

    def __hash__(self) -> int:
        """Hash for deduplication."""
        return hash((self.timestamp, self.crypto, self.direction, self.entry_price))


class TradeLogParser:
    """Parses bot.log files and extracts trade data."""

    # Regex patterns for log parsing
    ORDER_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*ORDER PLACED.*?'
        r'(BTC|ETH|SOL|XRP).*?(Up|Down).*?'
        r'Entry:\s*\$?([\d.]+).*?'
        r'Shares:\s*([\d.]+)',
        re.IGNORECASE
    )

    WIN_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?'
        r'(BTC|ETH|SOL|XRP).*?(Up|Down).*?WIN',
        re.IGNORECASE
    )

    LOSS_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?'
        r'(BTC|ETH|SOL|XRP).*?(Up|Down).*?LOSS',
        re.IGNORECASE
    )

    EPOCH_PATTERN = re.compile(
        r'epoch[_\s]?id[:\s]*([a-f0-9-]+)',
        re.IGNORECASE
    )

    def __init__(self, log_path: Path):
        """Initialize parser with log file path."""
        self.log_path = log_path
        self.trades: List[Trade] = []
        self.outcomes: Dict[str, str] = {}  # key: (timestamp, crypto, direction) -> outcome

    def parse(self) -> None:
        """Parse the log file and extract all trades."""
        if not self.log_path.exists():
            raise FileNotFoundError(f"Log file not found: {self.log_path}")

        with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Parse ORDER PLACED entries
        for match in self.ORDER_PATTERN.finditer(content):
            timestamp = match.group(1)
            crypto = match.group(2).upper()
            direction = match.group(3).capitalize()
            entry_price = float(match.group(4))
            shares = float(match.group(5))

            # Try to find epoch_id near this trade
            epoch_id = self._find_epoch_near_timestamp(content, timestamp)

            trade = Trade(
                timestamp=timestamp,
                crypto=crypto,
                direction=direction,
                entry_price=entry_price,
                shares=shares,
                epoch_id=epoch_id
            )
            self.trades.append(trade)

        # Parse outcomes (WIN/LOSS)
        for match in self.WIN_PATTERN.finditer(content):
            timestamp = match.group(1)
            crypto = match.group(2).upper()
            direction = match.group(3).capitalize()
            key = f"{timestamp}_{crypto}_{direction}"
            self.outcomes[key] = "WIN"

        for match in self.LOSS_PATTERN.finditer(content):
            timestamp = match.group(1)
            crypto = match.group(2).upper()
            direction = match.group(3).capitalize()
            key = f"{timestamp}_{crypto}_{direction}"
            self.outcomes[key] = "LOSS"

        # Match outcomes to trades (fuzzy matching by crypto + direction + nearby timestamp)
        self._match_outcomes()

    def _find_epoch_near_timestamp(self, content: str, timestamp: str) -> Optional[str]:
        """Find epoch_id near a given timestamp in the log."""
        # Simple approach: find epoch_id within 500 chars before/after timestamp
        idx = content.find(timestamp)
        if idx == -1:
            return None

        search_range = content[max(0, idx-500):min(len(content), idx+500)]
        match = self.EPOCH_PATTERN.search(search_range)
        return match.group(1) if match else None

    def _match_outcomes(self) -> None:
        """Match outcomes to trades using fuzzy time matching."""
        for trade in self.trades:
            # Try exact match first
            key = f"{trade.timestamp}_{trade.crypto}_{trade.direction}"
            if key in self.outcomes:
                trade.outcome = self.outcomes[key]
                continue

            # Try fuzzy match (within 15 minutes - typical epoch duration)
            trade_dt = datetime.strptime(trade.timestamp, "%Y-%m-%d %H:%M:%S")
            for outcome_key, outcome in self.outcomes.items():
                parts = outcome_key.split("_")
                if len(parts) != 3:
                    continue

                outcome_ts, outcome_crypto, outcome_dir = parts

                # Match crypto and direction
                if outcome_crypto != trade.crypto or outcome_dir != trade.direction:
                    continue

                # Check if timestamps are within 20 minutes
                try:
                    outcome_dt = datetime.strptime(outcome_ts, "%Y-%m-%d %H:%M:%S")
                    time_diff = abs((outcome_dt - trade_dt).total_seconds())
                    if time_diff <= 1200:  # 20 minutes
                        trade.outcome = outcome
                        break
                except ValueError:
                    continue

    def get_statistics(self) -> Dict:
        """Calculate statistics about the parsed trades."""
        total_trades = len(self.trades)
        complete_trades = sum(1 for t in self.trades if t.is_complete())
        incomplete_trades = total_trades - complete_trades

        # Date range
        if self.trades:
            dates = [datetime.strptime(t.timestamp, "%Y-%m-%d %H:%M:%S") for t in self.trades]
            date_range = (min(dates).date(), max(dates).date())
        else:
            date_range = (None, None)

        # Completeness by crypto
        by_crypto: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "complete": 0})
        for trade in self.trades:
            by_crypto[trade.crypto]["total"] += 1
            if trade.is_complete():
                by_crypto[trade.crypto]["complete"] += 1

        # Missing data patterns
        missing_epoch = sum(1 for t in self.trades if t.epoch_id is None)

        return {
            "total_trades": total_trades,
            "complete_trades": complete_trades,
            "incomplete_trades": incomplete_trades,
            "completeness_pct": (complete_trades / total_trades * 100) if total_trades > 0 else 0,
            "date_range": date_range,
            "by_crypto": dict(by_crypto),
            "missing_epoch_count": missing_epoch,
            "missing_epoch_pct": (missing_epoch / total_trades * 100) if total_trades > 0 else 0
        }

    def generate_report(self, output_path: Path) -> None:
        """Generate completeness report in markdown format."""
        stats = self.get_statistics()

        report = f"""# Trade Log Completeness Analysis

**Researcher:** Dr. Kenji Nakamoto (Data Forensics Specialist)
**Analysis Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Log File:** {self.log_path}

---

## Executive Summary

{self._generate_executive_summary(stats)}

---

## Detailed Statistics

### Overall Completeness

- **Total Trades:** {stats['total_trades']:,}
- **Complete Trades:** {stats['complete_trades']:,} ({stats['completeness_pct']:.1f}%)
- **Incomplete Trades:** {stats['incomplete_trades']:,}

### Date Range Coverage

- **First Trade:** {stats['date_range'][0] if stats['date_range'][0] else 'N/A'}
- **Last Trade:** {stats['date_range'][1] if stats['date_range'][1] else 'N/A'}
- **Total Days:** {(stats['date_range'][1] - stats['date_range'][0]).days + 1 if stats['date_range'][0] else 0}

### Completeness by Cryptocurrency

| Crypto | Total Trades | Complete | Incomplete | Completeness % |
|--------|--------------|----------|------------|----------------|
"""

        for crypto, data in sorted(stats['by_crypto'].items()):
            complete = data['complete']
            total = data['total']
            incomplete = total - complete
            pct = (complete / total * 100) if total > 0 else 0
            report += f"| {crypto} | {total:,} | {complete:,} | {incomplete:,} | {pct:.1f}% |\n"

        report += f"""
### Missing Data Patterns

- **Trades with Missing Epoch ID:** {stats['missing_epoch_count']:,} ({stats['missing_epoch_pct']:.1f}%)
- **Trades with Missing Outcome:** {stats['incomplete_trades']:,}

---

## Data Quality Assessment

"""

        report += self._generate_quality_assessment(stats)

        report += "\n---\n\n## Recommendations\n\n"
        report += self._generate_recommendations(stats)

        # Write report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report)

        print(f"✅ Report generated: {output_path}")

    def _generate_executive_summary(self, stats: Dict) -> str:
        """Generate executive summary based on stats."""
        completeness = stats['completeness_pct']

        if completeness >= 95:
            assessment = "**EXCELLENT** - Data is highly complete and trustworthy."
        elif completeness >= 85:
            assessment = "**GOOD** - Data is mostly complete with minor gaps."
        elif completeness >= 70:
            assessment = "**ACCEPTABLE** - Data has notable gaps but is usable with caution."
        else:
            assessment = "**POOR** - Data has significant gaps that may invalidate analysis."

        return f"""
This analysis examines **{stats['total_trades']:,} trades** spanning from **{stats['date_range'][0]}** to **{stats['date_range'][1]}**.

**Data Quality:** {assessment}

**Completeness:** {completeness:.1f}% of trades have outcome data (WIN/LOSS).
"""

    def _generate_quality_assessment(self, stats: Dict) -> str:
        """Generate quality assessment text."""
        issues = []

        if stats['completeness_pct'] < 95:
            issues.append(f"- ⚠️ **Incomplete Outcomes:** {stats['incomplete_trades']} trades missing outcome data")

        if stats['missing_epoch_pct'] > 10:
            issues.append(f"- ⚠️ **Missing Epoch IDs:** {stats['missing_epoch_count']} trades missing epoch_id ({stats['missing_epoch_pct']:.1f}%)")

        # Check per-crypto completeness
        for crypto, data in stats['by_crypto'].items():
            pct = (data['complete'] / data['total'] * 100) if data['total'] > 0 else 0
            if pct < 85:
                issues.append(f"- ⚠️ **{crypto} Incomplete:** Only {pct:.1f}% complete")

        if not issues:
            return "✅ **No significant data quality issues detected.** All metrics are within acceptable ranges.\n"

        return "**Issues Detected:**\n\n" + "\n".join(issues) + "\n"

    def _generate_recommendations(self, stats: Dict) -> str:
        """Generate recommendations based on findings."""
        recommendations = []

        if stats['completeness_pct'] < 95:
            recommendations.append(
                "1. **Investigate Missing Outcomes:** Review log entries around incomplete trades "
                "to understand why outcome data is missing. Possible causes:\n"
                "   - Trades still open (not yet resolved)\n"
                "   - Logging bugs during outcome resolution\n"
                "   - Manual redemptions not logged"
            )

        if stats['missing_epoch_pct'] > 10:
            recommendations.append(
                "2. **Fix Epoch ID Logging:** Add explicit epoch_id logging to ORDER PLACED messages "
                "to ensure every trade is tagged with its epoch."
            )

        if stats['total_trades'] < 50:
            recommendations.append(
                "3. **Insufficient Sample Size:** Current dataset has <50 trades. "
                "Statistical analysis requires ≥100 trades for meaningful conclusions."
            )

        recommendations.append(
            f"4. **Next Steps:** Proceed to US-RC-002 (duplicate detection) and US-RC-003 (balance reconciliation) "
            f"to further validate data integrity."
        )

        if not recommendations:
            recommendations.append("✅ **No immediate actions required.** Data quality is excellent.")

        return "\n\n".join(recommendations) + "\n"


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse and validate trade log completeness (US-RC-001)"
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to bot.log file"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("reports/kenji_nakamoto/trade_log_completeness.md"),
        help="Output report path (default: reports/kenji_nakamoto/trade_log_completeness.md)"
    )

    args = parser.parse_args()

    # Parse logs
    print(f"📊 Parsing trade logs from: {args.log_file}")
    parser_obj = TradeLogParser(args.log_file)

    try:
        parser_obj.parse()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error during parsing: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    # Print summary
    stats = parser_obj.get_statistics()
    print(f"\n✅ Parsed {stats['total_trades']:,} trades")
    print(f"   Complete: {stats['complete_trades']:,} ({stats['completeness_pct']:.1f}%)")
    print(f"   Incomplete: {stats['incomplete_trades']:,}")
    print(f"   Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")

    # Generate report
    parser_obj.generate_report(args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
