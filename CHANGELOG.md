# Changelog

All notable changes to the Screener trading system are documented here.

---

## [Unreleased] - 2025-11-16

### Fixed
- **CRITICAL**: Fixed `HistoricalDataManager.load()` method calls → `load_symbol_data()` (5 occurrences)
  - `src/screening/coarse_filter.py` (3 locations)
  - `src/screening/watchlist.py` (1 location)
  - `src/regime/regime_detector.py` (1 location)
  - Impact: Screening system could not load data - all symbols failed with "no_data" error

- **HIGH**: Fixed deprecated Dash API `app.run_server()` → `app.run()` (2 occurrences)
  - `src/main.py`
  - `src/dashboard/app.py`
  - Impact: Dashboard crashed on startup with ObsoleteAttributeException

- **HIGH**: Fixed test mocks for `historical_manager.load_symbol_data()` (11 occurrences)
  - `tests/test_coarse_filter.py`
  - Impact: 11+ screening tests failing due to incorrect mocking

### Documentation
- Archived outdated implementation docs to `docs/archive/`:
  - `SYSTEM_STATUS.md`
  - `DASHBOARD_CHARTS_IMPLEMENTATION.md`
  - `POSITIONS_PANEL_IMPLEMENTATION.md`
  - `KYMERA_THEME_IMPLEMENTATION.md`
- Created `BUG_FIXES_2025-11-16.md` for bug fix tracking
- Created this CHANGELOG.md for ongoing project history

---

## [v0.5.0] - 2025-11-15

### Added - Option 2: Dashboard & Enhancements (Complete)
- **Position Tracking Live Updates** (`src/execution/position_tracker.py`)
  - Real-time unrealized P&L calculation
  - Realized P&L on position close
  - Multi-position management with thread safety
  - 37 tests, 96% coverage

- **Dashboard Multi-Timeframe Charts** (`src/dashboard/charts.py`)
  - 5 timeframe support (5min/15min/1h/4h/1d)
  - 4 indicator panels (Price/BB, Stoch RSI, MACD, Volume)
  - Interactive zoom and pan
  - 24 tests, 94% coverage

- **Dashboard Positions Panel** (`src/dashboard/positions.py`)
  - Live positions table with 5s refresh
  - Portfolio summary card
  - Entry/exit prices, stop levels
  - Color-coded P&L
  - 31 tests, 95% coverage

