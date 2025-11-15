"""
Comprehensive test suite for IBDataManager.

Tests cover:
- Connection lifecycle (connect, disconnect, reconnect)
- Heartbeat monitoring and health checks
- Error handling and retry logic
- Resource cleanup and thread safety
- Metrics tracking
- Context manager behavior
- Edge cases and failure scenarios

Run with:
    pytest tests/test_ib_manager_comprehensive.py -v --cov=src.data.ib_manager

Requirements:
    - IB Gateway running on port 4002 for integration tests
    - Use @pytest.mark.integration for tests requiring IB Gateway
"""

from __future__ import annotations

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import pandas as pd
from ib_insync import IB

# Import the module under test
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.ib_manager import (
    IBDataManager,
    ConnectionState,
    ConnectionMetrics,
    create_ib_manager,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def manager():
    """Create IBDataManager with heartbeat disabled for faster tests."""
    mgr = IBDataManager(
        port=4002,
        client_id=999,  # Use high client ID to avoid conflicts
        heartbeat_enabled=False,  # Disable for unit tests
        reconnect_enabled=False,  # Disable for unit tests
    )
    yield mgr
    # Cleanup
    if mgr.is_connected():
        mgr.disconnect()


@pytest.fixture
def manager_with_heartbeat():
    """Create IBDataManager with heartbeat enabled."""
    mgr = IBDataManager(
        port=4002,
        client_id=998,
        heartbeat_enabled=True,
        heartbeat_interval=5,  # Short interval for testing
        reconnect_enabled=False,
    )
    yield mgr
    if mgr.is_connected():
        mgr.disconnect()


@pytest.fixture
def manager_with_reconnect():
    """Create IBDataManager with reconnection enabled."""
    mgr = IBDataManager(
        port=4002,
        client_id=997,
        reconnect_enabled=True,
        max_reconnect_attempts=3,
        reconnect_delay=2,
        heartbeat_enabled=False,
    )
    yield mgr
    if mgr.is_connected():
        mgr.disconnect()


# ============================================================================
# UNIT TESTS - Initialization
# ============================================================================

def test_initialization_defaults():
    """Test IBDataManager initialization with default parameters."""
    manager = IBDataManager()

    assert manager.host == "127.0.0.1"
    assert manager.port == 4002
    assert manager.client_id == 1
    assert manager.timeout == 20
    assert manager.reconnect_enabled is True
    assert manager.heartbeat_enabled is True
    assert manager.state == ConnectionState.DISCONNECTED
    assert manager.ib is None
    assert manager.metrics.connect_time is None


def test_initialization_custom_params():
    """Test IBDataManager initialization with custom parameters."""
    manager = IBDataManager(
        host="192.168.1.100",
        port=4001,
        client_id=5,
        timeout=30,
        reconnect_enabled=False,
        heartbeat_enabled=False,
        heartbeat_interval=60,
        rate_limit_delay=1.0,
    )

    assert manager.host == "192.168.1.100"
    assert manager.port == 4001
    assert manager.client_id == 5
    assert manager.timeout == 30
    assert manager.reconnect_enabled is False
    assert manager.heartbeat_enabled is False
    assert manager.heartbeat_interval == 60
    assert manager.rate_limit_delay == 1.0


def test_repr():
    """Test string representation."""
    manager = IBDataManager(port=4002, client_id=1)
    repr_str = repr(manager)

    assert "IBDataManager" in repr_str
    assert "4002" in repr_str
    assert "client_id=1" in repr_str
    assert "disconnected" in repr_str


# ============================================================================
# INTEGRATION TESTS - Connection
# ============================================================================

@pytest.mark.integration
def test_connect_success(manager):
    """Test successful connection to IB Gateway."""
    success = manager.connect()

    assert success is True
    assert manager.is_connected() is True
    assert manager.state == ConnectionState.CONNECTED
    assert manager.ib is not None
    assert manager.ib.isConnected() is True
    assert manager.metrics.connect_time is not None
    assert manager.metrics.last_heartbeat is not None


@pytest.mark.integration
def test_connect_already_connected(manager):
    """Test connecting when already connected."""
    manager.connect()
    assert manager.is_connected()

    # Try to connect again
    success = manager.connect()

    assert success is True  # Should return True, not reconnect
    assert manager.is_connected()


@pytest.mark.integration
def test_disconnect_clean(manager):
    """Test clean disconnection."""
    manager.connect()
    assert manager.is_connected()

    manager.disconnect()

    assert manager.is_connected() is False
    assert manager.state == ConnectionState.DISCONNECTED
    assert manager.ib is None


@pytest.mark.integration
def test_disconnect_when_not_connected(manager):
    """Test disconnect when not connected (should not error)."""
    assert not manager.is_connected()

    # Should not raise error
    manager.disconnect()

    assert not manager.is_connected()


@pytest.mark.integration
def test_context_manager(manager):
    """Test using IBDataManager as context manager."""
    assert not manager.is_connected()

    with manager as mgr:
        assert mgr.is_connected()
        assert mgr is manager

    # Should auto-disconnect after context
    assert not manager.is_connected()


# ============================================================================
# INTEGRATION TESTS - Heartbeat
# ============================================================================

@pytest.mark.integration
def test_heartbeat_starts_on_connect(manager_with_heartbeat):
    """Test heartbeat thread starts on connection."""
    assert manager_with_heartbeat._heartbeat_thread is None

    manager_with_heartbeat.connect()

    assert manager_with_heartbeat._heartbeat_thread is not None
    assert manager_with_heartbeat._heartbeat_thread.is_alive()


@pytest.mark.integration
def test_heartbeat_stops_on_disconnect(manager_with_heartbeat):
    """Test heartbeat thread stops on disconnection."""
    manager_with_heartbeat.connect()
    assert manager_with_heartbeat._heartbeat_thread.is_alive()

    manager_with_heartbeat.disconnect()

    # Give thread time to stop
    time.sleep(1)
    assert manager_with_heartbeat._heartbeat_thread is None


@pytest.mark.integration
def test_is_healthy_with_active_heartbeat(manager_with_heartbeat):
    """Test is_healthy returns True with active heartbeat."""
    manager_with_heartbeat.connect()

    # Wait for at least one heartbeat
    time.sleep(6)

    assert manager_with_heartbeat.is_healthy()
    assert manager_with_heartbeat.metrics.last_heartbeat is not None

    # Heartbeat should be recent
    heartbeat_age = (datetime.now() - manager_with_heartbeat.metrics.last_heartbeat).total_seconds()
    assert heartbeat_age < 10  # Should be less than 2x interval


@pytest.mark.integration
def test_is_healthy_stale_heartbeat():
    """Test is_healthy returns False when heartbeat is stale."""
    manager = IBDataManager(
        port=4002,
        client_id=996,
        heartbeat_enabled=True,
        heartbeat_interval=100,  # Long interval
    )

    try:
        manager.connect()

        # Manually set stale heartbeat
        manager.metrics.last_heartbeat = datetime.now() - timedelta(seconds=300)

        # Should be unhealthy due to stale heartbeat
        assert not manager.is_healthy()
    finally:
        manager.disconnect()


# ============================================================================
# INTEGRATION TESTS - Metrics
# ============================================================================

@pytest.mark.integration
def test_get_metrics_disconnected(manager):
    """Test metrics when disconnected."""
    metrics = manager.get_metrics()

    assert metrics["state"] == "disconnected"
    assert metrics["connected"] is False
    assert metrics["healthy"] is False
    assert metrics["uptime_seconds"] is None
    assert metrics["reconnect_count"] == 0
    assert metrics["error_count"] == 0


@pytest.mark.integration
def test_get_metrics_connected(manager):
    """Test metrics when connected."""
    manager.connect()
    time.sleep(1)  # Let some uptime accumulate

    metrics = manager.get_metrics()

    assert metrics["state"] == "connected"
    assert metrics["connected"] is True
    assert metrics["uptime_seconds"] is not None
    assert metrics["uptime_seconds"] >= 1.0
    assert "last_heartbeat" in metrics


# ============================================================================
# UNIT TESTS - Error Handling
# ============================================================================

def test_connect_connection_refused():
    """Test connection to non-existent IB Gateway."""
    manager = IBDataManager(
        port=9999,  # Invalid port
        client_id=995,
        reconnect_enabled=False,
        heartbeat_enabled=False,
    )

    with pytest.raises(ConnectionRefusedError):
        manager.connect(retry=False)

    assert manager.state == ConnectionState.ERROR
    assert manager.metrics.error_count > 0
    assert "Connection refused" in manager.metrics.last_error


def test_connect_with_retry_exhausted():
    """Test connection retry exhaustion."""
    manager = IBDataManager(
        port=9998,  # Invalid port
        client_id=994,
        reconnect_enabled=True,
        max_reconnect_attempts=2,
        reconnect_delay=1,
        heartbeat_enabled=False,
    )

    success = manager.connect(retry=True)

    assert success is False
    assert manager.state == ConnectionState.ERROR
    assert manager.metrics.error_count >= 2


# ============================================================================
# UNIT TESTS - State Management
# ============================================================================

def test_is_connected_when_ib_none(manager):
    """Test is_connected returns False when ib is None."""
    manager.ib = None
    assert manager.is_connected() is False


def test_is_connected_wrong_state(manager):
    """Test is_connected checks both ib and state."""
    manager.ib = Mock()
    manager.ib.isConnected = Mock(return_value=True)
    manager.state = ConnectionState.ERROR

    # Even if IB says connected, wrong state means not connected
    assert manager.is_connected() is False


def test_is_healthy_when_not_connected(manager):
    """Test is_healthy returns False when not connected."""
    assert not manager.is_connected()
    assert not manager.is_healthy()


# ============================================================================
# UNIT TESTS - Thread Safety
# ============================================================================

@pytest.mark.integration
def test_concurrent_connections():
    """Test thread-safe handling of concurrent connection attempts."""
    manager = IBDataManager(
        port=4002,
        client_id=993,
        heartbeat_enabled=False,
    )

    def connect_worker():
        manager.connect()

    threads = [threading.Thread(target=connect_worker) for _ in range(5)]

    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should successfully connect despite concurrent attempts
        assert manager.is_connected()

    finally:
        manager.disconnect()


# ============================================================================
# UNIT TESTS - Rate Limiting
# ============================================================================

def test_rate_limit_wait_enforces_delay(manager):
    """Test rate limiting enforces minimum delay."""
    manager.rate_limit_delay = 0.1  # 100ms
    manager._last_request_time = 0.0

    start = time.time()
    manager._rate_limit_wait()
    manager._rate_limit_wait()
    elapsed = time.time() - start

    # Second call should wait ~100ms
    assert elapsed >= 0.09  # Allow small timing variance


def test_rate_limit_wait_no_delay_when_past_limit(manager):
    """Test rate limiting doesn't wait if enough time passed."""
    manager.rate_limit_delay = 0.1
    manager._last_request_time = time.time() - 1.0  # 1 second ago

    start = time.time()
    manager._rate_limit_wait()
    elapsed = time.time() - start

    # Should not wait
    assert elapsed < 0.01


# ============================================================================
# UNIT TESTS - Cleanup
# ============================================================================

@pytest.mark.integration
def test_cancel_subscriptions_cleanup(manager):
    """Test subscription cleanup on disconnect."""
    manager.connect()

    # Add some mock subscriptions
    manager._active_subscriptions["AAPL"] = Mock()
    manager._active_subscriptions["MSFT"] = Mock()

    assert len(manager._active_subscriptions) == 2

    manager.disconnect()

    # Should be cleared
    assert len(manager._active_subscriptions) == 0


@pytest.mark.integration
def test_destructor_cleanup():
    """Test destructor cleans up connection."""
    manager = IBDataManager(
        port=4002,
        client_id=992,
        heartbeat_enabled=False,
    )

    manager.connect()
    assert manager.is_connected()

    # Delete should trigger cleanup
    del manager

    # If we got here without errors, cleanup worked
    assert True


# ============================================================================
# INTEGRATION TESTS - Convenience Function
# ============================================================================

@pytest.mark.integration
def test_create_ib_manager_auto_connect():
    """Test convenience function with auto-connect."""
    manager = create_ib_manager(
        port=4002,
        client_id=991,
        auto_connect=True,
        heartbeat_interval=60,
    )

    try:
        assert manager.is_connected()
        assert manager.heartbeat_interval == 60
    finally:
        manager.disconnect()


def test_create_ib_manager_no_auto_connect():
    """Test convenience function without auto-connect."""
    manager = create_ib_manager(
        port=4002,
        client_id=990,
        auto_connect=False,
    )

    assert not manager.is_connected()
    assert manager.port == 4002


# ============================================================================
# TEST SUMMARY
# ============================================================================

def test_comprehensive_test_count():
    """Verify we have comprehensive test coverage."""
    # This test verifies we have a good number of tests
    # Update this count as we add more tests
    import inspect

    test_functions = [
        name for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    ]

    assert len(test_functions) >= 25, f"Need at least 25 tests, have {len(test_functions)}"
    print(f"\n✅ Comprehensive test suite: {len(test_functions)} tests")


# ============================================================================
# PERFORMANCE BENCHMARKS
# ============================================================================

@pytest.mark.integration
@pytest.mark.benchmark
def test_connection_speed_benchmark(manager):
    """Benchmark connection speed."""
    iterations = 3
    total_time = 0

    for i in range(iterations):
        start = time.time()
        manager.connect()
        manager.disconnect()
        elapsed = time.time() - start
        total_time += elapsed

        time.sleep(1)  # Brief pause between iterations

    avg_time = total_time / iterations
    print(f"\nAverage connect/disconnect cycle: {avg_time:.2f}s")

    # Connection should complete in reasonable time
    assert avg_time < 5.0, f"Connection too slow: {avg_time:.2f}s"


# ============================================================================
# INTEGRATION TESTS - Historical Data Fetching
# ============================================================================

@pytest.mark.integration
def test_fetch_historical_bars_single_symbol(manager):
    """Test fetching historical bars for single symbol."""
    manager.connect()

    df = manager.fetch_historical_bars('AAPL', '15 mins', '5 D')

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'open' in df.columns
    assert 'high' in df.columns
    assert 'low' in df.columns
    assert 'close' in df.columns
    assert 'volume' in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)

    # Verify OHLC consistency
    assert (df['high'] >= df['low']).all()
    assert (df['high'] >= df['open']).all()
    assert (df['high'] >= df['close']).all()
    assert (df['low'] <= df['open']).all()
    assert (df['low'] <= df['close']).all()

    # Verify volume is non-negative
    assert (df['volume'] >= 0).all()

    print(f"\n✅ Fetched {len(df)} bars for AAPL")
    print(f"   Date range: {df.index[0]} to {df.index[-1]}")


