# SCREENER - Implementation Guide for Claude Code
## Multi-Timeframe Momentum Reversal Trading System

**Status**: Ready for Implementation
**Target Platform**: Claude Code (Web) → GitHub → Production Server
**Last Updated**: 2025-11-14

---

## 🎯 CRITICAL: Core Development Rules

**You MUST follow these five rules throughout implementation:**

### R1: Truthfulness
**Never guess; ask targeted questions**
- If any specification is unclear, ask before proceeding
- Validate assumptions with explicit questions
- Document all decisions and rationale

### R2: Completeness
**End-to-end code/docs/tests; zero placeholders**
- No TODOs, no placeholder functions
- Every function must be fully implemented
- All code must include comprehensive tests
- Documentation must be complete before commit

### R3: State Safety
**Checkpoint after each phase for continuation**
- Commit and push after completing each major phase
- Tag important milestones
- Ensure work can be resumed from any checkpoint
- Document current state in commit messages

### R4: Minimal Files
**Only necessary artifacts; keep docs current**
- ALWAYS edit existing files instead of creating new ones
- Only create files explicitly required by the specification
- Keep all documentation synchronized with code changes
- Remove outdated or redundant files immediately

### R5: Token Constraints
**Never shorten objectives; use R3 for continuation**
- Never abbreviate specifications to save tokens
- If approaching limits, checkpoint with R3 and continue
- Preserve complete functionality across sessions
- Document continuation points clearly

---

## 📋 Project Overview

This is a **professional-grade algorithmic trading system** that:
- Screens 500-2000 stocks in real-time
- Identifies mean-reversion-to-trend-expansion opportunities
- Uses multi-timeframe analysis (15m, 1h, 4h)
- Executes trades via Interactive Brokers API
- Provides real-time monitoring dashboard
- Implements comprehensive risk management

**Technology Stack:**
- Python 3.9+
- Interactive Brokers API (ib-insync)
- Pandas/Polars for data processing
- TA-Lib for technical indicators
- Dash/Plotly for dashboard
- SQLAlchemy + PostgreSQL/SQLite
- Pytest for testing

---

## 📚 Reference Documentation

All specifications are located in `/PRD/`:

1. **README-1.md** - Master index and quick start
2. **00_system_requirements_and_architecture.md** - Tech stack, infrastructure
3. **01_algorithm_spec.md** - Core trading algorithm
4. **02_mean_reversion_trend_system.md** - Risk management
5. **03_decision_tree_and_screening.md** - Decision logic
6. **04_universe_and_prescreening-1.md** - Universe construction
7. **05_watchlist_generation_and_scoring.md** - SABR20 scoring system
8. **06_regime_and_market_checks.md** - Market regime analysis
9. **07_realtime_dashboard_specification.md** - Dashboard UI
10. **08_data_pipeline_and_infrastructure.md** - Data management
11. **09_execution_and_monitoring.md** - Trade execution

**MANDATORY**: Read ALL these documents thoroughly before beginning implementation.

---

## 🏗️ Implementation Phases

### Phase 1: Project Setup and Infrastructure

**Objective:** Set up development environment, project structure, and core dependencies.

**Deliverables:**
- [R2] Complete project structure (no placeholders)
- [R4] Minimal necessary files only
- [R3] Initial checkpoint committed to GitHub

**Tasks:**

1. **Initialize Git Repository**
   ```bash
   git init
   git remote add origin git@github.com:astoreyai/screener.git
   ```

