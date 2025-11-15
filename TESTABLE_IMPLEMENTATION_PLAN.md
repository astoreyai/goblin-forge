# Testable Implementation Plan - Screener Project

**Created**: 2025-11-15
**Strategy**: Build incrementally with validation at each step
**Infrastructure**: Leverage proven IB Gateway setup from /home/aaron/projects/stoch

---

## Critical Infrastructure Decision

**IB Gateway Configuration**:
- Use IBC (Interactive Brokers Controller) automation from stoch project
- Paper trading port: **4002** (not 7497)
- Startup script: Adapt `/home/aaron/projects/stoch/scripts/start_ib_gateway.sh`
- Test framework: Adapt `/home/aaron/projects/stoch/scripts/test_paper_gateway.py`

---

## Phase 1: IB Gateway Connection (Day 1 Morning - 4 hours)

### 1a: Setup IB Gateway Infrastructure (30 min)
**Goal**: Create startup script and credentials structure for screener

**Tasks**:
1. Create `scripts/start_ib_gateway.sh` (adapt from stoch)
2. Update .env with IB_PORT=4002 for gateway_paper profile
3. Create test script `scripts/test_ib_connection.py`

**Test Command**:
```bash
# Start IB Gateway
./scripts/start_ib_gateway.sh paper

# Test connection
python scripts/test_ib_connection.py
```

**Success Criteria**:
- ✅ Gateway starts without errors
- ✅ Port 4002 is listening
- ✅ Test script connects successfully

---

### 1b: Create Minimal ib_manager.py (1 hour)
**Goal**: Connect to IB Gateway only (no data fetching yet)

**File**: `src/data/ib_manager.py`

**Implementation**:
```python
class IBDataManager:
    def __init__(self, host: str, port: int, client_id: int):
        """Initialize IB connection manager."""

    def connect(self) -> bool:
        """Connect to IB Gateway."""

    def disconnect(self):
        """Disconnect from IB Gateway."""

    def is_connected(self) -> bool:
        """Check connection status."""
```

**Test File**: `tests/test_ib_manager_connection.py`

**Test Command**:
```bash
pytest tests/test_ib_manager_connection.py -v
```

**Success Criteria**:
- ✅ Connection succeeds
- ✅ is_connected() returns True
- ✅ Disconnect works cleanly
- ✅ All tests pass

---

### 1c: Add Historical Data Fetching (1.5 hours)
**Goal**: Fetch bars for single symbol

**Add to ib_manager.py**:
```python
def fetch_historical_bars(
    self,
    symbol: str,
    bar_size: str = '15 mins',
    duration: str = '5 D',
    what_to_show: str = 'TRADES'
) -> pd.DataFrame:
    """Fetch historical bars for single symbol."""
```

**Test File**: `tests/test_ib_manager_historical.py`

**Test Command**:
```bash
# Test with AAPL
pytest tests/test_ib_manager_historical.py::test_fetch_single_symbol -v -s

# Expected output: DataFrame with OHLCV data for AAPL
```

**Success Criteria**:
- ✅ Returns valid DataFrame with OHLCV columns
- ✅ Data has correct timeframe (15m bars)
- ✅ Data covers requested duration (~5 days)
- ✅ No missing bars

---

### 1d: Add Error Handling (1 hour)
**Goal**: Handle common failure modes

**Add to ib_manager.py**:
- ConnectionError handling
- Timeout handling
- Invalid symbol handling
- Reconnection logic

**Test File**: `tests/test_ib_manager_errors.py`

**Test Command**:
```bash
pytest tests/test_ib_manager_errors.py -v
```

**Test Cases**:
- ✅ Invalid symbol raises appropriate error
- ✅ Disconnection is detected
- ✅ Reconnection succeeds after disconnect
- ✅ Timeout errors are handled gracefully

---

### 1e: Create src/data/__init__.py (5 min)
**Goal**: Make data package importable

**File**: `src/data/__init__.py`

**Content**:
```python
"""Data infrastructure for IB API, historical storage, and real-time aggregation."""
from .ib_manager import IBDataManager

__all__ = ['IBDataManager']
```

**Test Command**:
```bash
python -c "from src.data import IBDataManager; print('✅ Import successful')"
```

---

## Phase 2: Historical Data Manager (Day 1 Afternoon - 4 hours)

### 2a: Create Minimal historical_manager.py (1 hour)
**Goal**: Save/load single symbol to Parquet

**File**: `src/data/historical_manager.py`

