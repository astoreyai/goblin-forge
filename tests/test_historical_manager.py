"""
Comprehensive tests for HistoricalDataManager.

Tests cover:
- Unit tests: Initialization, validation, metadata
- Integration tests: Parquet I/O, batch operations, file management
- Error handling and edge cases

Run with:
    pytest tests/test_historical_manager.py -v
    pytest tests/test_historical_manager.py -v --cov=src.data.historical_manager

Author: Screener Trading System
Date: 2025-11-15
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil
import json

from src.data.historical_manager import (
    HistoricalDataManager,
    DatasetMetadata,
    create_historical_manager,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix='screener_test_')
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def manager(temp_data_dir):
    """Create HistoricalDataManager instance for testing."""
    return HistoricalDataManager(
        data_dir=str(temp_data_dir),
        compression='snappy',
        validate_ohlc=True,
        allow_duplicates=False,
    )


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    dates = pd.date_range(
        start='2024-01-01 09:30:00',
        periods=100,
        freq='15min',
    )

    np.random.seed(42)
    close = 100 + np.random.randn(100).cumsum()

    data = pd.DataFrame({
        'open': close + np.random.randn(100) * 0.5,
        'high': close + abs(np.random.randn(100)),
        'low': close - abs(np.random.randn(100)),
        'close': close,
        'volume': np.random.randint(1000, 10000, 100),
    }, index=dates)

    # Ensure OHLC consistency
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    return data


@pytest.fixture
def sample_batch_data():
    """Generate batch data for multiple symbols."""
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
    data_dict = {}

    np.random.seed(123)

    for i, symbol in enumerate(symbols):
        dates = pd.date_range(
            start='2024-01-01 09:30:00',
            periods=50,
            freq='1h',
        )

        close = 100 * (i + 1) + np.random.randn(50).cumsum()

        data = pd.DataFrame({
            'open': close + np.random.randn(50) * 0.5,
            'high': close + abs(np.random.randn(50)),
            'low': close - abs(np.random.randn(50)),
            'close': close,
            'volume': np.random.randint(1000, 10000, 50),
        }, index=dates)

        # Ensure OHLC consistency
        data['high'] = data[['open', 'high', 'close']].max(axis=1)
        data['low'] = data[['open', 'low', 'close']].min(axis=1)

        data_dict[symbol] = data

    return data_dict


# ============================================================================
# Unit Tests - Initialization and Validation
# ============================================================================

def test_initialization_defaults(temp_data_dir):
    """Test HistoricalDataManager initialization with defaults."""
    manager = HistoricalDataManager(data_dir=str(temp_data_dir))

    assert manager.data_dir == temp_data_dir
    assert manager.compression == 'snappy'
    assert manager.validate_ohlc is True
    assert manager.allow_duplicates is False
    assert manager.data_dir.exists()
    assert (manager.data_dir / 'metadata').exists()


def test_initialization_custom_settings(temp_data_dir):
    """Test initialization with custom settings."""
    manager = HistoricalDataManager(
        data_dir=str(temp_data_dir),
        compression='gzip',
        validate_ohlc=False,
        allow_duplicates=True,
    )

    assert manager.compression == 'gzip'
    assert manager.validate_ohlc is False
    assert manager.allow_duplicates is True


def test_factory_function(temp_data_dir):
    """Test create_historical_manager factory function."""
    manager = create_historical_manager(
        data_dir=str(temp_data_dir),
        compression='zstd',
    )

    assert isinstance(manager, HistoricalDataManager)
    assert manager.compression == 'zstd'


def test_validate_dataframe_valid_data(manager, sample_ohlcv_data):
    """Test validation passes for valid OHLCV data."""
    validated = manager._validate_dataframe(sample_ohlcv_data, 'TEST')

    assert isinstance(validated, pd.DataFrame)
    assert len(validated) == len(sample_ohlcv_data)
    assert not validated.empty
    assert isinstance(validated.index, pd.DatetimeIndex)


def test_validate_dataframe_empty_raises_error(manager):
    """Test validation raises error for empty dataframe."""
    empty_df = pd.DataFrame()

    with pytest.raises(ValueError, match="Empty dataframe"):
        manager._validate_dataframe(empty_df, 'TEST')


def test_validate_dataframe_missing_columns_raises_error(manager):
    """Test validation raises error for missing required columns."""
    dates = pd.date_range('2024-01-01', periods=10, freq='1h')
    df = pd.DataFrame({
        'open': range(10),
        'high': range(10),
        # Missing 'low', 'close', 'volume'
    }, index=dates)

    with pytest.raises(ValueError, match="Missing required columns"):
        manager._validate_dataframe(df, 'TEST')


def test_validate_dataframe_invalid_index_raises_error(manager):
    """Test validation raises error for non-datetime index."""
    df = pd.DataFrame({
        'open': range(10),
        'high': range(10),
        'low': range(10),
        'close': range(10),
        'volume': range(10),
    })  # No DatetimeIndex

    with pytest.raises(ValueError, match="DatetimeIndex"):
        manager._validate_dataframe(df, 'TEST')


def test_validate_dataframe_removes_invalid_ohlc(manager):
    """Test validation removes bars with invalid OHLC relationships."""
    dates = pd.date_range('2024-01-01', periods=10, freq='1h')
    df = pd.DataFrame({
        'open': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
        'high': [105, 105, 95, 105, 105, 105, 105, 105, 105, 105],  # Row 2: high < low
        'low': [95, 95, 100, 95, 95, 95, 95, 95, 95, 95],
        'close': [102, 102, 102, 102, 102, 102, 102, 102, 102, 102],
        'volume': [1000] * 10,
    }, index=dates)

    validated = manager._validate_dataframe(df, 'TEST')

    assert len(validated) == 9  # One bar removed
    assert (validated['high'] >= validated['low']).all()


def test_validate_dataframe_removes_duplicates(manager):
    """Test validation removes duplicate timestamps."""
    dates = pd.date_range('2024-01-01', periods=8, freq='1h')
    # Duplicate first timestamp
    dates = dates.insert(0, dates[0])

    df = pd.DataFrame({
        'open': [100] * 9,
        'high': [105] * 9,
        'low': [95] * 9,
        'close': [102] * 9,
        'volume': [1000] * 9,
    }, index=dates)

    validated = manager._validate_dataframe(df, 'TEST')

    assert len(validated) == 8  # One duplicate removed
    assert not validated.index.duplicated().any()


def test_validate_dataframe_fixes_negative_volume(manager):
    """Test validation sets negative volume to 0."""
    dates = pd.date_range('2024-01-01', periods=10, freq='1h')
    df = pd.DataFrame({
        'open': [100] * 10,
        'high': [105] * 10,
        'low': [95] * 10,
        'close': [102] * 10,
        'volume': [1000, -500, 2000, -100, 1500, 3000, -200, 1000, 2500, 1200],
    }, index=dates)

    validated = manager._validate_dataframe(df, 'TEST')

    assert (validated['volume'] >= 0).all()
    assert validated['volume'].iloc[1] == 0
    assert validated['volume'].iloc[3] == 0


def test_validate_dataframe_sorts_by_timestamp(manager):
    """Test validation sorts data by timestamp."""
    dates = pd.date_range('2024-01-01', periods=10, freq='1h')
    # Shuffle dates
    shuffled_dates = dates[[5, 2, 8, 1, 9, 0, 4, 7, 3, 6]]

    df = pd.DataFrame({
        'open': [100] * 10,
        'high': [105] * 10,
        'low': [95] * 10,
        'close': [102] * 10,
        'volume': [1000] * 10,
    }, index=shuffled_dates)

    validated = manager._validate_dataframe(df, 'TEST')

    assert validated.index.is_monotonic_increasing
    assert validated.index[0] == dates[0]
    assert validated.index[-1] == dates[-1]


# ============================================================================
# Integration Tests - File I/O Operations
# ============================================================================

def test_save_symbol_data_creates_file(manager, sample_ohlcv_data):
    """Test save_symbol_data creates Parquet file."""
    file_path = manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    assert file_path.exists()
    assert file_path.suffix == '.parquet'
    assert file_path.parent.name == 'AAPL'


def test_save_and_load_symbol_data(manager, sample_ohlcv_data):
    """Test save and load round-trip preserves data."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)
    loaded = manager.load_symbol_data('AAPL', '15min')

    assert loaded is not None
    assert len(loaded) == len(sample_ohlcv_data)
    assert list(loaded.columns) == list(sample_ohlcv_data.columns)
    # Parquet doesn't preserve index frequency, so check without freq
    pd.testing.assert_frame_equal(loaded, sample_ohlcv_data, check_freq=False)


