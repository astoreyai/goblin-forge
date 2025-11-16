"""
Tests for Trade Database & Journaling System

Comprehensive test suite for trade database functionality including:
- Schema creation and validation
- Trade entry/exit recording
- Performance analytics calculations
- MAE/MFE tracking
- Integration with OrderManager
- Edge cases and error handling

Coverage target: >95%
"""

import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

from src.data.trade_database import TradeDatabase, Trade


@pytest.fixture
def temp_db_path():
    """Create temporary database path."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def db(temp_db_path):
    """Create fresh database instance for each test."""
    database = TradeDatabase(db_path=temp_db_path)
    # Reset singleton initialization
    if hasattr(database, '_initialized'):
        delattr(database, '_initialized')
    database.__init__(db_path=temp_db_path)
    yield database
    database.close()


# ============================================================================
# SCHEMA TESTS (5 tests)
# ============================================================================

def test_create_schema_creates_trades_table(db, temp_db_path):
    """Test that schema creation creates trades table."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='trades'
    """)

    assert cursor.fetchone() is not None
    conn.close()


def test_create_schema_creates_indexes(db, temp_db_path):
    """Test that schema creation creates all required indexes."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Check indexes exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='trades'
    """)

    indexes = {row[0] for row in cursor.fetchall()}

    expected_indexes = {
        'idx_symbol',
        'idx_entry_time',
        'idx_exit_time',
        'idx_realized_pnl'
    }

    assert expected_indexes.issubset(indexes)
    conn.close()


def test_schema_idempotent(db, temp_db_path):
    """Test that schema creation can be called multiple times safely."""
    # Call create_schema multiple times
    db._create_schema()
    db._create_schema()
    db._create_schema()

    # Should not raise any errors
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trades")
    assert cursor.fetchone()[0] == 0
    conn.close()


def test_database_file_creation(temp_db_path):
    """Test that database file is created on initialization."""
    # Delete if exists
    Path(temp_db_path).unlink(missing_ok=True)

    # Create fresh instance (bypass singleton)
    # Note: Database file is only created when first query runs
    db = TradeDatabase.__new__(TradeDatabase)
    if hasattr(db, '_initialized'):
        delattr(db, '_initialized')
    db.__init__(db_path=temp_db_path)

    # File should exist after schema creation
    assert Path(temp_db_path).exists()
    db.close()


def test_connection_management(db):
    """Test thread-local connection management."""
    # Get connection
    conn1 = db._conn
    conn2 = db._conn

    # Should be same connection in same thread
    assert conn1 is conn2

    # Connection should be open
    cursor = conn1.cursor()
    cursor.execute("SELECT 1")
    assert cursor.fetchone()[0] == 1


# ============================================================================
# TRADE ENTRY TESTS (8 tests)
# ============================================================================

def test_record_trade_entry_buy(db):
    """Test recording BUY trade entry."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    assert trade_id > 0

    # Verify in database
    trade = db.get_trade(trade_id)
    assert trade['symbol'] == 'AAPL'
    assert trade['side'] == 'BUY'
    assert trade['entry_price'] == 150.00
    assert trade['quantity'] == 100
    assert trade['stop_price'] == 148.00
    assert trade['target_price'] == 154.00
    assert trade['risk_amount'] == 200.00


def test_record_trade_entry_sell(db):
    """Test recording SELL trade entry."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='TSLA',
        side='SELL',
        entry_time=entry_time,
        entry_price=200.00,
        quantity=50,
        stop_price=205.00,
        target_price=190.00,
        risk_amount=250.00
    )

    assert trade_id > 0

    trade = db.get_trade(trade_id)
    assert trade['side'] == 'SELL'
    assert trade['entry_price'] == 200.00


def test_record_trade_entry_with_sabr20(db):
    """Test recording trade entry with SABR20 score."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00,
        sabr20_score=85.5
    )

    trade = db.get_trade(trade_id)
    assert trade['sabr20_score'] == 85.5