**Implementation**:
```python
class HistoricalDataManager:
    def __init__(self, data_dir: str):
        """Initialize with data directory."""

    def save_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame
    ) -> Path:
        """Save single symbol's data to Parquet."""

    def load_symbol_data(
        self,
        symbol: str,
        timeframe: str
    ) -> pd.DataFrame:
        """Load single symbol's data from Parquet."""
```

**Test File**: `tests/test_historical_manager_basic.py`

**Test Command**:
```bash
pytest tests/test_historical_manager_basic.py -v
```

**Success Criteria**:
- ✅ Save creates Parquet file
- ✅ Load reads correct data
- ✅ Round-trip preserves data integrity
- ✅ Directory structure created correctly

---

### 2b: Add Batch Operations (1.5 hours)
**Goal**: Handle multiple symbols efficiently

**Add to historical_manager.py**:
```python
def save_multiple_symbols(
    self,
    data_dict: Dict[str, pd.DataFrame],
    timeframe: str
) -> Dict[str, Path]:
    """Save multiple symbols in parallel."""

def load_multiple_symbols(
    self,
    symbols: List[str],
    timeframe: str
) -> Dict[str, pd.DataFrame]:
    """Load multiple symbols in parallel."""
```

**Test File**: `tests/test_historical_manager_batch.py`

**Test Command**:
```bash
# Test with 10 symbols
pytest tests/test_historical_manager_batch.py::test_batch_save_load -v
```

**Success Criteria**:
- ✅ All symbols saved correctly
- ✅ All symbols loaded correctly
- ✅ Parallel processing works
- ✅ Performance acceptable (<5s for 10 symbols)

---

### 2c: Add Data Validation (1 hour)
**Goal**: Detect and handle bad data

**Add to historical_manager.py**:
```python
def validate_data(self, data: pd.DataFrame) -> bool:
    """Validate OHLCV data integrity."""
    # Check for:
    # - Required columns
    # - Duplicate timestamps
    # - Missing values
    # - OHLC consistency (High >= Low, etc.)
```

**Test File**: `tests/test_historical_manager_validation.py`

**Test Command**:
```bash
pytest tests/test_historical_manager_validation.py -v
```

**Test Cases**:
- ✅ Valid data passes validation
- ✅ Missing columns detected
- ✅ Duplicate timestamps rejected
- ✅ OHLC inconsistencies caught

---

### 2d: Fix Orphaned Test (30 min)
**Goal**: Update tests/test_historical_manager.py to work with new implementation

**File**: `tests/test_historical_manager.py`

**Test Command**:
```bash
# This test currently fails with ImportError
pytest tests/test_historical_manager.py -v

# After fix, should pass
```

**Success Criteria**:
- ✅ No ImportError
- ✅ All tests pass
- ✅ R2 (Completeness) violation resolved

---

## Phase 3: Integration Test - Single Symbol End-to-End (Day 1 Evening - 2 hours)

### 3a: Create Integration Test Script (1 hour)
**Goal**: Test full pipeline with one symbol

**File**: `scripts/test_e2e_single_symbol.py`

**Flow**:
1. Start IB Gateway (if not running)
2. Connect via ib_manager
3. Fetch AAPL 15m data (5 days)
4. Save to Parquet via historical_manager
5. Load from Parquet
6. Validate data integrity
7. Print summary

**Test Command**:
```bash
python scripts/test_e2e_single_symbol.py
```

**Success Criteria**:
- ✅ Full pipeline completes without errors
- ✅ Data saved and loaded successfully
- ✅ Data integrity maintained
- ✅ Execution time <10 seconds

---

### 3b: Test with Multiple Timeframes (1 hour)
**Goal**: Verify multi-timeframe support

**File**: `scripts/test_multitimeframe.py`

**Flow**:
1. Connect to IB
2. Fetch AAPL data for: 15m, 1h, 4h
3. Save all timeframes
4. Load all timeframes
5. Validate alignment

**Test Command**:
```bash
python scripts/test_multitimeframe.py
```

**Success Criteria**:
- ✅ All timeframes fetched
- ✅ All timeframes saved
- ✅ All timeframes loaded
- ✅ Bar counts correct for each timeframe

---

## Phase 4: Real-time Aggregator (Day 2 Morning - 4 hours)

### 4a: Create Minimal realtime_aggregator.py (2 hours)
**Goal**: Aggregate 5s bars to higher timeframes

**File**: `src/data/realtime_aggregator.py`

**Implementation**:
```python
class RealtimeAggregator:
    def __init__(self, timeframes: List[str]):
        """Initialize with target timeframes."""

    def add_bar(self, bar_5s: BarData):
        """Add 5-second bar and trigger aggregation."""

    def get_latest_bar(self, timeframe: str) -> Optional[BarData]:
        """Get latest aggregated bar for timeframe."""
```