2. **Create Project Structure** (as specified in PRD/README-1.md):
   ```
   screener/
   ├── README.md
   ├── requirements.txt
   ├── .env.example
   ├── .gitignore
   ├── PRD/                       # Already exists - don't modify
   ├── src/
   │   ├── __init__.py
   │   ├── config.py
   │   ├── data/
   │   │   ├── __init__.py
   │   │   ├── ib_manager.py
   │   │   ├── historical_manager.py
   │   │   └── realtime_aggregator.py
   │   ├── indicators/
   │   │   ├── __init__.py
   │   │   ├── calculator.py
   │   │   ├── accumulation.py
   │   │   └── cache.py
   │   ├── screening/
   │   │   ├── __init__.py
   │   │   ├── universe.py
   │   │   ├── coarse_filter.py
   │   │   ├── sabr_scorer.py
   │   │   └── watchlist.py
   │   ├── regime/
   │   │   ├── __init__.py
   │   │   ├── analyzer.py
   │   │   └── monitor.py
   │   ├── execution/
   │   │   ├── __init__.py
   │   │   ├── validator.py
   │   │   ├── executor.py
   │   │   └── position_tracker.py
   │   ├── dashboard/
   │   │   ├── __init__.py
   │   │   ├── app.py
   │   │   ├── components/
   │   │   └── callbacks/
   │   ├── pipeline/
   │   │   ├── __init__.py
   │   │   └── pipeline_manager.py
   │   └── main.py
   ├── config/
   │   ├── trading_params.yaml
   │   └── system_config.yaml
   ├── data/
   │   ├── historical/
   │   └── cache/
   ├── logs/
   ├── tests/
   │   ├── __init__.py
   │   ├── test_indicators.py
   │   ├── test_screening.py
   │   └── test_execution.py
   └── scripts/
       ├── setup_database.py
       ├── download_historical.py
       └── backtest.py
   ```

3. **Create requirements.txt** (from PRD/00_system_requirements_and_architecture.md):
   ```
   ib-insync>=0.9.86
   pandas>=2.0.0
   numpy>=1.24.0
   polars>=0.19.0
   pyarrow>=13.0.0
   ta-lib>=0.4.28
   pandas-ta>=0.3.14
   dash>=2.14.0
   plotly>=5.17.0
   dash-bootstrap-components>=1.5.0
   sqlalchemy>=2.0.0
   psycopg2-binary>=2.9.9
   loguru>=0.7.0
   python-dotenv>=1.0.0
   schedule>=1.2.0
   pytest>=7.4.0
   pytest-cov>=4.1.0
   pyyaml>=6.0
   ```

4. **Create .env.example**:
   ```bash
   # Interactive Brokers
   IB_HOST=127.0.0.1
   IB_PORT=7497
   IB_CLIENT_ID=1

   # Database
   DB_TYPE=sqlite
   DB_PATH=data/trading.db
   # DB_TYPE=postgresql
   # DB_HOST=localhost
   # DB_PORT=5432
   # DB_NAME=trading_system
   # DB_USER=trader
   # DB_PASSWORD=

   # Paths
   DATA_DIR=./data
   CONFIG_DIR=./config
   LOG_DIR=./logs

   # System
   MAX_WORKERS=8
   ENABLE_PAPER_TRADING=True
   ```

5. **Create .gitignore**:
   ```
   # Python
   __pycache__/
   *.py[cod]
   *$py.class
   *.so
   .Python
   env/
   venv/

   # Environment
   .env

   # Data
   data/historical/
   data/cache/
   *.parquet
   *.db

   # Logs
   logs/
   *.log

   # IDE
   .vscode/
   .idea/
   *.swp

   # OS
   .DS_Store
   Thumbs.db
   ```

6. **[R3] Initial checkpoint**:
   ```bash
   git add .
   git commit -m "Phase 1: Project structure and configuration"
   git push -u origin main
   ```

**Phase 1 Checklist:**
- [ ] [R2] Project structure complete with no placeholders
- [ ] [R4] Only necessary files created
- [ ] Dependencies documented in requirements.txt
- [ ] Environment configuration templated
- [ ] [R3] Git repository committed and pushed to GitHub
- [ ] README.md with setup instructions created

---

### Phase 2: Data Infrastructure Layer

**Objective:** Implement data fetching, storage, and indicator calculation.

**Reference:** PRD/08_data_pipeline_and_infrastructure.md, PRD/00_system_requirements_and_architecture.md

**Tasks:**

1. **[R2] Implement `src/data/ib_manager.py`** (COMPLETE, no TODOs):
   - `IBConnectionConfig` dataclass
   - `IBDataManager` class with connection management
   - `fetch_historical_bars()` method
   - `subscribe_realtime_bars()` method
   - Error handling and reconnection logic
   - Full implementation required (reference PRD 08)

