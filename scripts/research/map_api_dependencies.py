#!/usr/bin/env python3
"""
API Dependency Mapper - System Reliability Analysis
Persona: Dmitri "The Hammer" Volkov (System Reliability Engineer)

Scans bot code to inventory all external API dependencies.
Identifies single points of failure, missing timeouts, and error handling gaps.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class APIEndpoint:
    """Represents an external API endpoint used by the bot."""
    name: str
    url_pattern: str
    purpose: str
    found_in_code: bool = False
    timeout_configured: bool = False
    timeout_value: Optional[float] = None
    retry_logic: bool = False
    error_handling: bool = False
    fallback_present: bool = False


def scan_for_api_usage(code_path: str, api: APIEndpoint) -> APIEndpoint:
    """
    Search code for API usage patterns.
    Updates api object with findings.
    """
    try:
        # Search for URL pattern in code
        result = subprocess.run(
            ['grep', '-r', api.url_pattern, code_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            api.found_in_code = True

            # Check for timeout parameter
            timeout_pattern = rf'{re.escape(api.url_pattern)}.*timeout\s*=\s*(\d+)'
            timeout_matches = re.findall(timeout_pattern, result.stdout, re.IGNORECASE)
            if timeout_matches:
                api.timeout_configured = True
                api.timeout_value = float(timeout_matches[0])

            # Check for retry logic
            if 'retry' in result.stdout.lower() or 'attempts' in result.stdout.lower():
                api.retry_logic = True

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Check for error handling by reading the actual bot code files
    try:
        bot_file = Path(code_path) / 'momentum_bot_v12.py'
        if bot_file.exists():
            with open(bot_file, 'r') as f:
                content = f.read()

            # If API is used, check for error handling patterns
            if api.url_pattern in content:
                # Look for try/except or status_code checks
                if 'try:' in content and 'except' in content:
                    api.error_handling = True

    except Exception:
        pass

    return api


def check_timeout_usage(code_path: str) -> Dict[str, List[str]]:
    """
    Check for requests calls with timeout parameters.
    Returns dict of {timeout_value: [code_locations]}
    """
    timeout_locations = {}

    try:
        # Search for requests.get/post with timeout
        result = subprocess.run(
            ['grep', '-rn', r'requests\.\(get\|post\|put\|delete\)', code_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                # Extract timeout value
                timeout_match = re.search(r'timeout\s*=\s*(\d+(?:\.\d+)?)', line)
                if timeout_match:
                    timeout_val = timeout_match.group(1)
                    location = line.split(':')[0] if ':' in line else 'unknown'

                    if timeout_val not in timeout_locations:
                        timeout_locations[timeout_val] = []
                    timeout_locations[timeout_val].append(location)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return timeout_locations


def check_circuit_breakers(code_path: str) -> List[Dict[str, str]]:
    """
    Search for circuit breaker patterns in code.
    Returns list of detected patterns with file locations.
    """
    patterns = []

    # Circuit breaker patterns to look for
    searches = [
        ('consecutive.*fail', 'Consecutive failure counter'),
        ('error_count', 'Error count tracking'),
        ('circuit.*breaker', 'Explicit circuit breaker'),
        ('backoff', 'Exponential backoff'),
        ('cooldown', 'Cooldown period'),
    ]

    for pattern, description in searches:
        try:
            result = subprocess.run(
                ['grep', '-rn', '-i', pattern, code_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout:
                lines = result.stdout.splitlines()
                for line in lines[:3]:  # Limit to first 3 matches per pattern
                    patterns.append({
                        'pattern': description,
                        'location': line.split(':')[0] if ':' in line else 'unknown',
                        'snippet': line.split(':', 2)[-1].strip() if line.count(':') >= 2 else ''
                    })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return patterns


def analyze_api_reliability(code_path: str) -> str:
    """
    Main analysis function. Generates comprehensive API dependency report.
    """
    # Define all known API endpoints
    apis = [
        APIEndpoint(
            name="Polymarket Gamma API",
            url_pattern="gamma-api.polymarket.com",
            purpose="Market discovery - find active 15-min Up/Down markets"
        ),
        APIEndpoint(
            name="Polymarket CLOB API",
            url_pattern="clob.polymarket.com",
            purpose="Order placement and market data"
        ),
        APIEndpoint(
            name="Polymarket Data API",
            url_pattern="data-api.polymarket.com",
            purpose="Position tracking and balance queries"
        ),
        APIEndpoint(
            name="Binance API",
            url_pattern="api.binance.com",
            purpose="BTC/ETH/SOL/XRP spot price feeds"
        ),
        APIEndpoint(
            name="Kraken API",
            url_pattern="api.kraken.com",
            purpose="Price feed confirmation (cross-exchange)"
        ),
        APIEndpoint(
            name="Coinbase API",
            url_pattern="api.coinbase.com",
            purpose="Price feed confirmation (cross-exchange)"
        ),
        APIEndpoint(
            name="Polygon RPC",
            url_pattern="polygon-rpc.com",
            purpose="Blockchain queries - balance checks, position redemption"
        ),
    ]

    # Scan for API usage
    for api in apis:
        scan_for_api_usage(code_path, api)

    # Check timeout configuration
    timeout_locations = check_timeout_usage(code_path)

    # Check for circuit breaker patterns
    circuit_breakers = check_circuit_breakers(code_path)

    # Calculate stats
    total_apis = len(apis)
    apis_found = sum(1 for api in apis if api.found_in_code)
    apis_with_timeout = sum(1 for api in apis if api.timeout_configured)
    apis_with_error_handling = sum(1 for api in apis if api.error_handling)

    # Generate report
    report = []
    report.append("# API Dependency Map - System Reliability Audit")
    report.append("")
    report.append("**Persona:** Dmitri \"The Hammer\" Volkov (System Reliability Engineer)")
    report.append("")
    report.append("## Executive Summary")
    report.append("")

    # Determine overall status
    if apis_found == 0:
        status = "UNKNOWN"
        emoji = "⚠️"
        summary = "No API usage detected (development environment). Production audit required."
    elif apis_with_timeout == apis_found and apis_with_error_handling == apis_found:
        status = "EXCELLENT"
        emoji = "🟢"
        summary = f"All {apis_found} APIs have timeout configuration and error handling."
    elif apis_with_timeout >= apis_found * 0.8:
        status = "GOOD"
        emoji = "🟡"
        summary = f"{apis_with_timeout}/{apis_found} APIs have timeouts. Minor gaps exist."
    else:
        status = "POOR"
        emoji = "🔴"
        summary = f"Only {apis_with_timeout}/{apis_found} APIs have timeouts. Critical gaps in reliability."

    report.append(f"**Status:** {emoji} {status}")
    report.append(f"**Summary:** {summary}")
    report.append("")
    report.append(f"- **Total APIs mapped:** {total_apis}")
    report.append(f"- **APIs found in code:** {apis_found}")
    report.append(f"- **APIs with timeouts:** {apis_with_timeout}")
    report.append(f"- **APIs with error handling:** {apis_with_error_handling}")
    report.append(f"- **Circuit breakers detected:** {len(circuit_breakers)}")
    report.append("")

    # API dependency table
    report.append("## API Dependency Inventory")
    report.append("")
    report.append("| API | Purpose | Found | Timeout | Error Handling | Fallback |")
    report.append("|-----|---------|-------|---------|----------------|----------|")

    for api in apis:
        found = "✅" if api.found_in_code else "❌"
        timeout = f"✅ ({api.timeout_value}s)" if api.timeout_configured else "❌"
        error = "✅" if api.error_handling else "❌"
        fallback = "✅" if api.fallback_present else "❌"

        report.append(f"| {api.name} | {api.purpose} | {found} | {timeout} | {error} | {fallback} |")

    report.append("")

    # Timeout configuration details
    report.append("## Timeout Configuration Audit")
    report.append("")

    if timeout_locations:
        report.append("**Timeout values found in code:**")
        report.append("")
        for timeout_val, locations in sorted(timeout_locations.items()):
            report.append(f"- **{timeout_val}s:** {len(locations)} occurrences")
            for loc in locations[:3]:  # Show first 3 locations
                report.append(f"  - `{loc}`")
        report.append("")
    else:
        report.append("⚠️ **No timeout values detected** (or code not accessible)")
        report.append("")

    # Circuit breaker analysis
    report.append("## Circuit Breaker Analysis")
    report.append("")

    if circuit_breakers:
        report.append(f"**Detected {len(circuit_breakers)} circuit breaker patterns:**")
        report.append("")
        for cb in circuit_breakers:
            report.append(f"- **{cb['pattern']}** in `{cb['location']}`")
            if cb['snippet']:
                report.append(f"  - Snippet: `{cb['snippet'][:80]}`")
        report.append("")
    else:
        report.append("⚠️ **No explicit circuit breaker patterns found**")
        report.append("")
        report.append("**Recommendation:** Implement circuit breakers for API resilience:")
        report.append("- Track consecutive failures per API")
        report.append("- Halt calls after N failures")
        report.append("- Exponential backoff (30s, 60s, 120s)")
        report.append("- Auto-recovery after cooldown period")
        report.append("")

    # Single points of failure
    report.append("## Single Points of Failure")
    report.append("")
    report.append("**Critical dependencies:**")
    report.append("")
    report.append("1. **Polymarket CLOB API** - Order placement")
    report.append("   - **Risk:** If down, bot cannot trade (halt required)")
    report.append("   - **Mitigation:** Timeout + error handling + halt on consecutive failures")
    report.append("")
    report.append("2. **Exchange Price Feeds** - Confluence signals")
    report.append("   - **Risk:** If all 3 down, no price data (halt required)")
    report.append("   - **Mitigation:** Use at least 2/3 exchanges (current implementation)")
    report.append("")
    report.append("3. **Polygon RPC** - Balance checks and redemptions")
    report.append("   - **Risk:** If down, cannot redeem winners or check balance")
    report.append("   - **Mitigation:** Fallback RPC endpoints (Alchemy, Infura)")
    report.append("")

    # Recommendations
    report.append("## Recommendations (Prioritized)")
    report.append("")

    if status == "POOR":
        report.append("### 🔴 CRITICAL (Implement immediately)")
        report.append("")
        report.append("1. **Add timeouts to all API calls** (currently missing)")
        report.append("   - Recommended: 5s (price feeds), 10s (orders), 15s (blockchain)")
        report.append("2. **Implement circuit breakers** (halt after 3 consecutive failures)")
        report.append("3. **Add error handling** (try/except with graceful degradation)")
        report.append("")

    if apis_found > 0:
        report.append("### 🟡 HIGH PRIORITY (Next sprint)")
        report.append("")
        report.append("1. **Implement RPC fallback chain** (polygon-rpc → Alchemy → Infura)")
        report.append("2. **Add API health monitoring** (track success rates per endpoint)")
        report.append("3. **Log API failures** (for post-mortem analysis)")
        report.append("")

    report.append("### 🟢 MEDIUM PRIORITY (Future)")
    report.append("")
    report.append("1. **Implement exponential backoff** (for transient failures)")
    report.append("2. **Add API response time tracking** (detect degradation)")
    report.append("3. **Create API dependency dashboard** (real-time monitoring)")
    report.append("")

    # Testing recommendations
    report.append("## Failure Mode Testing")
    report.append("")
    report.append("**Recommended chaos engineering tests:**")
    report.append("")
    report.append("1. **API Timeout Test**")
    report.append("   - Simulate: Slow API response (>30s)")
    report.append("   - Expected: Bot times out, logs error, skips trade")
    report.append("")
    report.append("2. **API Failure Test**")
    report.append("   - Simulate: API returns 500 error")
    report.append("   - Expected: Bot logs error, retries or halts gracefully")
    report.append("")
    report.append("3. **Total Outage Test**")
    report.append("   - Simulate: All price feeds down")
    report.append("   - Expected: Bot halts (no data = no trading)")
    report.append("")
    report.append("4. **Partial Outage Test**")
    report.append("   - Simulate: 1/3 price feeds down")
    report.append("   - Expected: Bot continues (uses 2/3 consensus)")
    report.append("")

    # Technical appendix
    report.append("## Appendix: Implementation Timeline")
    report.append("")
    report.append("**Week 1 (Critical):**")
    report.append("- Add timeouts to all API calls")
    report.append("- Implement basic circuit breakers")
    report.append("- Add try/except error handling")
    report.append("")
    report.append("**Week 2 (High Priority):**")
    report.append("- Implement RPC fallback chain")
    report.append("- Add API health monitoring")
    report.append("- Log all API failures")
    report.append("")
    report.append("**Week 3 (Testing):**")
    report.append("- Run chaos engineering tests")
    report.append("- Validate resilience improvements")
    report.append("- Document failure modes")
    report.append("")

    return "\n".join(report)


def main():
    """Main execution function."""
    # Determine code path
    code_path = '/Volumes/TerraTitan/Development/polymarket-autotrader/bot'

    if not Path(code_path).exists():
        code_path = 'bot'  # Fallback for different environments

    # Generate report
    report = analyze_api_reliability(code_path)

    # Save report
    report_dir = Path('reports/dmitri_volkov')
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / 'api_dependency_map.md'
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"✅ API dependency map generated: {report_path}")
    print(report)

    return 0


if __name__ == '__main__':
    exit(main())
