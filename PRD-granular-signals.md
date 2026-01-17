# PRD: Granular Signal Enhancement for Intra-Epoch Bot

## Introduction

Enhance the intra-epoch momentum bot with more granular signal detection to improve pattern accuracy and enable earlier entries. Currently the bot only tracks binary Up/Down direction per minute from a single exchange (Binance), discarding valuable information about move magnitude and cross-exchange agreement.

This enhancement adds:
1. **Price Magnitude Tracking** - Measure HOW MUCH price moved, not just direction
2. **Multi-Exchange Confluence** - Require multiple exchanges to agree on direction

Both features are toggleable via configuration constants and will be shadow-tested before enabling in live trading.

## Goals

- Improve pattern accuracy by filtering out weak signals (small moves that could reverse)
- Enable earlier entries by detecting strong momentum faster
- Add configurable magnitude thresholds (cumulative, per-minute, accuracy weighting)
- Add configurable exchange agreement requirements (2 or 3 of 3)
- Shadow test new logic against existing logic before enabling
- Maintain backward compatibility (can disable new features via config)

## User Stories

### US-GS-001: Add Configuration Constants for Granular Signals
**Description:** As a developer, I need configuration constants for all new granular signal features so they can be easily tuned and toggled.

**Acceptance Criteria:**
- [x] Add `ENABLE_MAGNITUDE_TRACKING = True` constant
- [x] Add `MIN_CUMULATIVE_MAGNITUDE = 0.008` (0.8% total move required)
- [x] Add `MIN_PER_MINUTE_MAGNITUDE = 0.002` (0.2% per minute to count)
- [x] Add `MAGNITUDE_ACCURACY_BOOST = 0.03` (3% accuracy boost for strong moves)
- [x] Add `STRONG_MOVE_THRESHOLD = 0.015` (1.5% = strong move)
- [x] Add `ENABLE_MULTI_EXCHANGE = True` constant
- [x] Add `MIN_EXCHANGES_AGREE = 2` (require 2 of 3 exchanges)
- [x] Add `EXCHANGE_SYMBOLS` dict mapping crypto to exchange symbols
- [x] Add `ENABLE_GRANULAR_SHADOW_LOG = True` for comparison logging
- [x] Constants placed in configuration section near top of file
- [x] Typecheck passes

---

### US-GS-002: Enhance Minute Candle Fetching with Magnitude Data
**Description:** As a developer, I need fetch_minute_candles to return magnitude data so we can analyze move strength.

**Acceptance Criteria:**
- [x] Modify `fetch_minute_candles()` to return list of dicts instead of strings
- [x] Each dict contains: `{"direction": "Up"/"Down", "change_pct": float, "volume": float}`
- [x] Change calculated as `(close - open) / open * 100`
- [x] Volume extracted from kline data (index 5 in Binance response)
- [x] Add helper function `get_directions_from_candles(candles)` for backward compatibility
- [x] Existing code continues to work with direction-only list
- [x] Typecheck passes

---

### US-GS-003: Add Cumulative Magnitude Check Function
**Description:** As a developer, I need a function to check if total price movement meets minimum threshold.

**Acceptance Criteria:**
- [x] Add `check_cumulative_magnitude(candles: List[dict], direction: str) -> Tuple[bool, float]`
- [x] Sums magnitude of candles matching the pattern direction
- [x] Returns `(passes_threshold, total_magnitude)`
- [x] Uses `MIN_CUMULATIVE_MAGNITUDE` constant
- [x] Returns `(True, magnitude)` if disabled via config
- [x] Includes docstring with example
- [x] Typecheck passes

---

### US-GS-004: Add Per-Minute Magnitude Check Function
**Description:** As a developer, I need a function to check if individual minute moves are meaningful (not noise).

**Acceptance Criteria:**
- [x] Add `check_per_minute_magnitude(candles: List[dict], direction: str) -> Tuple[int, int]`
- [x] Returns `(strong_count, weak_count)` for candles matching direction
- [x] "Strong" = magnitude >= `MIN_PER_MINUTE_MAGNITUDE`
- [x] Can be used to require "4 of 5 STRONG moves" vs just "4 of 5 moves"
- [x] Includes docstring with example
- [x] Typecheck passes

---

### US-GS-005: Add Magnitude-Weighted Accuracy Boost Function
**Description:** As a developer, I need a function to boost pattern accuracy based on move strength.

**Acceptance Criteria:**
- [x] Add `calculate_magnitude_boost(candles: List[dict], direction: str) -> float`
- [x] Returns accuracy boost (0.0 to `MAGNITUDE_ACCURACY_BOOST`)
- [x] Boost scales linearly with magnitude above `STRONG_MOVE_THRESHOLD`
- [x] No boost if magnitude below threshold
- [x] Max boost capped at `MAGNITUDE_ACCURACY_BOOST`
- [x] Returns 0.0 if feature disabled via config
- [x] Includes docstring with formula explanation
- [x] Typecheck passes

---

### US-GS-006: Add Multi-Exchange Price Fetcher
**Description:** As a developer, I need to fetch prices from Binance, Kraken, and Coinbase to detect confluence.

**Acceptance Criteria:**
- [x] Add `get_binance_price(symbol: str) -> Optional[float]` function
- [x] Add `get_kraken_price(symbol: str) -> Optional[float]` function
- [x] Add `get_coinbase_price(symbol: str) -> Optional[float]` function
- [x] Add `fetch_multi_exchange_prices(crypto: str) -> Dict[str, float]`
- [x] Uses ThreadPoolExecutor for parallel fetching (2-second timeout each)
- [x] Returns dict like `{"binance": 104523.50, "kraken": 104521.00, "coinbase": 104525.00}`
- [x] Handles failures gracefully (returns available prices)
- [x] Typecheck passes