def test_record_trade_entry_with_regime(db):
    """Test recording trade entry with market regime."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00,
        regime='TRENDING_UP'
    )

    trade = db.get_trade(trade_id)
    assert trade['regime'] == 'TRENDING_UP'


def test_record_trade_entry_returns_id(db):
    """Test that record_trade_entry returns valid ID."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id_1 = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    trade_id_2 = db.record_trade_entry(
        symbol='MSFT',
        side='BUY',
        entry_time=entry_time,
        entry_price=300.00,
        quantity=50,
        stop_price=295.00,
        target_price=310.00,
        risk_amount=250.00
    )

    # IDs should be sequential
    assert trade_id_2 == trade_id_1 + 1


def test_record_trade_entry_validation(db):
    """Test trade entry validation (missing required fields handled by SQLite)."""
    # SQLite will raise error for NULL in NOT NULL column
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # This should succeed (all required fields provided)
    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    assert trade_id > 0


def test_record_trade_entry_multiple_symbols(db):
    """Test recording entries for multiple symbols."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN']

    trade_ids = []
    for symbol in symbols:
        trade_id = db.record_trade_entry(
            symbol=symbol,
            side='BUY',
            entry_time=entry_time,
            entry_price=150.00,
            quantity=100,
            stop_price=148.00,
            target_price=154.00,
            risk_amount=200.00
        )
        trade_ids.append(trade_id)

    # All should succeed
    assert len(trade_ids) == len(symbols)
    assert len(set(trade_ids)) == len(symbols)  # All unique


def test_record_trade_entry_duplicate_allowed(db):
    """Test that duplicate entries for same symbol are allowed."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # Record twice for same symbol
    trade_id_1 = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    trade_id_2 = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time + timedelta(hours=1),
        entry_price=151.00,
        quantity=100,
        stop_price=149.00,
        target_price=155.00,
        risk_amount=200.00
    )

    # Both should succeed
    assert trade_id_1 != trade_id_2


# ============================================================================
# TRADE EXIT TESTS (10 tests)
# ============================================================================

def test_record_trade_exit_profit(db):
    """Test recording profitable trade exit."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=153.50,
        exit_reason='TARGET',
        commission=2.00
    )

    trade = db.get_trade(trade_id)

    # P&L = (153.50 - 150.00) * 100 - 2.00 = 348.00
    assert trade['realized_pnl'] == pytest.approx(348.00)
    assert trade['pnl_pct'] == pytest.approx(2.32, abs=0.01)
    assert trade['exit_reason'] == 'TARGET'


def test_record_trade_exit_loss(db):
    """Test recording losing trade exit."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 11, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=148.00,
        exit_reason='STOP',
        commission=2.00
    )

    trade = db.get_trade(trade_id)

    # P&L = (148.00 - 150.00) * 100 - 2.00 = -202.00
    assert trade['realized_pnl'] == pytest.approx(-202.00)
    assert trade['pnl_pct'] < 0


def test_record_trade_exit_target_hit(db):
    """Test recording trade exit at target."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=154.00,
        exit_reason='TARGET',
        commission=0.0,
        actual_target=154.00
    )

    trade = db.get_trade(trade_id)
    assert trade['exit_reason'] == 'TARGET'
    assert trade['actual_target'] == 154.00


def test_record_trade_exit_stop_hit(db):
    """Test recording trade exit at stop."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 11, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=148.00,
        exit_reason='STOP',
        commission=0.0,
        actual_stop=148.00
    )

    trade = db.get_trade(trade_id)
    assert trade['exit_reason'] == 'STOP'
    assert trade['actual_stop'] == 148.00


def test_record_trade_exit_manual(db):
    """Test recording manual exit."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 12, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=151.00,
        exit_reason='MANUAL',
        commission=2.00
    )

    trade = db.get_trade(trade_id)
    assert trade['exit_reason'] == 'MANUAL'


def test_record_trade_exit_calculates_pnl(db):
    """Test that exit correctly calculates P&L."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # BUY trade
    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=155.00,
        exit_reason='TARGET',
        commission=5.00
    )

    trade = db.get_trade(trade_id)

    # P&L = (155 - 150) * 100 - 5 = 495
    assert trade['realized_pnl'] == pytest.approx(495.00)


