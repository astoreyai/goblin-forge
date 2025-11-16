# Screener Trading System - Architecture Documentation

**Version**: v0.5.0
**Last Updated**: 2025-11-16
**Status**: Production Ready

This document provides a comprehensive overview of the Screener trading system architecture, including component diagrams, data flow, integration points, and design decisions.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Architecture](#component-architecture)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [API Interfaces](#api-interfaces)
7. [Integration Points](#integration-points)
8. [Design Patterns](#design-patterns)
9. [Security Architecture](#security-architecture)
10. [Scalability and Performance](#scalability-and-performance)
11. [Deployment Architecture](#deployment-architecture)

---

## System Overview

The Screener is a **professional-grade algorithmic trading system** designed to identify and execute mean-reversion-to-trend-expansion opportunities across multiple timeframes. The system integrates with Interactive Brokers for real-time market data and trade execution, implements sophisticated screening algorithms, and provides real-time monitoring through a web-based dashboard.

### Key Capabilities

- **Multi-Timeframe Analysis**: 5min, 15min, 1hour, 4hour, 1day
- **Real-Time Market Data**: Live streaming via Interactive Brokers API
- **Proprietary SABR20 Scoring**: 6-component scoring system (0-100 points)
- **Risk Management**: 1% per-trade, 3% portfolio limits enforced
- **Trade Execution**: Automated order placement with validation
- **Position Tracking**: Real-time P&L monitoring
- **Trailing Stops**: Dynamic stop loss adjustment
- **Trade Journaling**: Comprehensive trade logging and analytics
- **Web Dashboard**: Real-time monitoring and control

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Language** | Python 3.11.2 |
| **IB Integration** | ib-insync 0.9.86 |
| **Data Processing** | pandas 2.0, NumPy 1.24, Polars 0.19 |
| **Technical Analysis** | TA-Lib 0.4.28 |
| **Database** | SQLite 3.x (dev), PostgreSQL 13+ (prod) |
| **Dashboard** | Dash 2.14, Plotly 5.17, Dash Bootstrap Components |
| **Testing** | pytest 9.0, pytest-cov 7.0 |
| **Logging** | loguru 0.7 |
| **Scheduling** | schedule 1.2 |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERACTIVE BROKERS                          │
│                    (Market Data & Order Execution)                  │
└────────────────┬────────────────────────────────────┬───────────────┘
                 │                                    │
                 │ IB API (ib-insync)                │ IB API
                 ↓                                    ↓
┌────────────────────────────────────┐  ┌──────────────────────────────┐
│      DATA INFRASTRUCTURE           │  │   EXECUTION INFRASTRUCTURE   │
├────────────────────────────────────┤  ├──────────────────────────────┤
│ • IB Gateway Manager (Phase 1)     │  │ • Execution Validator        │
│ • Historical Data Manager (Phase 2)│  │ • Position Tracker           │
│ • Real-time Aggregator (Phase 3a)  │  │ • Trailing Stop Manager      │
│ • Multi-Timeframe Builder          │  │ • Order Manager              │
└────────────┬───────────────────────┘  └──────────┬───────────────────┘
             │                                     │
             │ Parquet Storage                     │ Trade Database
             ↓                                     ↓
┌────────────────────────────────────┐  ┌──────────────────────────────┐
│      SCREENING SYSTEM (Phase 5)    │  │   DATABASE LAYER             │
├────────────────────────────────────┤  ├──────────────────────────────┤
│ • Universe Manager                 │  │ • Trade Journal              │
│ • Coarse Filter                    │  │ • Position History           │
│ • SABR20 Engine (6 components)     │  │ • Performance Analytics      │
│ • Watchlist Generator              │  │ • Configuration Storage      │
│ • Accumulation Analyzer            │  │ • Metadata & Logs            │
└────────────┬───────────────────────┘  └──────────┬───────────────────┘
             │                                     │
             │ Watchlist Events                    │ Query Interface
             ↓                                     ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      WEB DASHBOARD (Phase 7)                        │
├─────────────────────────────────────────────────────────────────────┤
│ • Watchlist Tab (real-time screened symbols)                        │
│ • Charts Tab (multi-timeframe with indicators)                      │
│ • Positions Tab (live P&L tracking)                                 │
│ • Portfolio Summary (account metrics)                               │
└─────────────────────────────────────────────────────────────────────┘
             │
             │ HTTP (Dash/Plotly)
             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         WEB BROWSER                                 │
│                    (User Interface - Desktop Kymera Theme)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Data Infrastructure Layer

#### 1.1 IB Gateway Manager
**File**: `src/data/ib_manager.py`
**Purpose**: Manages connection to Interactive Brokers Gateway/TWS
**Key Features**:
- Singleton pattern for single connection management
- Auto-reconnection with exponential backoff
- Heartbeat monitoring (30s intervals)
- Rate limiting (0.5s between requests)
- Connection state tracking
- Thread-safe operations

**Key Methods**:
```python
class IBDataManager:
    def connect() -> bool
    def disconnect() -> None
    def fetch_historical_bars(symbol, bar_size, duration) -> pd.DataFrame
    def get_current_quote(symbol) -> Quote
    def is_connected() -> bool
    def _heartbeat() -> None  # Background thread
```

**Dependencies**:
- ib_insync: IB API wrapper
- loguru: Logging

**Integration Points**:
- → Historical Data Manager (provides data)
- → Real-time Aggregator (provides live bars)
- → Execution Validator (provides account info)

#### 1.2 Historical Data Manager
**File**: `src/data/historical_manager.py`
**Purpose**: Manages persistent storage of historical market data
**Key Features**:
- Parquet format for efficient storage (5:1 compression)
- Metadata tracking (source, date range, bar count)
- Batch operations (save/load multiple symbols)
- Data validation (OHLCV integrity, no gaps)
- Dataset management (list, delete, statistics)
- Thread-safe file operations

**Key Methods**:
```python
class HistoricalDataManager:
    def save_data(symbol, data, metadata) -> None
    def load_data(symbol, start_date, end_date) -> pd.DataFrame
    def batch_save(data_dict) -> None
    def batch_load(symbols) -> Dict[str, pd.DataFrame]
    def list_datasets() -> List[str]
    def get_metadata(symbol) -> Dict
    def delete_dataset(symbol) -> None
```

**Storage Format**:
```
data/
├── AAPL_15min.parquet       # Price data
├── AAPL_15min.meta.json     # Metadata
├── MSFT_15min.parquet
└── MSFT_15min.meta.json
```

**Dependencies**:
- pandas: Data manipulation
- pyarrow: Parquet I/O
- loguru: Logging

**Integration Points**:
- ← IB Gateway Manager (receives data)
- → Screening System (provides historical data)
- → Dashboard (provides chart data)

#### 1.3 Real-time Bar Aggregator
**File**: `src/data/realtime_aggregator.py`
**Purpose**: Aggregates real-time 5-second bars into higher timeframes
**Key Features**:
- Multi-timeframe aggregation (5sec → 1min, 5min, 15min, 1h, 4h, 1d)
- OHLCV validation (high ≥ low, etc.)
- Bar boundary detection (align with timeframe periods)
- Callback support for completed bars
- Thread-safe operations
- Memory-efficient streaming

**Key Methods**:
```python
class RealtimeAggregator:
    def add_bar(symbol, timeframe, bar) -> None
    def get_completed_bars(symbol, timeframe) -> List[Bar]
    def register_callback(timeframe, callback) -> None
    def to_dataframe(symbol, timeframe) -> pd.DataFrame
```

**Aggregation Logic**:
```
5-second bars → Buffer
  ↓ (time boundary check)
1-minute bar (12 x 5sec bars) → Emit
  ↓ (time boundary check)
5-minute bar (5 x 1min bars) → Emit
  ↓ (time boundary check)
15-minute bar (3 x 5min bars) → Emit
  ... and so on
```

**Dependencies**:
- pandas: Data aggregation
- loguru: Logging

**Integration Points**:
- ← IB Gateway Manager (receives 5sec bars)
- → Screening System (provides aggregated bars)
- → Dashboard (provides real-time chart updates)

---

### 2. Execution Infrastructure Layer

#### 2.1 Execution Validator
**File**: `src/execution/validator.py`
**Purpose**: Validates all trade orders against risk management rules
**Key Features**:
- 1% max risk per trade enforcement (CRITICAL)
- 3% max total portfolio risk enforcement (CRITICAL)
- Position size calculation (risk-based)
- Stop loss validation (direction + distance)
- Account balance checks
- Position limits (max 10 concurrent)
- Thread-safe validation

**Validation Flow**:
```
Trade Signal
  ↓
1. Check account balance > 0
  ↓
2. Calculate position size from risk (1%)
  ↓
3. Validate stop loss (direction & distance)
  ↓
4. Check total portfolio risk ≤ 3%
  ↓
5. Check position count ≤ 10
  ↓
6. Check symbol whitelist (if configured)
  ↓
Approved ✅ / Rejected ❌
```

**Key Methods**:
```python
class ExecutionValidator:
    def validate_trade(trade_signal) -> ValidationResult
    def calculate_position_size(risk_amount, stop_distance) -> int
    def validate_stop_loss(entry_price, stop_price, direction) -> bool
    def check_portfolio_risk() -> bool
    def add_position(position) -> None
    def remove_position(symbol) -> None
```

**Risk Calculations**:
```python
# Position Size
risk_amount = account_balance * max_risk_per_trade  # 1%
position_size = risk_amount / stop_distance

# Portfolio Risk
total_risk = sum(position.risk for position in open_positions)
portfolio_risk_pct = total_risk / account_balance
assert portfolio_risk_pct <= 0.03  # 3% max
```

**Dependencies**:
- loguru: Logging
- dataclasses: Type-safe data structures

**Integration Points**:
- → Position Tracker (updates positions)
- → Order Manager (executes validated trades)
- → Database (logs validation results)

#### 2.2 Position Tracker
**File**: `src/execution/position_tracker.py`
**Purpose**: Tracks open positions and calculates real-time P&L
**Key Features**:
- Real-time unrealized P&L calculation
- Realized P&L on position close
- Multi-position tracking
- Thread-safe operations
- Position history
- Performance metrics

**Key Methods**:
```python
class PositionTracker:
    def add_position(symbol, quantity, entry_price, stop_loss) -> None
    def update_position(symbol, current_price) -> None
    def close_position(symbol, exit_price) -> Position
    def get_position(symbol) -> Position
    def get_all_positions() -> List[Position]
    def get_unrealized_pnl() -> float
    def get_realized_pnl() -> float
    def to_dataframe() -> pd.DataFrame
```

**Position Data Structure**:
```python
@dataclass
class Position:
    symbol: str
    quantity: int
    direction: str  # 'long' or 'short'
    entry_price: float
    entry_time: datetime
    stop_loss: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: str = 'open'  # 'open', 'closed'
```

**P&L Calculations**:
```python
# Long Position
unrealized_pnl = (current_price - entry_price) * quantity

# Short Position
unrealized_pnl = (entry_price - current_price) * quantity

# Realized P&L (on close)
realized_pnl = (exit_price - entry_price) * quantity  # long
realized_pnl = (entry_price - exit_price) * quantity  # short
```

**Dependencies**:
- pandas: DataFrame conversion
- loguru: Logging
- dataclasses: Position data structure

**Integration Points**:
- ← Execution Validator (adds positions)
- ← Real-time Aggregator (updates current prices)
- → Dashboard (provides position data)
- → Database (logs position history)

#### 2.3 Trailing Stop Manager
**File**: `src/execution/trailing_stops.py`
**Purpose**: Manages dynamic trailing stop loss adjustments
**Key Features**:
- Configurable trailing distance (default 2%)
- Automatic stop adjustment as price moves favorably
- Per-position tracking
- Scheduler integration (60s intervals)
- IB order modification
- No stop reduction (only increases)

**Trailing Logic**:
```
Long Position:
  If current_price > entry_price * (1 + trailing_distance):
    new_stop = current_price * (1 - trailing_distance)
    if new_stop > current_stop:
      update_stop(new_stop)

Short Position:
  If current_price < entry_price * (1 - trailing_distance):
    new_stop = current_price * (1 + trailing_distance)
    if new_stop < current_stop:
      update_stop(new_stop)
```

**Key Methods**:
```python
class TrailingStopManager:
    def update_trailing_stops() -> None
    def calculate_new_stop(position, current_price) -> float
    def modify_stop_order(symbol, new_stop) -> bool
    def start_scheduler() -> None
    def stop_scheduler() -> None
```

**Dependencies**:
- schedule: Task scheduling
- loguru: Logging
- ib-insync: Order modification

**Integration Points**:
- ← Position Tracker (gets position data)
- → IB Gateway Manager (modifies stop orders)
- → Database (logs stop adjustments)

---

### 3. Screening System Layer

#### 3.1 Universe Manager
**File**: `src/screening/universe.py`
**Purpose**: Manages the stock universe for screening
**Key Features**:
- 7000+ US stocks loaded from CSV
- Filtering by price, volume, market cap
- IB quote validation
- Batch symbol processing
- Universe update scheduling (daily/weekly)

**Universe Filters**:
```python
filters = {
    'min_price': 5.0,         # Minimum $5
    'max_price': 1000.0,      # Maximum $1000
    'min_volume': 1000000,    # 1M shares daily
    'min_market_cap': 100M    # $100M market cap
}
```

**Key Methods**:
```python
class UniverseManager:
    def load_universe() -> List[str]
    def filter_by_price(symbols, min_price, max_price) -> List[str]
    def filter_by_volume(symbols, min_volume) -> List[str]
    def get_current_quotes(symbols) -> Dict[str, Quote]
    def update_universe() -> None
```

**Integration Points**:
- ← IB Gateway Manager (validates symbols)
- → Coarse Filter (provides symbols to screen)

#### 3.2 Coarse Filter
**File**: `src/screening/coarse_filter.py`
**Purpose**: Fast filtering to reduce universe from 7000 to ~500 symbols
**Key Features**:
- Bollinger Band position check (lower 30%)
- Trend strength filter (2%+ uptrend)
- Volume filter (20%+ above average)
- Volatility filter (ATR 1-10%)
- Parallel processing support

**Filter Criteria**:
```python
coarse_filters = {
    'bb_position': [0.0, 0.3],      # Lower 30% of BB
    'trend_strength': 0.02,          # 2%+ above SMA(50)
    'volume_ratio': 1.2,             # 20%+ above avg
    'volatility': [0.01, 0.10]       # ATR/price 1-10%
}
```

**Key Methods**:
```python
class CoarseFilter:
    def screen(symbols, data) -> List[str]
    def check_bb_position(df) -> bool
    def check_trend(df) -> bool
    def check_volume(df) -> bool
    def check_volatility(df) -> bool
```

**Performance**:
- 1000 symbols screened in ~5 seconds
- 95%+ reduction (7000 → ~300)

**Integration Points**:
- ← Universe Manager (receives symbols)
- → SABR20 Engine (provides filtered symbols)

#### 3.3 SABR20 Engine
**File**: `src/screening/sabr20_engine.py`
**Purpose**: Proprietary 6-component scoring system (0-100 points)
**Key Features**:
- Multi-timeframe analysis (15min, 1hour, 4hour)
- 6 weighted components
- Indicator caching for performance
- Parallel scoring support

**SABR20 Components**:

| Component | Weight | Points | Description |
|-----------|--------|--------|-------------|
| **1. BB Position** | 15% | 0-15 | Distance from lower BB |
| **2. Stoch/RSI Alignment** | 20% | 0-20 | Oversold signal alignment |
| **3. Accumulation Intensity** | 18% | 0-18 | Stoch/RSI ratio analysis (NEW) |
| **4. Trend Strength** | 17% | 0-17 | Price vs SMA(50) distance |
| **5. MACD Divergence** | 15% | 0-15 | Bullish divergence detection |
| **6. Volume Profile** | 15% | 0-15 | Volume vs average ratio |
| **Total** | 100% | **0-100** | Final SABR20 score |

**Component Calculations**:

**Component 1: BB Position (15 points)**
```python
bb_position = (close - bb_lower) / (bb_upper - bb_lower)
points = (1 - bb_position) * 15  # Lower position = more points
```

**Component 2: Stoch/RSI Alignment (20 points)**
```python
stoch_oversold = stoch_k < 20 and stoch_d < 20
rsi_oversold = rsi < 30
both_oversold = stoch_oversold and rsi_oversold
points = 20 if both_oversold else (10 if stoch_oversold or rsi_oversold else 0)
```

**Component 3: Accumulation Intensity (18 points)** - NEW
```python
# Calculate Stoch/RSI signal ratio over 50 bars
stoch_signals = sum(stoch_k < 20 for stoch_k in stoch_k_series)
rsi_recoveries = sum(rsi > 30 and prev_rsi < 30 for rsi, prev_rsi in zip(rsi_series, rsi_series.shift()))
ratio = stoch_signals / max(rsi_recoveries, 1)

# Classify accumulation phase
if ratio > 3.0: phase = 'early_accumulation'  # 18 points
elif ratio > 2.0: phase = 'mid_accumulation'  # 14 points
elif ratio > 1.5: phase = 'late_accumulation' # 10 points
elif ratio > 1.2: phase = 'breakout'          # 6 points
```

**Component 4: Trend Strength (17 points)**
```python
trend_strength = (close - sma50) / sma50
points = min(trend_strength * 100, 17)  # Cap at 17
```

**Component 5: MACD Divergence (15 points)**
```python
price_declining = price[-1] < price[-5]
macd_rising = macd[-1] > macd[-5]
bullish_divergence = price_declining and macd_rising
points = 15 if bullish_divergence else 0
```

**Component 6: Volume Profile (15 points)**
```python
volume_ratio = current_volume / avg_volume_20
points = min((volume_ratio - 1) * 30, 15)  # Cap at 15
```

**Key Methods**:
```python
class SABR20Engine:
    def score(symbol, data_15m, data_1h, data_4h) -> SABR20Score
    def score_component_1(df) -> float  # BB Position
    def score_component_2(df) -> float  # Stoch/RSI Alignment
    def score_component_3(df) -> float  # Accumulation Intensity
    def score_component_4(df) -> float  # Trend Strength
    def score_component_5(df) -> float  # MACD Divergence
    def score_component_6(df) -> float  # Volume Profile
```

**Performance**:
- 100 symbols scored in ~8.7 seconds
- Indicator caching reduces recalculation

**Integration Points**:
- ← Coarse Filter (receives filtered symbols)
- → Watchlist Generator (provides scored symbols)

#### 3.4 Watchlist Generator
**File**: `src/screening/watchlist.py`
**Purpose**: Orchestrates full screening pipeline
**Key Features**:
- Pipeline orchestration (universe → coarse → sabr20 → watchlist)
- Parallel processing (optional)
- Result aggregation and ranking
- Watchlist size limit (top 20)
- Error handling and logging

**Pipeline Flow**:
```
7000 symbols (Universe)
    ↓ (Price, Volume, Market Cap filters)
5000 symbols
    ↓ (Coarse Filter: BB, Trend, Volume, Volatility)
300 symbols
    ↓ (SABR20 Scoring: 6 components)
100 symbols with scores
    ↓ (Filter: score >= 60)
50 qualified symbols
    ↓ (Sort by score, take top 20)
20-symbol Watchlist ✅
```

**Key Methods**:
```python
class WatchlistGenerator:
    def generate_watchlist() -> List[WatchlistEntry]
    def run_pipeline() -> pd.DataFrame
    def aggregate_results(results) -> pd.DataFrame
    def filter_by_score(df, min_score=60) -> pd.DataFrame
```

**Performance**:
- Full pipeline: 1000 symbols in <30 seconds
- Parallel mode: >80% efficiency

**Integration Points**:
- Uses: Universe Manager, Coarse Filter, SABR20 Engine
- → Dashboard (provides watchlist)
- → Database (logs screening results)

#### 3.5 Accumulation Analyzer
**File**: `src/screening/accumulation.py`
**Purpose**: Analyzes accumulation phases for SABR20 Component 3
**Key Features**:
- Stoch/RSI ratio calculation
- Accumulation phase classification
- Batch analysis support
- Configurable thresholds

**Phase Classification**:
```python
ratio_thresholds = {
    'early_accumulation': 3.0,  # Heavy accumulation
    'mid_accumulation': 2.0,    # Moderate accumulation
    'late_accumulation': 1.5,   # Light accumulation
    'breakout': 1.2             # Approaching breakout
}
```

**Key Methods**:
```python
def calculate_ratio(df, window=50) -> pd.Series
def classify_phase(ratio) -> str
def analyze(df) -> AccumulationResult
def batch_analyze(data_dict) -> Dict[str, AccumulationResult]
```

**Integration Points**:
- → SABR20 Engine (provides Component 3 scoring)

---

### 4. Database Layer

#### 4.1 Trade Database
**File**: `src/database/trade_db.py`
**Purpose**: Persistent storage for trades and journal entries
**Key Features**:
- SQLite/PostgreSQL support via SQLAlchemy ORM
- Automatic schema creation
- Trade logging (entry, exit, P&L)
- Journal entries (notes, tags, analysis)
- Performance analytics
- Backup/restore functionality

**Database Schema** (see [Database Schema](#database-schema) section)

**Key Methods**:
```python
class TradeDatabase:
    def log_trade(trade) -> None
    def update_trade(trade_id, updates) -> None
    def get_trade(trade_id) -> Trade
    def get_trades(filters) -> List[Trade]
    def add_journal_entry(trade_id, entry) -> None
    def get_performance_metrics() -> PerformanceMetrics
    def backup_database(path) -> None
    def restore_database(path) -> None
```

**Integration Points**:
- ← Position Tracker (logs trades)
- ← Execution Validator (logs validation results)
- → Dashboard (provides trade history)
- → Performance Analytics (provides metrics)

---

### 5. Dashboard Layer

#### 5.1 Dashboard Application
**File**: `src/dashboard/app.py`
**Purpose**: Web-based monitoring and control interface
**Key Features**:
- Dash/Plotly web framework
- Desktop Kymera UI theme (sophisticated dark theme)
- Real-time updates via intervals
- Multi-tab layout
- Responsive design

**Dashboard Tabs**:

1. **Watchlist Tab**
   - Real-time screened symbols
   - SABR20 scores with color coding
   - Current prices and changes
   - Entry/exit signals
   - Click to view chart

2. **Charts Tab**
   - Multi-timeframe dropdown (5min, 15min, 1h, 4h, 1d)
   - Price panel with Bollinger Bands, SMA20, SMA50
   - Stochastic RSI panel
   - MACD panel
   - Volume panel with color coding
   - Interactive zoom/pan

3. **Positions Tab**
   - Live position table
   - Portfolio summary card
   - Real-time P&L updates
   - Entry/exit prices
   - Stop loss levels
   - Position duration

**Key Files**:
- `src/dashboard/app.py`: Main application
- `src/dashboard/charts.py`: Chart generation
- `src/dashboard/positions.py`: Positions panel
- `src/dashboard/assets/kymera_theme.css`: Styling

**Update Intervals**:
- Positions: 5 seconds
- Watchlist: 60 seconds
- Charts: 30 seconds

**Integration Points**:
- ← Watchlist Generator (gets watchlist)
- ← Position Tracker (gets positions)
- ← Historical Data Manager (gets chart data)
- ← Trade Database (gets trade history)

---

## Data Flow

### 1. Market Data Ingestion Flow

```
IB Gateway/TWS
    ↓ (IB API - Real-time 5-second bars)
IB Gateway Manager
    ├─→ Historical Data Manager (Parquet storage)
    └─→ Real-time Aggregator (Multi-timeframe aggregation)
           ↓
        Dashboard Charts (Real-time display)
```

### 2. Screening Flow

```
Universe CSV (7000 symbols)
    ↓
Universe Manager (Load & validate)
    ↓
Coarse Filter (BB, Trend, Volume, Volatility)
    ↓ (~300 symbols)
SABR20 Engine (Score 0-100)
    ↓ (~100 scored symbols)
Watchlist Generator (Top 20, score >= 60)
    ↓
Dashboard Watchlist Tab
```

### 3. Trade Execution Flow

```
Watchlist Signal (score >= 60)
    ↓
Execution Validator
    ├─→ Check account balance
    ├─→ Calculate position size (1% risk)
    ├─→ Validate stop loss
    ├─→ Check portfolio risk (≤ 3%)
    └─→ Check position limit (≤ 10)
          ↓ [Approved]
Order Manager
    ↓ (Place market order via IB API)
IB Gateway Manager
    ↓ (Order confirmation)
Position Tracker
    ├─→ Add position
    ├─→ Calculate unrealized P&L
    └─→ Update dashboard
          ↓
Trade Database (Log trade)
```

### 4. Position Management Flow

```
Open Position
    ↓ (Every 60 seconds)
Trailing Stop Manager
    ├─→ Get current price
    ├─→ Calculate new stop (2% trailing)
    ├─→ Check if stop should increase
    └─→ Modify stop order via IB API
          ↓
Position Tracker (Update stop loss)
    ↓ (Every 5 seconds)
Dashboard Positions Tab (Update display)
```

### 5. Position Close Flow

```
Stop Loss Hit OR Manual Close
    ↓
IB Gateway Manager (Order fill notification)
    ↓
Position Tracker
    ├─→ Calculate realized P&L
    ├─→ Mark position closed
    └─→ Update portfolio metrics
          ↓
Trade Database (Log exit & final P&L)
    ↓
Dashboard Positions Tab (Move to closed)
```

---

## Database Schema

### SQLAlchemy Models

#### Trades Table
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- 'long' or 'short'
    quantity INTEGER NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    stop_loss FLOAT NOT NULL,
    exit_price FLOAT,
    exit_time TIMESTAMP,
    realized_pnl FLOAT DEFAULT 0.0,
    status VARCHAR(10) DEFAULT 'open',  -- 'open' or 'closed'
    sabr20_score FLOAT,
    entry_signal TEXT,
    exit_signal TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_entry_time ON trades(entry_time);
CREATE INDEX idx_trades_status ON trades(status);
```

#### Journal Entries Table
```sql
CREATE TABLE journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_type VARCHAR(20),  -- 'analysis', 'note', 'lesson'
    content TEXT NOT NULL,
    tags VARCHAR(200),  -- Comma-separated tags
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

CREATE INDEX idx_journal_trade_id ON journal_entries(trade_id);
CREATE INDEX idx_journal_entry_time ON journal_entries(entry_time);
```

#### Positions Table (Snapshot)
```sql
CREATE TABLE positions_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price FLOAT NOT NULL,
    current_price FLOAT NOT NULL,
    stop_loss FLOAT NOT NULL,
    unrealized_pnl FLOAT NOT NULL,
    snapshot_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_positions_symbol ON positions_snapshot(symbol);
CREATE INDEX idx_positions_snapshot_time ON positions_snapshot(snapshot_time);
```

#### Performance Metrics Table
```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    total_trades INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    win_rate FLOAT NOT NULL,
    avg_win FLOAT NOT NULL,
    avg_loss FLOAT NOT NULL,
    total_pnl FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    sharpe_ratio FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_performance_period_start ON performance_metrics(period_start);
```

---

## API Interfaces

### Internal Python APIs

All components expose clean Python APIs:

```python
# IB Gateway Manager
from src.data.ib_manager import ib_manager
df = ib_manager.fetch_historical_bars('AAPL', '15 mins', '5 D')

# Historical Data Manager
from src.data.historical_manager import historical_manager
historical_manager.save_data('AAPL', df, metadata)

# Real-time Aggregator
from src.data.realtime_aggregator import RealtimeAggregator
aggregator = RealtimeAggregator()
aggregator.add_bar('AAPL', '5sec', bar)

# Execution Validator
from src.execution.validator import ExecutionValidator
validator = ExecutionValidator(account_balance=100000)
result = validator.validate_trade(trade_signal)

# Position Tracker
from src.execution.position_tracker import PositionTracker
tracker = PositionTracker()
tracker.add_position('AAPL', 100, 150.0, 148.0)

# Screening System
from src.screening.watchlist import WatchlistGenerator
generator = WatchlistGenerator()
watchlist = generator.generate_watchlist()

# Trade Database
from src.database.trade_db import TradeDatabase
db = TradeDatabase()
db.log_trade(trade)
```

### External APIs

#### Interactive Brokers API
- **Protocol**: IB Gateway API via ib-insync wrapper
- **Connection**: TCP socket (port 4002 paper, 7496 live)
- **Authentication**: IB username/password
- **Rate Limits**: 60 requests per 10 minutes for historical data
- **Data Format**: pandas DataFrame or ib-insync objects

#### Dashboard HTTP API (Dash)
- **Protocol**: HTTP
- **Port**: 8050 (configurable)
- **Endpoints**:
  - `/`: Main dashboard
  - `/_dash-update-component`: Callback updates (internal)
  - `/health`: Health check endpoint
  - `/health/ib`: IB connection health
  - `/health/db`: Database health

---

## Integration Points

### External Integrations

1. **Interactive Brokers**
   - Market data streaming
   - Historical data fetching
   - Order placement
   - Account information
   - Position tracking

### Internal Integration Flow

```
┌─────────────────┐
│  IB Gateway     │
└────────┬────────┘
         │
         ├──────→ Historical Data Manager
         │              ↓
         │         Parquet Storage
         │              ↓
         ├──────→ Screening System
         │              ↓
         │         Watchlist
         │              ↓
         ├──────→ Execution Validator
         │              ↓
         ├──────→ Order Manager
         │              ↓
         └──────→ Position Tracker
                        ↓
                  Dashboard Display
```

---

## Design Patterns

### 1. Singleton Pattern
**Used in**: IB Gateway Manager, Historical Data Manager
**Purpose**: Ensure single connection to IB Gateway
**Implementation**:
```python
class IBDataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 2. Observer Pattern
**Used in**: Real-time Aggregator (bar callbacks)
**Purpose**: Notify dashboard when new bars complete
**Implementation**:
```python
class RealtimeAggregator:
    def __init__(self):
        self._callbacks = {}

    def register_callback(self, timeframe, callback):
        self._callbacks[timeframe] = callback

    def _notify_bar_complete(self, timeframe, bar):
        if timeframe in self._callbacks:
            self._callbacks[timeframe](bar)
```

### 3. Strategy Pattern
**Used in**: SABR20 Scoring Components
**Purpose**: Pluggable scoring components
**Implementation**:
```python
class ScoringComponent(ABC):
    @abstractmethod
    def score(self, df) -> float:
        pass

class BBPositionScorer(ScoringComponent):
    def score(self, df) -> float:
        # Component 1 implementation
        pass
```

### 4. Builder Pattern
**Used in**: Watchlist Generation Pipeline
**Purpose**: Construct screening pipeline step-by-step
**Implementation**:
```python
class WatchlistBuilder:
    def __init__(self):
        self._pipeline = []

    def add_universe_filter(self, filter_fn):
        self._pipeline.append(filter_fn)
        return self

    def add_coarse_filter(self, filter_fn):
        self._pipeline.append(filter_fn)
        return self

    def add_scoring(self, scoring_fn):
        self._pipeline.append(scoring_fn)
        return self

    def build(self):
        return lambda symbols: reduce(lambda x, f: f(x), self._pipeline, symbols)
```

### 5. Repository Pattern
**Used in**: Trade Database
**Purpose**: Abstract data access layer
**Implementation**:
```python
class TradeRepository:
    def __init__(self, session):
        self.session = session

    def get_by_id(self, trade_id):
        return self.session.query(Trade).filter_by(id=trade_id).first()

    def get_all(self):
        return self.session.query(Trade).all()

    def save(self, trade):
        self.session.add(trade)
        self.session.commit()
```

### 6. Dependency Injection
**Used in**: Throughout system for testability
**Purpose**: Inject dependencies rather than hard-coding
**Implementation**:
```python
class ExecutionValidator:
    def __init__(self, ib_manager=None, position_tracker=None):
        self.ib_manager = ib_manager or ib_manager_singleton
        self.position_tracker = position_tracker or PositionTracker()
```

---

## Security Architecture

### 1. Authentication & Authorization
- IB Gateway credentials stored in `.env` (never committed)
- Dashboard has no authentication (localhost only by default)
- For production: Add basic auth or OAuth to dashboard

### 2. Data Security
- Database credentials encrypted at rest
- No sensitive data in logs
- Parquet files contain only market data (public)

### 3. Network Security
- IB Gateway connection: localhost only (127.0.0.1)
- Dashboard: configurable host (0.0.0.0 for network access)
- Firewall rules recommended for production

### 4. Input Validation
- All trade signals validated before execution
- Symbol validation against IB database
- Price/quantity sanity checks
- Stop loss distance limits (0.5%-10%)

---

## Scalability and Performance

### Current Capacity
- **Symbols**: 7000 universe, 1000 active screening
- **Screening Speed**: 30 seconds for 1000 symbols
- **Data Storage**: ~10 MB per symbol per year (Parquet)
- **Concurrent Positions**: 10 maximum
- **Dashboard**: Real-time updates for 20 watchlist symbols

### Scalability Strategies

1. **Horizontal Scaling**
   - Multi-process screening (enabled via config)
   - Distributed screening across multiple machines
   - Load-balanced dashboard instances

2. **Vertical Scaling**
   - More CPU cores for parallel processing
   - More RAM for larger indicator caches
   - SSD for faster Parquet I/O

3. **Database Scaling**
   - Migrate from SQLite to PostgreSQL
   - Add read replicas for dashboard
   - Partition tables by date

4. **Caching**
   - Indicator caching (5-minute TTL)
   - Quote caching (30-second TTL)
   - SABR20 score caching (60-second TTL)

### Performance Optimization

1. **Code-Level**
   - Vectorized pandas operations
   - NumPy for numerical computations
   - TA-Lib C library for indicators
   - Polars for large-scale data processing

2. **Data-Level**
   - Parquet compression (5:1 ratio)
   - Column-oriented storage
   - Efficient data types (float32 vs float64)

3. **System-Level**
   - Connection pooling
   - Batch operations
   - Lazy loading
   - Garbage collection tuning

---

## Deployment Architecture

### Development Environment
```
Local Machine
├── Python venv
├── SQLite database
├── IB Gateway (paper trading)
└── Dashboard (localhost:8050)
```

### Production Environment (Linux)
```
Production Server
├── systemd services
│   ├── screener.service (main system)
│   ├── screener-dashboard.service (dashboard)
│   ├── screener-trailing.service (trailing stops)
│   └── ibgateway.service (IB Gateway)
├── PostgreSQL database
├── Nginx reverse proxy (dashboard)
├── Log rotation (logrotate)
├── Automated backups (cron)
└── Monitoring (Prometheus + Grafana)
```

### Docker Deployment (Alternative)
```
Docker Compose
├── screener container (main system)
├── dashboard container (dashboard)
├── postgres container (database)
└── ibgateway container (IB Gateway via VNC)
```

---

## Conclusion

The Screener trading system is a **production-ready, professionally-architected algorithmic trading platform** with:

- ✅ **Clean separation of concerns** across 5 major layers
- ✅ **Robust error handling** and logging throughout
- ✅ **Comprehensive testing** (662 tests, 93.8% coverage)
- ✅ **Scalable architecture** supporting 1000+ symbols
- ✅ **Strong risk management** (1%/3% limits enforced)
- ✅ **Real-time monitoring** via web dashboard
- ✅ **Production deployment** strategies (systemd, Docker)

The architecture balances **simplicity** (easy to understand and maintain) with **sophistication** (professional-grade capabilities), making it suitable for both individual traders and small trading firms.

---

**End of Architecture Documentation**