2. **[R2] Implement `src/data/historical_manager.py`** (COMPLETE):
   - `HistoricalDataManager` class
   - `save_bars()` - Write to Parquet
   - `load_bars()` - Read from Parquet
   - `update_historical_data()` - Merge new with existing
   - Directory structure management

3. **[R2] Implement `src/data/realtime_aggregator.py`** (COMPLETE):
   - `RealtimeBarAggregator` class
   - `add_bar()` - Process 5-second bars
   - `_aggregate_to_timeframe()` - Convert to 1min, 15min, etc.
   - `get_bars()` - Retrieve aggregated data

4. **[R2] Implement `src/indicators/calculator.py`** (COMPLETE):
   - `IndicatorEngine` class
   - `calculate_all_indicators()` - BB, StochRSI, MACD, RSI, ATR
   - Use TA-Lib for calculations
   - Return DataFrame with all indicators

5. **[R2] Implement `src/indicators/accumulation.py`** (COMPLETE):
   - `detect_stoch_buy_signal()` - Stoch RSI oversold crosses
   - `detect_rsi_buy_signal()` - RSI oversold recoveries
   - `calculate_accumulation_ratio()` - Signal frequency ratio
   - `classify_accumulation_phase()` - Phase determination
   - `calculate_accumulation_score()` - 0-18 point scoring

6. **[R2] Implement `src/indicators/cache.py`** (COMPLETE):
   - `IndicatorCache` class
   - In-memory caching with TTL
   - Cache invalidation methods

7. **[R2] Create `scripts/download_historical.py`** (COMPLETE):
   - Bulk download script for universe
   - Rate limiting (0.5s between requests)
   - Progress tracking with tqdm
   - Error handling and retry logic

8. **[R2] Create `scripts/setup_database.py`** (COMPLETE):
   - Database schema creation (from PRD 05, 06, 09)
   - Tables: trades, watchlist_realtime, regime_snapshots
   - Indexes for performance

**Testing Requirements [R2]:**
- Unit tests for indicator calculations (compare to known values)
- Test IB connection (mock or paper account)
- Test Parquet read/write
- Test accumulation ratio calculation
- All tests must pass before proceeding

**[R3] Phase 2 Checkpoint:**
```bash
git add .
git commit -m "Phase 2: Data infrastructure complete - all tests passing"
git push
git tag -a v0.2.0 -m "Data layer complete"
git push --tags
```

**Phase 2 Checklist:**
- [ ] [R2] IB integration fully functional (no placeholders)
- [ ] [R2] Historical data management complete
- [ ] [R2] Real-time bar aggregation implemented
- [ ] [R2] All indicators calculating correctly
- [ ] [R2] Accumulation ratio analysis functional
- [ ] [R2] Database schema deployed
- [ ] [R2] All tests passing (>80% coverage)
- [ ] [R3] Git committed and pushed with tag

---

### Phase 3: Screening and Scoring System

**Objective:** Implement universe screening, SABR20 scoring, and watchlist generation.

**Reference:** PRD/04_universe_and_prescreening-1.md, PRD/05_watchlist_generation_and_scoring.md

**Tasks:**

1. **[R2] Implement `src/screening/universe.py`** (COMPLETE):
   - `fetch_sp500_components()`
   - `fetch_nasdaq100_components()`
   - `build_base_universe()` - Combine indices
   - `apply_quality_filters()` - Price, volume, spread filters
   - `update_universe_job()` - Scheduled daily update

2. **[R2] Implement `src/screening/coarse_filter.py`** (COMPLETE):
   - `calculate_coarse_indicators()` - 1-hour indicators
   - `coarse_filter()` - Fast screening logic
   - `screen_single_symbol()` - Process one symbol
   - `screen_universe_parallel()` - Parallel processing
   - `calculate_preliminary_score()` - 0-100 ranking