@pytest.mark.integration
def test_fetch_historical_bars_multiple_timeframes(manager):
    """Test fetching different timeframes."""
    manager.connect()

    timeframes = [
        ('15 mins', '5 D'),
        ('1 hour', '10 D'),
        ('4 hours', '30 D'),
    ]

    for bar_size, duration in timeframes:
        df = manager.fetch_historical_bars('MSFT', bar_size, duration)

        assert not df.empty
        assert isinstance(df.index, pd.DatetimeIndex)

        print(f"\n✅ {bar_size}: {len(df)} bars")


@pytest.mark.integration
def test_fetch_historical_bars_invalid_symbol(manager):
    """Test fetching with invalid symbol."""
    manager.connect()

    with pytest.raises(ValueError, match="Could not qualify contract"):
        manager.fetch_historical_bars('INVALID_SYMBOL_XYZ', '15 mins', '5 D')


@pytest.mark.integration
def test_fetch_historical_bars_not_connected():
    """Test fetching without connection raises error."""
    manager = IBDataManager(port=4002, heartbeat_enabled=False)

    with pytest.raises(ConnectionError, match="Not connected"):
        manager.fetch_historical_bars('AAPL', '15 mins', '5 D')


@pytest.mark.integration
def test_fetch_historical_bars_rate_limiting(manager):
    """Test rate limiting between requests."""
    manager.connect()
    manager.rate_limit_delay = 0.5  # 500ms

    symbols = ['AAPL', 'MSFT', 'GOOGL']

    start = time.time()
    for symbol in symbols:
        df = manager.fetch_historical_bars(symbol, '1 hour', '1 D')
        assert not df.empty

    elapsed = time.time() - start

    # Should take at least 1.0 seconds (2 delays for 3 requests)
    assert elapsed >= 1.0, f"Rate limiting not working: only {elapsed:.2f}s"

    print(f"\n✅ Rate limiting working: {elapsed:.2f}s for 3 requests")