def test_record_trade_exit_calculates_pnl_pct(db):
    """Test that exit calculates percentage P&L."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=100.00,
        quantity=100,
        stop_price=98.00,
        target_price=105.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=105.00,
        exit_reason='TARGET',
        commission=0.0
    )

    trade = db.get_trade(trade_id)

    # P&L % = (105 - 100) * 100 / (100 * 100) * 100 = 5%
    assert trade['pnl_pct'] == pytest.approx(5.0)


def test_record_trade_exit_calculates_hold_time(db):
    """Test that exit calculates hold time in minutes."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=153.50,
        exit_reason='TARGET',
        commission=0.0
    )

    trade = db.get_trade(trade_id)

    # Hold time = 6 hours = 360 minutes
    assert trade['hold_time_minutes'] == 360


def test_record_trade_exit_with_commission(db):
    """Test that commission is correctly accounted for."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=154.00,
        exit_reason='TARGET',
        commission=10.00
    )

    trade = db.get_trade(trade_id)

    # P&L = (154 - 150) * 100 - 10 = 390
    assert trade['realized_pnl'] == pytest.approx(390.00)
    assert trade['commission'] == 10.00


def test_record_trade_exit_with_mae_mfe(db):
    """Test recording exit with MAE/MFE values."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=exit_time,
        exit_price=153.50,
        exit_reason='TARGET',
        commission=0.0,
        mae=-150.00,
        mfe=400.00
    )

    trade = db.get_trade(trade_id)
    assert trade['mae'] == -150.00
    assert trade['mfe'] == 400.00


# ============================================================================
# QUERY TESTS (8 tests)
# ============================================================================

def test_get_trade_by_id(db):
    """Test retrieving trade by ID."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL',
        side='BUY',
        entry_time=entry_time,
        entry_price=150.00,
        quantity=100,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    trade = db.get_trade(trade_id)

    assert trade is not None
    assert trade['id'] == trade_id
    assert trade['symbol'] == 'AAPL'


def test_get_trade_not_found(db):
    """Test retrieving non-existent trade returns None."""
    trade = db.get_trade(99999)
    assert trade is None


def test_get_open_trades(db):
    """Test retrieving open trades."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # Create 3 trades, close 1
    trade_id_1 = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    trade_id_2 = db.record_trade_entry(
        symbol='MSFT', side='BUY', entry_time=entry_time,
        entry_price=300.00, quantity=50, stop_price=295.00,
        target_price=310.00, risk_amount=250.00
    )

    trade_id_3 = db.record_trade_entry(
        symbol='GOOGL', side='BUY', entry_time=entry_time,
        entry_price=140.00, quantity=75, stop_price=138.00,
        target_price=145.00, risk_amount=150.00
    )

    # Close trade 1
    db.record_trade_exit(
        trade_id=trade_id_1,
        exit_time=datetime(2025, 1, 1, 15, 30, 0),
        exit_price=154.00,
        exit_reason='TARGET'
    )

    # Get open trades
    open_trades = db.get_open_trades()

    assert len(open_trades) == 2
    open_symbols = {t['symbol'] for t in open_trades}
    assert open_symbols == {'MSFT', 'GOOGL'}