3. **[R2] Implement `src/screening/sabr_scorer.py`** (COMPLETE):
   - `SABR20Score` dataclass
   - `calculate_setup_strength()` - Component 1 (0-30 pts)
   - `calculate_bottom_phase()` - Component 2 (0-22 pts)
   - `calculate_accumulation_intensity()` - Component 3 (0-18 pts) **NEW**
   - `calculate_trend_momentum()` - Component 4 (0-18 pts)
   - `calculate_risk_reward()` - Component 5 (0-10 pts)
   - `calculate_volume_profile()` - Component 6 (0-2 pts)
   - `calculate_sabr20_score()` - Main scoring function
   - `classify_bottom_state()` - State determination

4. **[R2] Implement `src/screening/watchlist.py`** (COMPLETE):
   - `run_multiframe_analysis()` - Full multi-TF analysis
   - `classify_setup()` - A+/A/B/C grading
   - `generate_actionable_watchlist()` - Filter to tradeable setups
   - `save_watchlist_snapshot()` - Database storage

**Testing Requirements [R2]:**
- Test universe construction (verify symbol counts)
- Test coarse filter performance (<30s for 1000 symbols)
- Test SABR20 calculations (verify scoring ranges)
- Test accumulation ratio on known patterns
- Integration test: full screening pipeline
- All tests must pass

**[R3] Phase 3 Checkpoint:**
```bash
git add .
git commit -m "Phase 3: Screening and scoring complete - all tests passing"
git push
git tag -a v0.3.0 -m "Screening engine complete"
git push --tags
```

**Phase 3 Checklist:**
- [ ] [R2] Universe construction functional
- [ ] [R2] Coarse screening processing 1000+ symbols in <30s
- [ ] [R2] SABR20 scoring with accumulation analysis working
- [ ] [R2] Watchlist generation producing ranked results
- [ ] [R2] All components fully tested
- [ ] [R3] Git committed and pushed with tag

---

### Phase 4: Market Regime Analysis

**Objective:** Implement market environment assessment and position sizing adjustments.

**Reference:** PRD/06_regime_and_market_checks.md

**Tasks:**

1. **[R2] Implement `src/regime/analyzer.py`** (COMPLETE):
   - `IndexTrend` dataclass
   - `VolatilityRegime` dataclass
   - `MarketBreadth` dataclass
   - `MarketEnvironment` dataclass
   - `classify_index_trend()` - Trend for SPY/QQQ/IWM/DIA
   - `calculate_market_trend_consensus()` - Multi-index consensus
   - `classify_volatility_regime()` - VIX analysis
   - `calculate_index_correlation()` - Cross-index correlation
   - `calculate_market_breadth()` - A/D, new highs/lows
   - `assess_market_environment()` - Complete regime assessment

2. **[R2] Implement `src/regime/monitor.py`** (COMPLETE):
   - `RegimeMonitor` class
   - `update()` - Refresh regime assessment
   - `get_current()` - Return cached regime
   - `save_to_db()` - Persist to database
   - `check_regime_change()` - Alert on significant changes

3. **[R2] Create regime-based filters** (COMPLETE):
   - `filter_watchlist_by_regime()` - Apply regime filters
   - `calculate_position_size_with_regime()` - Adjust sizes

**Testing Requirements [R2]:**
- Test VIX classification across regimes
- Test trend consensus calculation
- Test regime state transitions
- Verify position size adjustments
- All tests must pass

**[R3] Phase 4 Checkpoint:**
```bash
git add .
git commit -m "Phase 4: Regime analysis complete - all tests passing"
git push
git tag -a v0.4.0 -m "Regime analysis complete"
git push --tags
```

**Phase 4 Checklist:**
- [ ] [R2] Regime analysis functional
- [ ] [R2] VIX monitoring working
- [ ] [R2] Trend consensus calculating
- [ ] [R2] Position sizing adjusting based on regime
- [ ] [R2] Tests passing
- [ ] [R3] Git committed and pushed with tag

---

### Phase 5: Dashboard and Visualization

**Objective:** Build real-time web dashboard for monitoring and analysis.

**Reference:** PRD/07_realtime_dashboard_specification.md

**Tasks:**

1. **[R2] Implement `src/dashboard/app.py`** (COMPLETE):
   - Initialize Dash app with Bootstrap theme
   - Create main layout with grid structure
   - Set up interval components for updates
   - Configure callbacks