**Test File**: `tests/test_realtime_aggregator.py`

**Test Command**:
```bash
pytest tests/test_realtime_aggregator.py -v
```

**Success Criteria**:
- ✅ 5s → 1m aggregation works
- ✅ 1m → 15m aggregation works
- ✅ OHLCV calculations correct
- ✅ Volume summed correctly

---

### 4b: Add IB Real-time Streaming (2 hours)
**Goal**: Stream 5-second bars from IB

**Add to ib_manager.py**:
```python
def subscribe_realtime_bars(
    self,
    symbol: str,
    bar_size: int = 5,
    callback: Callable[[BarData], None] = None
):
    """Subscribe to real-time 5-second bars."""
```

**Test File**: `tests/test_ib_realtime.py`

**Test Command**:
```bash
# Test during market hours only
pytest tests/test_ib_realtime.py -v
```

**Success Criteria**:
- ✅ Subscription succeeds
- ✅ Bars received every 5 seconds
- ✅ Callback triggered correctly
- ✅ Unsubscribe works cleanly

---

## Phase 5: Execution Validator (Day 2 Afternoon - 4 hours)

### 5a: Create execution/validator.py (2 hours)
**Goal**: Implement 1% per trade, 3% total risk limits

**File**: `src/execution/validator.py`

**Implementation**:
```python
class TradeValidator:
    def __init__(self, config: TradingConfig):
        """Initialize with risk limits."""

    def validate_trade(
        self,
        symbol: str,
        entry_price: float,
        stop_price: float,
        position_size: int,
        account_value: float,
        current_exposure: float
    ) -> ValidationResult:
        """Validate trade against risk limits."""
```

**Test File**: `tests/test_trade_validator.py`

**Test Command**:
```bash
pytest tests/test_trade_validator.py -v
```

**Test Cases**:
- ✅ Valid trade passes
- ✅ >1% risk rejected
- ✅ >3% total exposure rejected
- ✅ Negative position size rejected
- ✅ Invalid stop price rejected

---

### 5b: Add Position Size Calculator (1 hour)
**Goal**: Calculate shares based on risk

**Add to validator.py**:
```python
def calculate_position_size(
    self,
    entry_price: float,
    stop_price: float,
    account_value: float,
    risk_per_trade: float = 0.01
) -> int:
    """Calculate position size based on risk."""
```

**Test File**: `tests/test_position_sizing.py`

**Test Command**:
```bash
pytest tests/test_position_sizing.py -v
```

**Success Criteria**:
- ✅ Correct shares calculated
- ✅ Risk never exceeds limit
- ✅ Rounds to valid share count
- ✅ Edge cases handled (high volatility)

---

### 5c: Create execution/__init__.py (5 min)
**File**: `src/execution/__init__.py`

**Content**:
```python
"""Trade execution and risk validation."""
from .validator import TradeValidator

__all__ = ['TradeValidator']
```

---

## Phase 6: Scale Test (Day 2 Evening - 2 hours)

### 6a: Test with 10 Symbols (1 hour)
**Goal**: Verify system handles multiple symbols

**File**: `scripts/test_10_symbols.py`

**Symbols**: AAPL, MSFT, GOOGL, AMZN, TSLA, META, NVDA, AMD, NFLX, SPY

**Flow**:
1. Connect to IB
2. Fetch 15m data for all 10 symbols (5 days each)
3. Save to Parquet
4. Calculate basic indicators (BB, RSI)
5. Run through validator
6. Measure performance

**Test Command**:
```bash
python scripts/test_10_symbols.py
```

**Success Criteria**:
- ✅ All symbols processed successfully
- ✅ No data corruption
- ✅ Execution time <60 seconds
- ✅ Memory usage acceptable

---

### 6b: Test with 100 Symbols (1 hour)
**Goal**: Stress test parallel processing

**File**: `scripts/test_100_symbols.py`

**Flow**:
1. Load first 100 tickers from ticker_downloader
2. Fetch 15m data in parallel (respect IB rate limits)
3. Save all to Parquet
4. Verify data integrity
5. Measure performance

**Test Command**:
```bash
python scripts/test_100_symbols.py
```

**Success Criteria**:
- ✅ All symbols processed
- ✅ No rate limit errors
- ✅ Execution time <5 minutes
- ✅ All data validates correctly

---

## Phase 7: Update Documentation & Tests (Day 3 Morning - 2 hours)

### 7a: Update TODO.md (30 min)
**File**: `TODO.md`

**Updates**:
- Mark completed phases ✅
- Update progress percentages
- Document what works
- Note any deviations from plan

---