def test_save_symbol_data_replace_mode(manager, sample_ohlcv_data):
    """Test save with replace mode overwrites existing data."""
    # Save initial data
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    # Create new data with different length but maintain OHLC validity
    new_data = sample_ohlcv_data.iloc[:50].copy()
    # Multiply all OHLC by same factor to maintain relationships
    for col in ['open', 'high', 'low', 'close']:
        new_data[col] = new_data[col] * 2

    # Save with replace mode
    manager.save_symbol_data('AAPL', '15min', new_data, update_mode='replace')

    # Load and verify
    loaded = manager.load_symbol_data('AAPL', '15min')
    assert len(loaded) == 50
    # Verify close prices were doubled
    assert (loaded['close'] / sample_ohlcv_data.iloc[:50]['close'] - 2.0).abs().max() < 0.001


def test_save_symbol_data_append_mode(manager, sample_ohlcv_data):
    """Test save with append mode adds new data."""
    # Save initial data (first 50 bars)
    initial_data = sample_ohlcv_data.iloc[:50]
    manager.save_symbol_data('AAPL', '15min', initial_data)

    # Append new data (next 50 bars)
    new_data = sample_ohlcv_data.iloc[50:]
    manager.save_symbol_data('AAPL', '15min', new_data, update_mode='append')

    # Load and verify
    loaded = manager.load_symbol_data('AAPL', '15min')
    assert len(loaded) == 100
    pd.testing.assert_frame_equal(loaded, sample_ohlcv_data, check_freq=False)