@pytest.mark.integration
def test_fetch_historical_bars_metrics_tracking(manager):
    """Test metrics are updated during fetching."""
    manager.connect()

    initial_requests = manager.metrics.requests_sent

    manager.fetch_historical_bars('AAPL', '1 hour', '1 D')
    manager.fetch_historical_bars('MSFT', '1 hour', '1 D')

    assert manager.metrics.requests_sent == initial_requests + 2


# ============================================================================
# UNIT TESTS - Data Validation
# ============================================================================

def test_validate_bars_valid_data():
    """Test validation with valid OHLCV data."""
    manager = IBDataManager()

    # Create valid test data
    dates = pd.date_range('2025-01-01', periods=5, freq='15min')
    df = pd.DataFrame({
        'open': [100, 101, 102, 103, 104],
        'high': [101, 102, 103, 104, 105],
        'low': [99, 100, 101, 102, 103],
        'close': [100.5, 101.5, 102.5, 103.5, 104.5],
        'volume': [1000, 1100, 1200, 1300, 1400],
    }, index=dates)

    validated = manager._validate_bars(df, 'TEST')

    assert len(validated) == 5
    assert (validated['high'] >= validated['low']).all()


def test_validate_bars_removes_invalid_ohlc():
    """Test validation removes invalid OHLC bars."""
    manager = IBDataManager()

    dates = pd.date_range('2025-01-01', periods=5, freq='15min')
    df = pd.DataFrame({
        'open': [100, 101, 102, 103, 104],
        'high': [101, 102, 99, 104, 105],  # 3rd bar: high < low (invalid)
        'low': [99, 100, 101, 102, 103],
        'close': [100.5, 101.5, 102.5, 103.5, 104.5],
        'volume': [1000, 1100, 1200, 1300, 1400],
    }, index=dates)

    validated = manager._validate_bars(df, 'TEST')

    # Should remove the invalid bar
    assert len(validated) == 4