### 7b: Run Full Test Suite (30 min)
**Test Command**:
```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

**Success Criteria**:
- ✅ >80% code coverage
- ✅ All tests pass
- ✅ No warnings

---

### 7c: Update IMPLEMENTATION_ANALYSIS.md (30 min)
**File**: `IMPLEMENTATION_ANALYSIS.md`

**Updates**:
- Document what's now implemented
- Update missing components list
- Update phase completion percentages
- Document any SABR20 decisions

---

### 7d: Git Commit & Push (30 min)
**Commands**:
```bash
# Run tests first
pytest tests/ -v --cov=src

# Commit
git add .
git commit -m "Phase 1-2: IB Gateway and Historical Manager complete

- Implemented ib_manager.py with connection and historical fetching
- Implemented historical_manager.py with Parquet storage
- Created realtime_aggregator.py skeleton
- Created execution/validator.py with risk checks
- All tests passing (42+ tests)
- Fixed orphaned test file

Tests: 85% coverage
Updated: TODO.md, IMPLEMENTATION_ANALYSIS.md"

# Tag
git tag -a v0.3.0 -m "IB Gateway and data infrastructure complete"

# Push
git push origin main --tags
```

---

## Daily Testing Schedule

### Every Morning Before Coding:
```bash
# 1. Start IB Gateway
./scripts/start_ib_gateway.sh paper

# 2. Run quick smoke test
python scripts/test_ib_connection.py

# 3. Check gateway health
curl -s http://localhost:4002 || echo "Gateway ready on port 4002"
```

### After Each Component:
```bash
# 1. Run specific tests
pytest tests/test_[component].py -v

# 2. Run integration test
python scripts/test_e2e_single_symbol.py
```

### Before Each Commit:
```bash
# 1. Run full test suite
pytest tests/ -v --cov=src

# 2. Check coverage >80%
# 3. Verify no errors
# 4. Update TODO.md
```

---

## Debugging Commands

### Check IB Gateway Status:
```bash
# Check if running
pgrep -f "ibgateway.*total.*jar"

# Check port
netstat -tuln | grep 4002

# View logs
tail -f ~/.ibgateway/logs/ibgateway_paper_*.log
```

### Test Database:
```bash
# Check Parquet files
ls -lh data/historical/15m/

# Inspect Parquet
python -c "import pandas as pd; print(pd.read_parquet('data/historical/15m/AAPL.parquet'))"
```

### Test Imports:
```bash
# Test all imports work
python -c "
from src.data import IBDataManager
from src.data.historical_manager import HistoricalDataManager
from src.data.realtime_aggregator import RealtimeAggregator
from src.execution import TradeValidator
print('✅ All imports successful')
"
```

---

## Success Metrics

### Day 1 End:
- ✅ IB Gateway connection working
- ✅ Historical data fetch working
- ✅ Parquet storage working
- ✅ Single symbol e2e test passing
- ✅ Tests: ~20 passing

### Day 2 End:
- ✅ Real-time streaming working
- ✅ Trade validator working
- ✅ 10 symbol test passing
- ✅ Tests: ~40 passing
- ✅ Coverage: >80%

### Day 3 End:
- ✅ 100 symbol test passing
- ✅ All documentation updated
- ✅ Code committed and pushed
- ✅ Tests: 50+ passing
- ✅ R2 (Completeness) violation resolved

---

## Risk Mitigation

### If IB Gateway Fails:
1. Check logs: `~/.ibgateway/logs/`
2. Verify credentials in `~/.ibgateway/secrets/`
3. Restart gateway: `pkill -f ibgateway && ./scripts/start_ib_gateway.sh paper`
4. Test with stoch test: `/home/aaron/projects/stoch/scripts/test_paper_gateway.py`

### If Tests Fail:
1. Run individually: `pytest tests/test_specific.py::test_name -v -s`
2. Check imports: Python path issues
3. Check IB connection: Gateway must be running
4. Check data: Verify Parquet files exist

### If Performance Issues:
1. Profile: `python -m cProfile -o profile.stats script.py`
2. Check IB rate limits: 0.5s between requests
3. Verify parallel processing: MAX_WORKERS setting
4. Check disk I/O: Parquet write speed

---

## Next Steps After This Plan

Once Phases 1-7 complete:
1. Implement remaining execution components (executor, position_tracker)
2. Implement pipeline_manager
3. Complete dashboard components
4. Run 1000 symbol screening test
5. Paper trading validation (1 week minimum)

---

**This plan is TESTABLE, DEBUGGABLE, and INCREMENTAL.**
**Each step has clear success criteria and can be validated independently.**
**Progress can be checkpointed at any time per R3 (State Safety).**