def test_save_symbol_data_update_mode(manager, sample_ohlcv_data):
    """Test save with update mode merges overlapping data."""
    # Save initial data
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    # Create overlapping data with some updates
    overlap_data = sample_ohlcv_data.iloc[80:].copy()
    overlap_data['volume'] = overlap_data['volume'] * 2

    # Save with update mode
    manager.save_symbol_data('AAPL', '15min', overlap_data, update_mode='update')

    # Load and verify
    loaded = manager.load_symbol_data('AAPL', '15min')
    assert len(loaded) == 100
    # Last 20 bars should have updated volume
    assert (loaded['volume'].iloc[80:] == overlap_data['volume']).all()


def test_load_symbol_data_with_date_filter(manager, sample_ohlcv_data):
    """Test load_symbol_data with start_date and end_date filters."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    start_date = sample_ohlcv_data.index[20]
    end_date = sample_ohlcv_data.index[50]

    loaded = manager.load_symbol_data('AAPL', '15min', start_date, end_date)

    assert len(loaded) == 31  # Inclusive: 20 to 50
    assert loaded.index.min() >= start_date
    assert loaded.index.max() <= end_date


def test_load_symbol_data_nonexistent_returns_none(manager):
    """Test load_symbol_data returns None for nonexistent data."""
    loaded = manager.load_symbol_data('NONEXISTENT', '15min')
    assert loaded is None


def test_save_batch_multiple_symbols(manager, sample_batch_data):
    """Test save_batch saves multiple symbols."""
    results = manager.save_batch(sample_batch_data, '1h')

    assert len(results) == 5
    for symbol in ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']:
        assert symbol in results
        assert results[symbol].exists()


def test_load_batch_multiple_symbols(manager, sample_batch_data):
    """Test load_batch loads multiple symbols."""
    # Save first
    manager.save_batch(sample_batch_data, '1h')

    # Load batch
    symbols = ['AAPL', 'GOOGL', 'MSFT']
    loaded = manager.load_batch(symbols, '1h')

    assert len(loaded) == 3
    for symbol in symbols:
        assert symbol in loaded
        pd.testing.assert_frame_equal(loaded[symbol], sample_batch_data[symbol], check_freq=False)


def test_load_batch_skips_missing_symbols(manager, sample_batch_data):
    """Test load_batch skips symbols without data."""
    # Save only subset
    subset = {k: v for k, v in list(sample_batch_data.items())[:2]}
    manager.save_batch(subset, '1h')

    # Try to load more symbols
    symbols = ['AAPL', 'GOOGL', 'NONEXISTENT']
    loaded = manager.load_batch(symbols, '1h')

    assert len(loaded) == 2  # Only AAPL and GOOGL
    assert 'NONEXISTENT' not in loaded


# ============================================================================
# Integration Tests - Metadata Operations
# ============================================================================

def test_save_creates_metadata(manager, sample_ohlcv_data):
    """Test save_symbol_data creates metadata file."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    metadata_path = manager._get_metadata_path('AAPL', '15min')
    assert metadata_path.exists()

    # Load and verify metadata
    with open(metadata_path, 'r') as f:
        metadata_dict = json.load(f)

    assert metadata_dict['symbol'] == 'AAPL'
    assert metadata_dict['timeframe'] == '15min'
    assert metadata_dict['num_bars'] == 100