2. **[R2] Implement `src/dashboard/components/header.py`** (COMPLETE):
   - `create_header()` - Clock, connection, regime indicator

3. **[R2] Implement `src/dashboard/components/regime_panel.py`** (COMPLETE):
   - `create_regime_panel()` - VIX, trend, breadth display
   - Real-time metric updates

4. **[R2] Implement `src/dashboard/components/watchlist_table.py`** (COMPLETE):
   - `create_watchlist_table()` - Interactive DataTable
   - Columns: Symbol, SABR20, Grade, State, Acc Phase, Acc Ratio
   - Conditional formatting for scores and phases
   - Click handlers for symbol selection

5. **[R2] Implement `src/dashboard/components/charts.py`** (COMPLETE):
   - `create_multi_tf_chart()` - Multi-panel chart
   - Candlesticks + Bollinger Bands
   - Stoch RSI panel
   - MACD panel
   - Volume panel
   - `create_chart_tabs()` - 15m/1h/4h tabs
   - `create_accumulation_panel()` - Ratio visualization

6. **[R2] Implement `src/dashboard/components/positions.py`** (COMPLETE):
   - `create_positions_panel()` - Active positions display
   - `create_position_card()` - Individual position details
   - P&L tracking

7. **[R2] Implement `src/dashboard/components/alerts.py`** (COMPLETE):
   - `create_alerts_panel()` - Recent alerts
   - `create_alert_item()` - Individual alert formatting

8. **[R2] Implement `src/dashboard/callbacks/updates.py`** (COMPLETE):
   - `update_watchlist()` - Refresh every 15s
   - `update_charts()` - On symbol selection or 1min timer
   - `update_regime_indicator()` - Every 30min
   - `update_positions()` - Every 5s

**Testing Requirements [R2]:**
- Test dashboard renders without errors
- Test all callbacks execute
- Test data updates in real-time
- Verify chart interactions
- Performance test (page load <2s)
- All tests must pass

**[R3] Phase 5 Checkpoint:**
```bash
git add .
git commit -m "Phase 5: Dashboard complete - all tests passing"
git push
git tag -a v0.5.0 -m "Dashboard complete"
git push --tags
```

**Phase 5 Checklist:**
- [ ] [R2] Dashboard accessible at localhost:8050
- [ ] [R2] All panels rendering correctly
- [ ] [R2] Real-time updates working
- [ ] [R2] Charts interactive and responsive
- [ ] [R2] Accumulation phase displayed in watchlist
- [ ] [R3] Git committed and pushed with tag

---

### Phase 6: Trade Execution and Risk Management

**Objective:** Implement order execution, position tracking, and risk controls.

**Reference:** PRD/09_execution_and_monitoring.md, PRD/02_mean_reversion_trend_system.md

**Tasks:**

1. **[R2] Implement `src/execution/validator.py`** (COMPLETE):
   - `TradeValidation` dataclass
   - `RiskValidator` class
   - `validate_trade()` - Pre-trade checks
   - Enforce: max risk per trade, total risk, position limits, R:R minimums

2. **[R2] Implement `src/execution/executor.py`** (COMPLETE):
   - `OrderExecutor` class
   - `place_bracket_order()` - Entry + stop + target
   - `place_market_order()` - Simple market orders
   - `cancel_order()` - Cancel pending
   - `modify_stop()` - Trail stops

3. **[R2] Implement `src/execution/position_tracker.py`** (COMPLETE):
   - `Position` dataclass
   - `PositionTracker` class
   - `add_position()` - Record new position
   - `update_position()` - Update with current price
   - `remove_position()` - Close and archive
   - `get_total_unrealized_pnl()`
   - `get_total_risk_exposure()`

4. **[R2] Implement trade flow functions** (COMPLETE):
   - `execute_trade_from_watchlist()` - Complete execution flow
   - `record_trade_entry()` - Database logging
   - `record_trade_exit()` - Update with exit info

5. **[R2] Implement exit management** (COMPLETE):
   - `check_and_update_trailing_stops()` - Trail logic
   - `check_time_based_exits()` - Close before market close