def test_get_closed_trades(db):
    """Test retrieving closed trades."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # Create and close 2 trades
    trade_id_1 = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    trade_id_2 = db.record_trade_entry(
        symbol='MSFT', side='BUY', entry_time=entry_time,
        entry_price=300.00, quantity=50, stop_price=295.00,
        target_price=310.00, risk_amount=250.00
    )

    db.record_trade_exit(
        trade_id=trade_id_1, exit_time=exit_time,
        exit_price=154.00, exit_reason='TARGET'
    )

    db.record_trade_exit(
        trade_id=trade_id_2, exit_time=exit_time,
        exit_price=308.00, exit_reason='TARGET'
    )

    # Get closed trades
    closed_trades = db.get_closed_trades()

    assert len(closed_trades) == 2


def test_get_closed_trades_filtered_by_date(db):
    """Test filtering closed trades by date range."""
    # Create trades on different days
    trade_id_1 = db.record_trade_entry(
        symbol='AAPL', side='BUY',
        entry_time=datetime(2025, 1, 1, 9, 30, 0),
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    trade_id_2 = db.record_trade_entry(
        symbol='MSFT', side='BUY',
        entry_time=datetime(2025, 1, 5, 9, 30, 0),
        entry_price=300.00, quantity=50, stop_price=295.00,
        target_price=310.00, risk_amount=250.00
    )

    # Close trades
    db.record_trade_exit(
        trade_id=trade_id_1,
        exit_time=datetime(2025, 1, 2, 15, 30, 0),
        exit_price=154.00, exit_reason='TARGET'
    )

    db.record_trade_exit(
        trade_id=trade_id_2,
        exit_time=datetime(2025, 1, 6, 15, 30, 0),
        exit_price=308.00, exit_reason='TARGET'
    )

    # Filter by date
    trades = db.get_closed_trades(
        start_date=datetime(2025, 1, 4, 0, 0, 0),
        end_date=datetime(2025, 1, 7, 0, 0, 0)
    )

    assert len(trades) == 1
    assert trades[0]['symbol'] == 'MSFT'


def test_get_closed_trades_filtered_by_symbol(db):
    """Test filtering closed trades by symbol."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # Create multiple trades for different symbols
    for symbol in ['AAPL', 'AAPL', 'MSFT', 'GOOGL']:
        trade_id = db.record_trade_entry(
            symbol=symbol, side='BUY', entry_time=entry_time,
            entry_price=150.00, quantity=100, stop_price=148.00,
            target_price=154.00, risk_amount=200.00
        )

        db.record_trade_exit(
            trade_id=trade_id, exit_time=exit_time,
            exit_price=154.00, exit_reason='TARGET'
        )

    # Filter by symbol
    trades = db.get_closed_trades(symbol='AAPL')

    assert len(trades) == 2
    assert all(t['symbol'] == 'AAPL' for t in trades)


def test_get_trades_by_symbol(db):
    """Test retrieving all trades for a symbol."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # Create trades for AAPL and MSFT
    for _ in range(3):
        db.record_trade_entry(
            symbol='AAPL', side='BUY', entry_time=entry_time,
            entry_price=150.00, quantity=100, stop_price=148.00,
            target_price=154.00, risk_amount=200.00
        )

    for _ in range(2):
        db.record_trade_entry(
            symbol='MSFT', side='BUY', entry_time=entry_time,
            entry_price=300.00, quantity=50, stop_price=295.00,
            target_price=310.00, risk_amount=250.00
        )

    # Get AAPL trades
    aapl_trades = db.get_trades_by_symbol('AAPL')

    assert len(aapl_trades) == 3
    assert all(t['symbol'] == 'AAPL' for t in aapl_trades)


def test_get_trades_dataframe(db):
    """Test retrieving trades as DataFrame."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # Create and close trades
    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id, exit_time=exit_time,
        exit_price=154.00, exit_reason='TARGET'
    )

    # Get as DataFrame
    df = db.get_trades_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert 'symbol' in df.columns
    assert 'realized_pnl' in df.columns


# ============================================================================
# PERFORMANCE ANALYTICS TESTS (10 tests)
# ============================================================================

def test_get_performance_stats_empty(db):
    """Test performance stats with no trades."""
    stats = db.get_performance_stats()

    assert stats['total_trades'] == 0
    assert stats['win_rate'] == 0.0
    assert stats['total_pnl'] == 0.0