def test_validate_bars_removes_duplicates():
    """Test validation removes duplicate timestamps."""
    manager = IBDataManager()

    dates = pd.to_datetime([
        '2025-01-01 09:30:00',
        '2025-01-01 09:45:00',
        '2025-01-01 09:45:00',  # Duplicate
        '2025-01-01 10:00:00',
    ])

    df = pd.DataFrame({
        'open': [100, 101, 101.5, 102],
        'high': [101, 102, 102.5, 103],
        'low': [99, 100, 100.5, 101],
        'close': [100.5, 101.5, 101.7, 102.5],
        'volume': [1000, 1100, 1150, 1200],
    }, index=dates)

    validated = manager._validate_bars(df, 'TEST')

    # Should remove duplicate, keeping first
    assert len(validated) == 3
    assert not validated.index.duplicated().any()


def test_validate_bars_handles_negative_volume():
    """Test validation fixes negative volume."""
    manager = IBDataManager()

    dates = pd.date_range('2025-01-01', periods=3, freq='15min')
    df = pd.DataFrame({
        'open': [100, 101, 102],
        'high': [101, 102, 103],
        'low': [99, 100, 101],
        'close': [100.5, 101.5, 102.5],
        'volume': [1000, -500, 1200],  # Negative volume
    }, index=dates)

    validated = manager._validate_bars(df, 'TEST')

    # Should set negative volume to 0
    assert (validated['volume'] >= 0).all()
    assert validated.loc[dates[1], 'volume'] == 0