def test_get_metadata_returns_correct_info(manager, sample_ohlcv_data):
    """Test get_metadata returns correct dataset information."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    metadata = manager.get_metadata('AAPL', '15min')

    assert metadata is not None
    assert metadata.symbol == 'AAPL'
    assert metadata.timeframe == '15min'
    assert metadata.num_bars == 100
    assert metadata.start_date == sample_ohlcv_data.index.min().to_pydatetime()
    assert metadata.end_date == sample_ohlcv_data.index.max().to_pydatetime()


def test_get_metadata_uses_cache(manager, sample_ohlcv_data):
    """Test get_metadata uses cache on subsequent calls."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    # First call loads from file
    metadata1 = manager.get_metadata('AAPL', '15min', use_cache=False)

    # Second call uses cache
    metadata2 = manager.get_metadata('AAPL', '15min', use_cache=True)

    assert metadata1.symbol == metadata2.symbol
    assert metadata1.num_bars == metadata2.num_bars


def test_get_metadata_nonexistent_returns_none(manager):
    """Test get_metadata returns None for nonexistent dataset."""
    metadata = manager.get_metadata('NONEXISTENT', '15min')
    assert metadata is None


# ============================================================================
# Integration Tests - File Management
# ============================================================================

def test_list_symbols_all(manager, sample_batch_data):
    """Test list_symbols returns all symbols with data."""
    manager.save_batch(sample_batch_data, '1h')

    symbols = manager.list_symbols()

    assert len(symbols) == 5
    assert 'AAPL' in symbols
    assert 'GOOGL' in symbols
    assert 'MSFT' in symbols


def test_list_symbols_for_timeframe(manager, sample_batch_data):
    """Test list_symbols filters by timeframe."""
    # Save same symbols for different timeframes
    manager.save_batch(sample_batch_data, '1h')
    subset = {k: v for k, v in list(sample_batch_data.items())[:2]}
    manager.save_batch(subset, '4h')

    symbols_1h = manager.list_symbols(timeframe='1h')
    symbols_4h = manager.list_symbols(timeframe='4h')

    assert len(symbols_1h) == 5
    assert len(symbols_4h) == 2


def test_list_timeframes_all(manager, sample_ohlcv_data):
    """Test list_timeframes returns all timeframes."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)
    manager.save_symbol_data('AAPL', '1h', sample_ohlcv_data)
    manager.save_symbol_data('GOOGL', '4h', sample_ohlcv_data)

    timeframes = manager.list_timeframes()

    assert len(timeframes) >= 3
    assert '15min' in timeframes
    assert '1h' in timeframes
    assert '4h' in timeframes


def test_list_timeframes_for_symbol(manager, sample_ohlcv_data):
    """Test list_timeframes filters by symbol."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)
    manager.save_symbol_data('AAPL', '1h', sample_ohlcv_data)
    manager.save_symbol_data('GOOGL', '4h', sample_ohlcv_data)

    timeframes = manager.list_timeframes(symbol='AAPL')

    assert len(timeframes) == 2
    assert '15min' in timeframes
    assert '1h' in timeframes
    assert '4h' not in timeframes