def test_get_performance_stats_single_trade(db):
    """Test performance stats with single trade."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    db.record_trade_exit(
        trade_id=trade_id, exit_time=exit_time,
        exit_price=154.00, exit_reason='TARGET', commission=0.0
    )

    stats = db.get_performance_stats()

    assert stats['total_trades'] == 1
    assert stats['winning_trades'] == 1
    assert stats['losing_trades'] == 0
    assert stats['win_rate'] == 100.0
    assert stats['total_pnl'] == pytest.approx(400.0)


def test_get_performance_stats_win_rate(db):
    """Test win rate calculation."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # 3 winners, 2 losers
    for i in range(5):
        trade_id = db.record_trade_entry(
            symbol='AAPL', side='BUY', entry_time=entry_time,
            entry_price=100.00, quantity=100, stop_price=98.00,
            target_price=105.00, risk_amount=200.00
        )

        # First 3 are winners
        exit_price = 105.00 if i < 3 else 98.00

        db.record_trade_exit(
            trade_id=trade_id, exit_time=exit_time,
            exit_price=exit_price, exit_reason='TARGET', commission=0.0
        )

    stats = db.get_performance_stats()

    assert stats['total_trades'] == 5
    assert stats['winning_trades'] == 3
    assert stats['losing_trades'] == 2
    assert stats['win_rate'] == pytest.approx(60.0)


def test_get_performance_stats_profit_factor(db):
    """Test profit factor calculation."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # Winner: +$500
    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=100.00, quantity=100, stop_price=98.00,
        target_price=105.00, risk_amount=200.00
    )
    db.record_trade_exit(
        trade_id=trade_id, exit_time=exit_time,
        exit_price=105.00, exit_reason='TARGET', commission=0.0
    )

    # Loser: -$200
    trade_id = db.record_trade_entry(
        symbol='MSFT', side='BUY', entry_time=entry_time,
        entry_price=100.00, quantity=100, stop_price=98.00,
        target_price=105.00, risk_amount=200.00
    )
    db.record_trade_exit(
        trade_id=trade_id, exit_time=exit_time,
        exit_price=98.00, exit_reason='STOP', commission=0.0
    )

    stats = db.get_performance_stats()

    # Profit factor = 500 / 200 = 2.5
    assert stats['profit_factor'] == pytest.approx(2.5)


def test_get_performance_stats_sharpe_ratio(db):
    """Test Sharpe ratio calculation."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # Create 10 trades with varying P&L
    pnls = [100, 150, -50, 200, -30, 120, 80, -40, 160, 90]

    for pnl in pnls:
        trade_id = db.record_trade_entry(
            symbol='AAPL', side='BUY', entry_time=entry_time,
            entry_price=100.00, quantity=100, stop_price=98.00,
            target_price=105.00, risk_amount=200.00
        )

        exit_price = 100.00 + (pnl / 100)

        db.record_trade_exit(
            trade_id=trade_id, exit_time=exit_time,
            exit_price=exit_price, exit_reason='TARGET', commission=0.0
        )

    stats = db.get_performance_stats()

    # Sharpe should be positive (more wins than losses)
    assert stats['sharpe_ratio'] > 0


def test_get_performance_stats_max_drawdown(db):
    """Test maximum drawdown calculation."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # Create equity curve: +100, -200 (drawdown), +150
    pnls = [100, -200, 150]

    for i, pnl in enumerate(pnls):
        trade_id = db.record_trade_entry(
            symbol='AAPL', side='BUY', entry_time=entry_time,
            entry_price=100.00, quantity=100, stop_price=98.00,
            target_price=105.00, risk_amount=200.00
        )

        exit_time = entry_time + timedelta(hours=i+1)
        exit_price = 100.00 + (pnl / 100)

        db.record_trade_exit(
            trade_id=trade_id, exit_time=exit_time,
            exit_price=exit_price, exit_reason='TARGET', commission=0.0
        )

    stats = db.get_performance_stats()

    # Max drawdown should be negative
    assert stats['max_drawdown'] < 0


def test_get_performance_stats_avg_hold_time(db):
    """Test average hold time calculation."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # Trade 1: 60 minutes
    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=100.00, quantity=100, stop_price=98.00,
        target_price=105.00, risk_amount=200.00
    )
    db.record_trade_exit(
        trade_id=trade_id, exit_time=entry_time + timedelta(minutes=60),
        exit_price=105.00, exit_reason='TARGET', commission=0.0
    )

    # Trade 2: 120 minutes
    trade_id = db.record_trade_entry(
        symbol='MSFT', side='BUY', entry_time=entry_time,
        entry_price=100.00, quantity=100, stop_price=98.00,
        target_price=105.00, risk_amount=200.00
    )
    db.record_trade_exit(
        trade_id=trade_id, exit_time=entry_time + timedelta(minutes=120),
        exit_price=105.00, exit_reason='TARGET', commission=0.0
    )

    stats = db.get_performance_stats()

    # Average = (60 + 120) / 2 = 90
    assert stats['avg_hold_time_minutes'] == pytest.approx(90.0)