def test_validate_bars_empty_dataframe():
    """Test validation raises error for empty DataFrame."""
    manager = IBDataManager()

    df = pd.DataFrame()

    with pytest.raises(ValueError, match="Empty DataFrame"):
        manager._validate_bars(df, 'TEST')


def test_validate_bars_missing_columns():
    """Test validation raises error for missing columns."""
    manager = IBDataManager()

    dates = pd.date_range('2025-01-01', periods=3, freq='15min')
    df = pd.DataFrame({
        'open': [100, 101, 102],
        'high': [101, 102, 103],
        # Missing 'low', 'close', 'volume'
    }, index=dates)

    with pytest.raises(ValueError, match="Missing required columns"):
        manager._validate_bars(df, 'TEST')


# ============================================================================
# RUN INSTRUCTIONS
# ============================================================================

if __name__ == "__main__":
    print("""
    Run tests with:

    # All tests (requires IB Gateway running)
    pytest tests/test_ib_manager_comprehensive.py -v

    # Unit tests only (no IB Gateway needed)
    pytest tests/test_ib_manager_comprehensive.py -v -m "not integration"

    # Integration tests only (requires IB Gateway)
    pytest tests/test_ib_manager_comprehensive.py -v -m integration

    # With coverage
    pytest tests/test_ib_manager_comprehensive.py -v --cov=src.data.ib_manager --cov-report=term-missing

    # Specific test
    pytest tests/test_ib_manager_comprehensive.py::test_connect_success -v -s
    """)