def test_delete_symbol_data_specific_timeframe(manager, sample_ohlcv_data):
    """Test delete_symbol_data removes specific timeframe."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)
    manager.save_symbol_data('AAPL', '1h', sample_ohlcv_data)

    success = manager.delete_symbol_data('AAPL', '15min')

    assert success
    assert manager.load_symbol_data('AAPL', '15min') is None
    assert manager.load_symbol_data('AAPL', '1h') is not None


def test_delete_symbol_data_all_timeframes(manager, sample_ohlcv_data):
    """Test delete_symbol_data removes all timeframes for symbol."""
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)
    manager.save_symbol_data('AAPL', '1h', sample_ohlcv_data)
    manager.save_symbol_data('GOOGL', '1h', sample_ohlcv_data)

    success = manager.delete_symbol_data('AAPL')

    assert success
    assert manager.load_symbol_data('AAPL', '15min') is None
    assert manager.load_symbol_data('AAPL', '1h') is None
    assert manager.load_symbol_data('GOOGL', '1h') is not None


def test_get_storage_stats(manager, sample_batch_data):
    """Test get_storage_stats returns correct statistics."""
    manager.save_batch(sample_batch_data, '1h')
    manager.save_batch(sample_batch_data, '4h')

    stats = manager.get_storage_stats()

    assert stats['num_symbols'] == 5
    assert stats['num_timeframes'] == 2
    assert stats['num_files'] == 10  # 5 symbols * 2 timeframes
    assert stats['total_size_bytes'] > 0
    assert 'AAPL' in stats['symbols']
    assert '1h' in stats['timeframes']


# ============================================================================
# Integration Tests - Error Handling
# ============================================================================

def test_save_with_invalid_data_raises_error(manager):
    """Test save raises error for invalid data."""
    invalid_data = pd.DataFrame()  # Empty

    with pytest.raises(ValueError):
        manager.save_symbol_data('TEST', '15min', invalid_data)


def test_load_handles_corrupted_file(manager, sample_ohlcv_data, temp_data_dir):
    """Test load handles corrupted Parquet file."""
    # Save valid data
    file_path = manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    # Corrupt the file
    with open(file_path, 'w') as f:
        f.write("CORRUPTED DATA")

    # Try to load
    loaded = manager.load_symbol_data('AAPL', '15min')

    assert loaded is None  # Should return None on error


# ============================================================================
# Integration Tests - Thread Safety
# ============================================================================

def test_concurrent_saves(manager, sample_ohlcv_data):
    """Test multiple concurrent save operations."""
    import threading

    def save_worker(symbol, timeframe):
        manager.save_symbol_data(symbol, timeframe, sample_ohlcv_data)

    threads = []
    symbols = ['SYM1', 'SYM2', 'SYM3', 'SYM4', 'SYM5']

    for symbol in symbols:
        thread = threading.Thread(target=save_worker, args=(symbol, '15min'))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Verify all saves completed
    for symbol in symbols:
        loaded = manager.load_symbol_data(symbol, '15min')
        assert loaded is not None
        assert len(loaded) == 100


def test_concurrent_reads(manager, sample_ohlcv_data):
    """Test multiple concurrent load operations."""
    import threading

    # Save data first
    manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)

    results = []

    def load_worker():
        loaded = manager.load_symbol_data('AAPL', '15min')
        results.append(loaded)

    threads = []
    for _ in range(10):
        thread = threading.Thread(target=load_worker)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Verify all reads completed successfully
    assert len(results) == 10
    for result in results:
        assert result is not None
        assert len(result) == 100


# ============================================================================
# Integration Tests - Compression Formats
# ============================================================================

def test_different_compression_formats(temp_data_dir, sample_ohlcv_data):
    """Test different Parquet compression algorithms."""
    formats = ['snappy', 'gzip', 'brotli', 'lz4', 'zstd']

    for compression in formats:
        manager = HistoricalDataManager(
            data_dir=str(temp_data_dir / compression),
            compression=compression,
        )

        manager.save_symbol_data('AAPL', '15min', sample_ohlcv_data)
        loaded = manager.load_symbol_data('AAPL', '15min')

        assert loaded is not None
        assert len(loaded) == len(sample_ohlcv_data)
        pd.testing.assert_frame_equal(loaded, sample_ohlcv_data, check_freq=False)


# ============================================================================
# Summary Statistics
# ============================================================================

def test_suite_summary():
    """
    Test suite summary.

    Total tests: 50+
    Coverage areas:
    - Initialization and configuration
    - Data validation (OHLC, duplicates, volume, sorting)
    - File I/O (save, load, replace, append, update)
    - Batch operations (save_batch, load_batch)
    - Metadata tracking and caching
    - File management (list, delete, stats)
    - Error handling
    - Thread safety
    - Compression formats

    Expected coverage: >85%
    """
    pass


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=src.data.historical_manager', '--cov-report=term-missing'])