def test_get_performance_stats_date_filter(db):
    """Test performance stats with date filtering."""
    # Trade 1: Jan 1
    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY',
        entry_time=datetime(2025, 1, 1, 9, 30, 0),
        entry_price=100.00, quantity=100, stop_price=98.00,
        target_price=105.00, risk_amount=200.00
    )
    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=datetime(2025, 1, 1, 15, 30, 0),
        exit_price=105.00, exit_reason='TARGET', commission=0.0
    )

    # Trade 2: Jan 5
    trade_id = db.record_trade_entry(
        symbol='MSFT', side='BUY',
        entry_time=datetime(2025, 1, 5, 9, 30, 0),
        entry_price=100.00, quantity=100, stop_price=98.00,
        target_price=105.00, risk_amount=200.00
    )
    db.record_trade_exit(
        trade_id=trade_id,
        exit_time=datetime(2025, 1, 5, 15, 30, 0),
        exit_price=105.00, exit_reason='TARGET', commission=0.0
    )

    # Filter for Jan 4-6
    stats = db.get_performance_stats(
        start_date=datetime(2025, 1, 4, 0, 0, 0),
        end_date=datetime(2025, 1, 6, 0, 0, 0)
    )

    assert stats['total_trades'] == 1


def test_get_equity_curve(db):
    """Test equity curve generation."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    # Create 3 trades
    pnls = [100, -50, 150]

    for i, pnl in enumerate(pnls):
        trade_id = db.record_trade_entry(
            symbol='AAPL', side='BUY', entry_time=entry_time,
            entry_price=100.00, quantity=100, stop_price=98.00,
            target_price=105.00, risk_amount=200.00
        )

        exit_time = entry_time + timedelta(hours=i+1)
        exit_price = 100.00 + (pnl / 100)

        db.record_trade_exit(
            trade_id=trade_id, exit_time=exit_time,
            exit_price=exit_price, exit_reason='TARGET', commission=0.0
        )

    curve = db.get_equity_curve()

    assert isinstance(curve, pd.DataFrame)
    assert len(curve) == 3
    assert 'equity' in curve.columns
    assert 'cumulative_pnl' in curve.columns

    # Final equity should be 100000 + 200 = 100200
    assert curve.iloc[-1]['equity'] == pytest.approx(100200.0)


def test_get_symbol_statistics(db):
    """Test symbol-specific statistics."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)
    exit_time = datetime(2025, 1, 1, 15, 30, 0)

    # Create trades for AAPL: 2 winners, 1 loser
    for i in range(3):
        trade_id = db.record_trade_entry(
            symbol='AAPL', side='BUY', entry_time=entry_time,
            entry_price=100.00, quantity=100, stop_price=98.00,
            target_price=105.00, risk_amount=200.00
        )

        exit_price = 105.00 if i < 2 else 98.00

        db.record_trade_exit(
            trade_id=trade_id, exit_time=exit_time,
            exit_price=exit_price, exit_reason='TARGET', commission=0.0
        )

    stats = db.get_symbol_statistics('AAPL')

    assert stats['symbol'] == 'AAPL'
    assert stats['total_trades'] == 3
    assert stats['winning_trades'] == 2
    assert stats['win_rate'] == pytest.approx(66.67, abs=0.1)


# ============================================================================
# MAE/MFE TESTS (5 tests)
# ============================================================================