6. **[R2] Implement performance tracking** (COMPLETE):
   - `PerformanceAnalyzer` class
   - `calculate_daily_metrics()` - Win rate, avg R, etc.
   - `generate_equity_curve()` - Cumulative P&L
   - `calculate_sharpe_ratio()`

**Testing Requirements [R2]:**
- Test risk validation (reject invalid trades)
- Test order placement (paper account)
- Test position tracking updates
- Test trailing stop logic
- Verify performance calculations
- All tests must pass

**[R3] Phase 6 Checkpoint:**
```bash
git add .
git commit -m "Phase 6: Execution engine complete - all tests passing"
git push
git tag -a v0.6.0 -m "Execution engine complete"
git push --tags
```

**Phase 6 Checklist:**
- [ ] [R2] Risk validation preventing bad trades
- [ ] [R2] Bracket orders executing correctly
- [ ] [R2] Positions tracked in real-time
- [ ] [R2] Trailing stops updating
- [ ] [R2] Performance metrics calculating
- [ ] [R2] Trade journal recording
- [ ] [R3] Git committed and pushed with tag

---

### Phase 7: Pipeline Orchestration and Main System

**Objective:** Integrate all components into cohesive automated system.

**Reference:** PRD/08_data_pipeline_and_infrastructure.md, PRD/09_execution_and_monitoring.md

**Tasks:**

1. **[R2] Implement `src/pipeline/pipeline_manager.py`** (COMPLETE):
   - `DataPipelineManager` class
   - `start()` - Initialize all components
   - `stop()` - Graceful shutdown
   - `_schedule_jobs()` - Set up scheduled tasks
   - `_update_historical_job()` - Pre-market data update
   - `_update_subscriptions_job()` - Real-time subscriptions
   - `_save_realtime_data_job()` - Post-market save

2. **[R2] Implement `src/main.py`** (COMPLETE):
   - `TradingSystem` class
   - `start()` - Complete system startup
   - `run_main_loop()` - Main execution loop
   - `stop()` - Graceful shutdown
   - Signal handlers (Ctrl+C)

3. **[R2] Implement scheduled jobs** (COMPLETE):
   - Pre-market (6:00 AM): Update universe and historical data
   - Pre-market (7:00 AM): Run comprehensive screening
   - Intraday (every 30min): Update coarse screening
   - Intraday (every 15min): Update watchlist
   - Intraday (every 5sec): Update positions
   - Intraday (every 1min): Check trailing stops
   - Post-market (4:30 PM): Save data, generate reports

4. **[R2] Create `config/trading_params.yaml`** (COMPLETE):
   - Universe parameters
   - Timeframe definitions
   - Indicator parameters
   - Risk limits
   - Threshold values

5. **[R2] Create `config/system_config.yaml`** (COMPLETE):
   - IB connection settings
   - Database configuration
   - Logging configuration
   - Performance parameters

**Testing Requirements [R2]:**
- Integration test: full system startup
- Test scheduled jobs execute
- Test graceful shutdown
- Test error recovery
- Load test: sustained operation
- All tests must pass

**[R3] Phase 7 Checkpoint:**
```bash
git add .
git commit -m "Phase 7: System integration complete - all tests passing"
git push
git tag -a v0.7.0 -m "System integration complete"
git push --tags
```

**Phase 7 Checklist:**
- [ ] [R2] Pipeline manager orchestrating all components
- [ ] [R2] Main system integrating all modules
- [ ] [R2] Scheduled jobs running automatically
- [ ] [R2] Configuration files complete
- [ ] [R2] Error handling robust
- [ ] [R3] Git committed and pushed with tag

---

### Phase 8: Testing, Documentation, and Production Ready

**Objective:** Comprehensive testing, documentation, and production deployment preparation.

**Tasks:**

1. **[R2] Unit Tests** (COMPLETE, >80% coverage):
   - `test_indicators.py` - All indicator calculations
   - `test_accumulation.py` - Accumulation ratio logic
   - `test_screening.py` - Coarse and fine screening
   - `test_sabr_scoring.py` - SABR20 score components
   - `test_regime.py` - Regime classification
   - `test_execution.py` - Order validation and placement