- **Desktop Kymera UI Theme** (`src/dashboard/assets/kymera_theme.css`)
  - Sophisticated dark theme (#0a0e27 base)
  - Professional color palette
  - Responsive design

- **Trade Database & Journaling** (`src/database/trade_db.py`)
  - SQLite/PostgreSQL support via SQLAlchemy ORM
  - 4-table schema (trades, journal, positions, metrics)
  - Performance analytics
  - Backup/restore functionality
  - 60 tests, 97% coverage

- **Trailing Stop Management** (`src/execution/trailing_stops.py`)
  - Configurable 2% trailing distance
  - Automatic stop adjustment
  - Scheduler integration (60s intervals)
  - IB order modification
  - 35 tests, 95% coverage

### Project Statistics (v0.5.0)
- 662 total tests (658 passing - 99.4%)
- 93.8% average code coverage
- 12,849 lines production code
- 13,258 lines test code
- Total: 26,107 lines

---

## [v0.4.0] - 2025-11-15

### Added - Phase 5: Screening & Scoring System
- **Universe Manager** (`src/screening/universe.py`)
  - 7000+ US stock management
  - File I/O with validation
  - IB quote integration
  - 53 tests, 98% coverage

- **Coarse Filter** (`src/screening/coarse_filter.py`)
  - Bollinger Band position filtering
  - Trend strength detection
  - Volume spike detection
  - Volatility range filtering (1-10% ATR)
  - 80 tests, 97% coverage

- **SABR20 Scoring Engine** (`src/screening/sabr20_engine.py`)
  - 6-component proprietary scoring (0-100 points)
  - Component 1: BB Position (0-20 pts)
  - Component 2: Stoch/RSI Alignment (0-18 pts)
  - Component 3: Accumulation Intensity (0-18 pts) ⭐ NEW
  - Component 4: Trend Strength (0-15 pts)
  - Component 5: MACD Divergence (0-14 pts)
  - Component 6: Volume Profile (0-15 pts)
  - 65 tests, 97% coverage

- **Watchlist Generator** (`src/screening/watchlist.py`)
  - Full pipeline orchestration
  - Parallel processing support
  - Multi-timeframe data loading
  - 61 tests, 99% coverage

- **Accumulation Analysis** (`src/indicators/accumulation_analysis.py`)
  - Stoch/RSI ratio calculation
  - Phase classification (early/mid/late/breakout)
  - Batch analysis support
  - 21 tests, 98% coverage

### Phase 5 Statistics
- 259 tests (100% passing)
- 98% average coverage
- 2,099 lines production code
- 4,361 lines test code

---

## [v0.3.0] - 2025-11-15

### Added - Phase 6: Scale Testing
- **10-Symbol Test** (`scripts/test_10_symbols.py`)
  - Execution time: 8.31s (target: 60s)
  - 1,300 bars fetched
  - 100% success rate

- **95-Symbol Test** (`scripts/test_100_symbols.py`)
  - Execution time: 48.21s (target: 300s)
  - 12,350 bars fetched
  - 100% success rate
  - 2.0 symbols/sec processing rate

- **Aggregation Accuracy Test** (`scripts/test_aggregation_accuracy.py`)
  - Multi-timeframe validation
  - OHLCV relationship checks
  - Volume preservation verification

- **Sequential Testing Workflow** (`scripts/test_sequential.py`)
  - 6-component comprehensive pipeline test
  - Component isolation support
  - Skip-IB option for cached data

---

## [v0.2.0] - 2025-11-15

### Added - Phases 3-4: Real-time Processing & Validation

#### Phase 3a: Real-time Bar Aggregator
- **Component**: `src/data/realtime_aggregator.py` (650 lines)
- **Features**:
  - Multi-timeframe aggregation (5sec → 1min/5min/15min/1h/4h/1d)
  - OHLCV validation
  - Bar boundary detection
  - Callback support
  - Thread-safe operations
- **Tests**: 36/36 passing, 98% coverage

#### Phase 3b: Execution Validator
- **Component**: `src/execution/validator.py` (600 lines)
- **Features**:
  - 1% max risk per trade (ENFORCED)
  - 3% max total portfolio risk (ENFORCED)
  - Position sizing (risk-based)
  - Stop loss validation (direction + distance)
  - Account balance checks
  - Position tracking
- **Tests**: 50/50 passing, 99% coverage

#### Phase 4: End-to-End Integration
- **Component**: `tests/test_e2e_pipeline.py` (650 lines)
- **Coverage**:
  - IB → Historical → Aggregation → Validation pipeline
  - Multi-symbol processing
  - Error handling (disconnection, invalid data)
  - Performance testing (>100 bars/sec)
- **Tests**: 3/9 passing without IB (6 require live IB Gateway)

---

## [v0.1.0] - 2025-11-15

### Added - Phases 1-2: Core Infrastructure

#### Phase 1: IB Gateway Manager
- **Component**: `src/data/ib_manager.py` (838 lines)
- **Features**:
  - Connection management with auto-reconnection
  - Heartbeat monitoring (30s intervals)
  - Rate limiting (0.5s between requests)
  - Historical data fetching (6 timeframes)
  - Connection state tracking
- **Tests**: 39/40 passing, 85% coverage

#### Phase 2: Historical Data Manager
- **Component**: `src/data/historical_manager.py` (728 lines)
- **Features**:
  - Parquet storage with snappy compression
  - Metadata tracking (source, date range, bar count)
  - Batch operations
  - Data validation (OHLCV integrity, no gaps)
  - Dataset management
- **Tests**: 38/38 passing, 93% coverage

---

## Project Conventions

### Versioning
- **Major** (v1.0.0): Breaking changes, major feature sets
- **Minor** (v0.X.0): New features, phase completions
- **Patch** (v0.0.X): Bug fixes, documentation updates

### Test Standards
- Minimum 80% coverage per module
- All tests must pass before version increment
- Type hints on all functions
- Google-style docstrings

### Commit Message Format
```
Phase X: [Description] - [status]

Detailed changes:
- [Change 1]
- [Change 2]

Tests: X% coverage, all passing
```

---

## Links
- **GitHub**: https://github.com/astoreyai/screener
- **Documentation**: [README.md](README.md)
- **Deployment**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