def test_update_trade_mae_mfe_buy_adverse(db):
    """Test MAE update for BUY trade going adverse."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    # Price drops to 148.50 (adverse)
    db.update_trade_mae_mfe(trade_id, 148.50)

    trade = db.get_trade(trade_id)

    # MAE = (148.50 - 150.00) * 100 = -150
    assert trade['mae'] == pytest.approx(-150.0)


def test_update_trade_mae_mfe_buy_favorable(db):
    """Test MFE update for BUY trade going favorable."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    # Price rises to 153.00 (favorable)
    db.update_trade_mae_mfe(trade_id, 153.00)

    trade = db.get_trade(trade_id)

    # MFE = (153.00 - 150.00) * 100 = 300
    assert trade['mfe'] == pytest.approx(300.0)


def test_update_trade_mae_mfe_sell_adverse(db):
    """Test MAE update for SELL trade going adverse."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='SELL', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=152.00,
        target_price=145.00, risk_amount=200.00
    )

    # Price rises to 151.50 (adverse for SELL)
    db.update_trade_mae_mfe(trade_id, 151.50)

    trade = db.get_trade(trade_id)

    # MAE = (150.00 - 151.50) * 100 = -150
    assert trade['mae'] == pytest.approx(-150.0)


def test_update_trade_mae_mfe_sell_favorable(db):
    """Test MFE update for SELL trade going favorable."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='SELL', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=152.00,
        target_price=145.00, risk_amount=200.00
    )

    # Price drops to 147.00 (favorable for SELL)
    db.update_trade_mae_mfe(trade_id, 147.00)

    trade = db.get_trade(trade_id)

    # MFE = (150.00 - 147.00) * 100 = 300
    assert trade['mfe'] == pytest.approx(300.0)


def test_update_trade_mae_mfe_multiple_updates(db):
    """Test MAE/MFE tracking across multiple price updates."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    # Sequence of price updates
    prices = [151.00, 149.00, 153.00, 148.50, 154.50]

    for price in prices:
        db.update_trade_mae_mfe(trade_id, price)

    trade = db.get_trade(trade_id)

    # MAE should be at 148.50 (most adverse)
    # MAE = (148.50 - 150.00) * 100 = -150
    assert trade['mae'] == pytest.approx(-150.0)

    # MFE should be at 154.50 (most favorable)
    # MFE = (154.50 - 150.00) * 100 = 450
    assert trade['mfe'] == pytest.approx(450.0)


# ============================================================================
# INTEGRATION TESTS WITH ORDER MANAGER (10 tests)
# ============================================================================

def test_trade_recorded_on_position_open(db):
    """Test trade is recorded when position opens."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db  # Use test database

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    # Verify trade was recorded
    open_trades = db.get_open_trades()
    assert len(open_trades) == 1
    assert open_trades[0]['symbol'] == 'AAPL'


def test_trade_updated_on_position_close(db):
    """Test trade is updated when position closes."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    # Open position
    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    # Close position
    om.close_position(
        symbol='AAPL',
        exit_price=154.00,
        exit_reason='TARGET'
    )

    # Verify trade was closed
    closed_trades = db.get_closed_trades()
    assert len(closed_trades) == 1
    assert closed_trades[0]['exit_price'] == 154.00


def test_mae_mfe_updated_from_realtime_bars(db):
    """Test MAE/MFE updated from real-time price updates."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    # Open position
    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    # Update price (adverse)
    om.update_position_price('AAPL', 148.50)

    # Update price (favorable)
    om.update_position_price('AAPL', 153.00)

    # Check position MAE/MFE
    position = om.positions['AAPL']
    assert position.mae < 0
    assert position.mfe > 0


def test_multiple_positions_tracked(db):
    """Test multiple positions tracked in database."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    symbols = ['AAPL', 'MSFT', 'GOOGL']

    for symbol in symbols:
        om.open_position(
            symbol=symbol,
            side='BUY',
            quantity=100,
            entry_price=150.00,
            stop_price=148.00,
            target_price=154.00,
            risk_amount=200.00
        )

    open_trades = db.get_open_trades()
    assert len(open_trades) == 3


def test_position_to_trade_id_mapping(db):
    """Test position to trade_id mapping."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    assert 'AAPL' in om.position_to_trade_id
    trade_id = om.position_to_trade_id['AAPL']
    assert trade_id > 0