2. **[R2] Integration Tests** (COMPLETE):
   - End-to-end screening pipeline
   - Dashboard rendering and updates
   - Trade execution flow
   - Data pipeline operation

3. **[R2] Performance Tests** (COMPLETE):
   - Screening speed (must process 1000 symbols in <30s)
   - Dashboard responsiveness (<500ms updates)
   - Database query performance (<100ms)
   - Memory stability over 24 hours

4. **[R2] Update Documentation** (COMPLETE):
   - README.md with complete setup instructions
   - API documentation (docstrings)
   - Configuration guide
   - Troubleshooting guide
   - Example usage

5. **Paper Trading Validation** (1 week minimum):
   - Run system on paper account
   - Monitor for errors
   - Validate signals match visual analysis
   - Verify P&L calculations
   - Document any issues

6. **Production Deployment Checklist**:
   - [ ] All tests passing
   - [ ] Paper trading validated
   - [ ] Database backups configured
   - [ ] Monitoring alerts set up
   - [ ] Error logging comprehensive
   - [ ] Risk parameters conservative
   - [ ] Emergency shutdown procedure documented

**[R3] Phase 8 Final Checkpoint:**
```bash
git add .
git commit -m "Phase 8: Production ready - all documentation and tests complete"
git push
git tag -a v1.0.0 -m "Production ready release"
git push --tags
```

**Phase 8 Checklist:**
- [ ] [R2] Test suite with >80% coverage
- [ ] [R2] All tests passing
- [ ] [R2] Documentation complete
- [ ] Paper trading successful (1 week)
- [ ] Production deployment ready
- [ ] [R3] Git tag v1.0.0 pushed

---

## 🔧 Code Quality Standards

### Type Hints (MANDATORY per R2)
```python
def calculate_sabr20_score(
    data_15m: pd.DataFrame,
    data_1h: pd.DataFrame,
    data_4h: pd.DataFrame
) -> SABR20Score:
```

### Docstrings (MANDATORY per R2)
Google-style docstrings for ALL functions:
```python
def calculate_accumulation_ratio(df: pd.DataFrame, window: int = 50) -> pd.Series:
    """
    Calculate Stoch/RSI signal ratio over sliding window.

    Parameters:
    -----------
    df : pd.DataFrame
        OHLCV data with indicators
    window : int
        Lookback period (default: 50)

    Returns:
    --------
    pd.Series : Accumulation ratio
    """
```

### Error Handling (MANDATORY per R2)
Comprehensive try-except blocks with logging:
```python
try:
    data = ib_manager.fetch_historical_bars(symbol, '15 mins', '5 D')
except ConnectionError as e:
    logger.error(f"IB connection failed for {symbol}: {e}")
    return None
except Exception as e:
    logger.error(f"Unexpected error fetching {symbol}: {e}")
    return None
```

### Logging (MANDATORY per R2)
Use loguru for structured logging:
```python
logger.info(f"Screening {len(symbols)} symbols")
logger.warning(f"Low data quality for {symbol}")
logger.error(f"Failed to calculate indicators: {e}")
```

### Configuration (MANDATORY per R2)
- Never hardcode credentials
- Use .env for secrets
- Use YAML for parameters
- All configuration must be externalized

---

## 📊 Success Metrics

### System Performance (MANDATORY)
- [ ] Screen 1000 symbols in <30 seconds
- [ ] Dashboard updates in <500ms
- [ ] Database queries <100ms average
- [ ] 99.5% uptime during market hours
- [ ] Zero data loss

### Code Quality (MANDATORY per R2)
- [ ] Test coverage >80%
- [ ] Zero critical bugs in production
- [ ] All type hints present
- [ ] All functions documented
- [ ] Passes linting (flake8, mypy)

---

## 🚨 Critical Implementation Notes

### 1. Accumulation Ratio (PRD/05)
- NEW component added to SABR20 (Component 3: 0-18 points)
- Calculates Stoch/RSI signal frequency ratio
- Detects institutional accumulation before breakout
- **CRITICAL**: Carefully implement signal detection functions