---

### US-GS-007: Add Exchange Confluence Detection
**Description:** As a developer, I need to detect when multiple exchanges agree on price direction.

**Acceptance Criteria:**
- [x] Add class or module-level `epoch_start_prices: Dict[str, Dict[str, float]]` to track epoch starts
- [x] Add `record_epoch_start_prices(crypto: str, epoch: int, prices: Dict[str, float])`
- [x] Add `get_exchange_confluence(crypto: str, epoch: int) -> Tuple[Optional[str], int, float]`
- [x] Returns `(direction, agree_count, avg_change_pct)` or `(None, count, change)` if no consensus
- [x] Direction determined by comparing current prices to epoch start prices
- [x] Uses `MIN_EXCHANGES_AGREE` constant for threshold
- [x] Change threshold of 0.1% to count as Up/Down (not Flat)
- [x] Typecheck passes

---

### US-GS-008: Integrate Magnitude Checks into Pattern Analysis
**Description:** As a developer, I need analyze_pattern to use magnitude data for better accuracy.

**Acceptance Criteria:**
- [x] Modify `analyze_pattern()` to accept candle dicts (not just direction strings)
- [x] Call `check_cumulative_magnitude()` and reject if fails (when enabled)
- [x] Call `check_per_minute_magnitude()` to get strong/weak counts
- [x] Call `calculate_magnitude_boost()` and add to base accuracy
- [x] Update reason string to include magnitude info (e.g., "4/5 DOWN (-1.8%) = 77.0% accuracy")
- [x] Backward compatible: still works if passed direction strings only
- [x] Typecheck passes

---

### US-GS-009: Integrate Confluence as Entry Filter
**Description:** As a developer, I need to check exchange confluence before placing trades.

**Acceptance Criteria:**
- [x] In main loop, call `fetch_multi_exchange_prices()` at start of each scan
- [x] Call `record_epoch_start_prices()` when new epoch detected
- [x] Before placing trade, call `get_exchange_confluence()`
- [x] If `ENABLE_MULTI_EXCHANGE` and confluence direction != pattern direction, skip trade
- [x] If confluence agrees, log confirmation (e.g., "Confluence: 3/3 exchanges agree DOWN")
- [x] If confluence disagrees, log skip reason (e.g., "SKIP: Pattern=Down but only 1/3 exchanges agree")
- [x] Typecheck passes

---

### US-GS-010: Add Shadow Comparison Logging
**Description:** As a developer, I need to log comparison between old and new signal logic for analysis.

**Acceptance Criteria:**
- [x] Add `log_granular_comparison()` function
- [x] Logs: pattern direction, old accuracy, new accuracy (with boost), magnitude, confluence
- [x] Format: `[GRANULAR] BTC: Pattern=Down(74%) Magnitude=-1.8%(+3%) Confluence=2/3 -> Final=77%`
- [x] Only logs when `ENABLE_GRANULAR_SHADOW_LOG = True`
- [x] Log to separate file `granular_signals.log` for easy analysis
- [x] Include timestamp and epoch info
- [x] Typecheck passes

---

### US-GS-011: Update Startup Logs with Granular Settings
**Description:** As a developer, I need startup logs to show all new granular signal settings.

**Acceptance Criteria:**
- [ ] Add section in startup log for "Granular Signal Enhancement"
- [ ] Show magnitude tracking status and thresholds
- [ ] Show multi-exchange status and agreement requirement
- [ ] Show shadow logging status
- [ ] Format matches existing startup log style
- [ ] Example output:
  ```
  Granular Signals: ENABLED
    - Magnitude: min cumulative 0.8%, min per-minute 0.2%, boost up to 3%
    - Multi-Exchange: 2/3 required (Binance, Kraken, Coinbase)
    - Shadow Logging: ENABLED
  ```
- [ ] Typecheck passes

---

## Non-Goals

- No sub-minute sampling (stick with 1-minute candles for now)
- No volume-weighted signals (volume data collected but not used in v1)
- No Polymarket orderbook analysis
- No cross-crypto correlation signals
- No automatic parameter tuning
- No changes to position sizing based on signal strength (future enhancement)

## Technical Considerations

- **Backward Compatibility:** All features toggleable via config constants
- **Existing Code:** Port multi-exchange logic from `momentum_bot_v12.py` (lines 1253-1400)
- **API Rate Limits:** Parallel exchange fetching with 2s timeout, fail gracefully
- **Shadow Testing:** Run for minimum 50 epochs before enabling in live trading
- **File Structure:** Keep all changes in `intra_epoch_bot.py` (no new files)

## Testing Plan

1. **Unit Testing:** Each function can be tested independently with mock data
2. **Shadow Period:** Enable `ENABLE_GRANULAR_SHADOW_LOG` but keep main features disabled
3. **Analysis:** After 50+ epochs, analyze `granular_signals.log` to compare old vs new accuracy
4. **Gradual Rollout:** Enable magnitude first, then confluence, measuring impact separately

## Success Metrics

- Shadow test shows granular signals would have filtered out at least 30% of losing trades
- Accuracy boost correlates with actual win rate (stronger moves = more wins)
- Multi-exchange confluence disagreements correlate with losing trades
- No increase in latency (parallel fetching keeps scan time under 3 seconds)