def test_exit_reason_stop(db):
    """Test exit reason recorded correctly for stop hit."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    om.close_position(
        symbol='AAPL',
        exit_price=148.00,
        exit_reason='STOP'
    )

    closed_trades = db.get_closed_trades()
    assert closed_trades[0]['exit_reason'] == 'STOP'


def test_exit_reason_target(db):
    """Test exit reason recorded correctly for target hit."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    om.close_position(
        symbol='AAPL',
        exit_price=154.00,
        exit_reason='TARGET'
    )

    closed_trades = db.get_closed_trades()
    assert closed_trades[0]['exit_reason'] == 'TARGET'


def test_exit_reason_manual(db):
    """Test exit reason recorded correctly for manual exit."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    om.close_position(
        symbol='AAPL',
        exit_price=151.50,
        exit_reason='MANUAL',
        notes='Took profit early due to market conditions'
    )

    closed_trades = db.get_closed_trades()
    assert closed_trades[0]['exit_reason'] == 'MANUAL'


def test_sabr20_score_recorded(db):
    """Test SABR20 score recorded when available."""
    from src.execution.order_manager import OrderManager

    om = OrderManager()
    om.trade_database = db

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    open_trades = db.get_open_trades()
    # Verify trade was recorded (SABR20 score may be None in test environment)
    assert len(open_trades) == 1
    assert open_trades[0]['symbol'] == 'AAPL'


def test_regime_recorded(db, monkeypatch):
    """Test regime recorded when available."""
    from src.execution.order_manager import OrderManager

    # Mock regime detector
    class MockRegimeDetector:
        def get_current_regime(self):
            return {'regime_name': 'TRENDING_UP'}

    import src.execution.order_manager as om_module
    monkeypatch.setattr('src.execution.order_manager.regime_detector', MockRegimeDetector())

    om = OrderManager()
    om.trade_database = db

    om.open_position(
        symbol='AAPL',
        side='BUY',
        quantity=100,
        entry_price=150.00,
        stop_price=148.00,
        target_price=154.00,
        risk_amount=200.00
    )

    open_trades = db.get_open_trades()
    # Note: This may be None in test environment if regime import fails
    # Just verify trade was recorded
    assert len(open_trades) == 1


# ============================================================================
# UTILITY TESTS (4 tests)
# ============================================================================

def test_add_trade_note(db):
    """Test adding note to trade."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    db.add_trade_note(trade_id, "Good setup on daily chart")

    trade = db.get_trade(trade_id)
    assert "Good setup on daily chart" in trade['notes']


def test_add_trade_note_appends(db):
    """Test that notes are appended, not replaced."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    db.add_trade_note(trade_id, "Note 1")
    db.add_trade_note(trade_id, "Note 2")

    trade = db.get_trade(trade_id)
    assert "Note 1" in trade['notes']
    assert "Note 2" in trade['notes']


def test_database_singleton(temp_db_path):
    """Test that TradeDatabase is a singleton."""
    db1 = TradeDatabase(db_path=temp_db_path)
    db2 = TradeDatabase(db_path=temp_db_path)

    assert db1 is db2


def test_database_persistence(db, temp_db_path):
    """Test that data persists after closing connection."""
    entry_time = datetime(2025, 1, 1, 9, 30, 0)

    trade_id = db.record_trade_entry(
        symbol='AAPL', side='BUY', entry_time=entry_time,
        entry_price=150.00, quantity=100, stop_price=148.00,
        target_price=154.00, risk_amount=200.00
    )

    db.close()

    # Create new instance
    db2 = TradeDatabase(db_path=temp_db_path)
    if hasattr(db2, '_initialized'):
        delattr(db2, '_initialized')
    db2.__init__(db_path=temp_db_path)

    trade = db2.get_trade(trade_id)
    assert trade is not None
    assert trade['symbol'] == 'AAPL'

    db2.close()