### 2. Risk Management (PRD/09)
- Never exceed 1% risk per trade
- Never exceed 3% total portfolio risk
- Always validate trades before execution
- Implement hard stops immediately on entry

### 3. IB API (PRD/08)
- Respect rate limits (0.5s between requests)
- Handle disconnections gracefully
- **NEVER place live orders in testing**
- Use paper trading account initially

### 4. Data Integrity (PRD/08)
- Validate all data before processing
- Handle missing bars
- Check for duplicate timestamps
- Backup database daily

### 5. Performance (PRD/00)
- Use parallel processing for screening
- Cache indicator calculations
- Optimize database queries
- Profile bottlenecks

---

## 🎯 GitHub Workflow

### Branching Strategy
- `main` - Production-ready code only
- Use feature branches for development if needed
- All phases merge to main when complete

### Commit Messages (per R3)
```
Phase X: [Description] - [Status]

Examples:
Phase 2: Data infrastructure complete - all tests passing
Phase 5: Dashboard complete - all tests passing
Phase 8: Production ready - all documentation and tests complete
```

### Tags (per R3)
- Tag each phase completion: `v0.2.0`, `v0.3.0`, etc.
- Tag final production: `v1.0.0`

---

## 🔄 Server Sync Instructions

After completing implementation and pushing to GitHub:

### On Development Machine (archimedes)
```bash
# Ensure all changes are committed and pushed
git status
git log --oneline -5
git push origin main --tags

# Syncthing will automatically sync to euclid
# Monitor sync status:
curl -s -H "X-API-Key: tNKdfYrHbq53LEnyemTHQNhYK3h5xJNp" \
  'http://127.0.0.1:8384/rest/db/status?folder=github' | jq .

# Or SSH to euclid to verify:
ssh euclid "cd ~/github/astoreyai/screener && git status && git log --oneline -5"
```

### On Server (euclid)
```bash
# Connect via Tailscale
ssh euclid

# Navigate to project
cd ~/github/astoreyai/screener

# Verify sync
git status
git pull  # If needed

# Setup production environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure production settings
cp .env.example .env
# Edit .env with production IB credentials

# Setup database
python scripts/setup_database.py

# Run tests
pytest tests/ -v --cov=src

# Start system (use systemd service or tmux for persistence)
python src/main.py
```

---

## ✅ Final Pre-Production Checklist

Before deploying to production:

- [ ] [R1] All specifications understood and implemented correctly
- [ ] [R2] All code complete with no TODOs or placeholders
- [ ] [R2] All functions have type hints and docstrings
- [ ] [R2] Test coverage >80%, all tests passing
- [ ] [R2] All documentation complete and current
- [ ] [R3] All phases committed and tagged
- [ ] [R4] No unnecessary files in repository
- [ ] [R5] Complete implementation across all phases
- [ ] Paper trading validated (1+ week)
- [ ] Performance benchmarks met
- [ ] Error handling comprehensive
- [ ] Logging configured
- [ ] Monitoring alerts set up
- [ ] Backup systems in place
- [ ] Risk parameters reviewed
- [ ] Emergency procedures documented
- [ ] GitHub repository pushed with all tags
- [ ] Syncthing sync to euclid verified

---

## 📞 Help and Resources

**PRD Documentation**: All specifications in `/PRD/`
**External Resources**:
- [IB API Documentation](https://interactivebrokers.github.io/tws-api/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [TA-Lib Documentation](https://ta-lib.org/)
- [Dash Documentation](https://dash.plotly.com/)

---

## 🎓 Implementation Philosophy

This implementation must follow Aaron's core development rules:

1. **[R1] Ask when unclear** - If any specification is ambiguous, ask for clarification
2. **[R2] Build complete systems** - Every component must be production-ready
3. **[R3] Checkpoint frequently** - Commit and push after each phase
4. **[R4] Minimize artifacts** - Only create necessary files
5. **[R5] Never compromise** - Implement complete functionality, use R3 to continue

---

**Remember:** This is a complex professional trading system. Follow the 5 rules religiously. Read all PRD documents thoroughly. Test extensively. Start with paper trading. Never risk real capital until fully validated.

Good luck! 🚀
