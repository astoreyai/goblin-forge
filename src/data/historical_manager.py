"""
Historical data management with Parquet storage.

This module provides efficient storage and retrieval of historical OHLCV data
using Parquet format for optimal compression and query performance.

Features:
- Parquet-based storage with automatic compression
- Batch operations for multiple symbols
- Data validation and integrity checks
- Efficient incremental updates
- Metadata tracking
- Thread-safe operations

Author: Screener Trading System
Date: 2025-11-15
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import threading

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger


@dataclass
class DatasetMetadata:
    """Metadata for a stored dataset."""

    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    num_bars: int
    file_path: str
    last_updated: datetime
    file_size_bytes: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'num_bars': self.num_bars,
            'file_path': self.file_path,
            'last_updated': self.last_updated.isoformat(),
            'file_size_bytes': self.file_size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DatasetMetadata':
        """Create from dictionary."""
        return cls(
            symbol=data['symbol'],
            timeframe=data['timeframe'],
            start_date=datetime.fromisoformat(data['start_date']),
            end_date=datetime.fromisoformat(data['end_date']),
            num_bars=data['num_bars'],
            file_path=data['file_path'],
            last_updated=datetime.fromisoformat(data['last_updated']),
            file_size_bytes=data['file_size_bytes'],
        )


class HistoricalDataManager:
    """
    Manage historical OHLCV data with Parquet storage.

    This class provides efficient storage and retrieval of historical market data
    using Apache Parquet format. Features include:
    - Automatic directory structure creation
    - Data validation and cleaning
    - Incremental updates
    - Batch operations
    - Metadata tracking
    - Thread-safe operations

    Directory Structure:
        data_dir/
            {symbol}/
                {timeframe}.parquet
            metadata/
                {symbol}_{timeframe}.json

    Parameters:
    -----------
    data_dir : str or Path
        Root directory for data storage
    compression : str, default='snappy'
        Parquet compression algorithm (snappy, gzip, brotli, lz4, zstd)
    validate_ohlc : bool, default=True
        Validate OHLC relationships before saving
    allow_duplicates : bool, default=False
        Allow duplicate timestamps (not recommended)

    Examples:
    ---------
    >>> manager = HistoricalDataManager('data/historical')
    >>> manager.save_symbol_data('AAPL', '15min', df)
    >>> data = manager.load_symbol_data('AAPL', '15min')
    >>> manager.save_batch({'AAPL': df1, 'GOOGL': df2}, '1h')
    """

    def __init__(
        self,
        data_dir: str = 'data/historical',
        compression: str = 'snappy',
        validate_ohlc: bool = True,
        allow_duplicates: bool = False,
    ):
        """Initialize historical data manager."""
        self.data_dir = Path(data_dir)
        self.compression = compression
        self.validate_ohlc = validate_ohlc
        self.allow_duplicates = allow_duplicates

        # Thread safety
        self._lock = threading.RLock()

        # Create directory structure
        self._ensure_directories()

        # Metadata cache
        self._metadata_cache: Dict[Tuple[str, str], DatasetMetadata] = {}

        logger.info(
            f"Initialized HistoricalDataManager at {self.data_dir} "
            f"with compression={compression}"
        )

    def _ensure_directories(self) -> None:
        """Create necessary directory structure."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / 'metadata').mkdir(exist_ok=True)
        logger.debug(f"Ensured directory structure at {self.data_dir}")

    def _get_file_path(self, symbol: str, timeframe: str) -> Path:
        """
        Get file path for symbol and timeframe.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : str
            Timeframe (e.g., '15min', '1h', '4h')

        Returns:
        --------
        Path
            Full path to Parquet file
        """
        symbol_dir = self.data_dir / symbol
        symbol_dir.mkdir(exist_ok=True)
        return symbol_dir / f"{timeframe}.parquet"

    def _get_metadata_path(self, symbol: str, timeframe: str) -> Path:
        """Get metadata file path."""
        return self.data_dir / 'metadata' / f"{symbol}_{timeframe}.json"

    def _validate_dataframe(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Validate and clean OHLCV dataframe.

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV data to validate
        symbol : str
            Symbol name (for logging)

        Returns:
        --------
        pd.DataFrame
            Validated and cleaned dataframe

        Raises:
        -------
        ValueError
            If dataframe is empty or missing required columns
        """
        if df.empty:
            raise ValueError(f"Empty dataframe for {symbol}")

        # Check required columns
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Missing required columns for {symbol}: {missing_cols}"
            )

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(
                f"DataFrame index must be DatetimeIndex for {symbol}, "
                f"got {type(df.index)}"
            )

        # Validate OHLC relationships
        if self.validate_ohlc:
            invalid_bars = (
                (df['high'] < df['low']) |
                (df['high'] < df['open']) |
                (df['high'] < df['close']) |
                (df['low'] > df['open']) |
                (df['low'] > df['close'])
            )
            num_invalid = invalid_bars.sum()
            if num_invalid > 0:
                logger.warning(
                    f"Found {num_invalid} invalid OHLC bars for {symbol}, removing"
                )
                df = df[~invalid_bars].copy()

        # Remove duplicates
        if not self.allow_duplicates:
            num_duplicates = df.index.duplicated().sum()
            if num_duplicates > 0:
                logger.warning(
                    f"Found {num_duplicates} duplicate timestamps for {symbol}, "
                    f"keeping first occurrence"
                )
                df = df[~df.index.duplicated(keep='first')].copy()

        # Sort by timestamp
        df = df.sort_index()

        # Ensure positive volume
        if (df['volume'] < 0).any():
            logger.warning(f"Found negative volume for {symbol}, setting to 0")
            df.loc[df['volume'] < 0, 'volume'] = 0

        return df

    def save_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
        update_mode: str = 'replace',
    ) -> Path:
        """
        Save OHLCV data for a single symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol (e.g., 'AAPL')
        timeframe : str
            Timeframe identifier (e.g., '15min', '1h', '4h')
        data : pd.DataFrame
            OHLCV data with DatetimeIndex
        update_mode : str, default='replace'
            How to handle existing data:
            - 'replace': Replace entire dataset
            - 'append': Append new data (removes duplicates)
            - 'update': Update overlapping periods, append new

        Returns:
        --------
        Path
            Path to saved Parquet file

        Raises:
        -------
        ValueError
            If data validation fails
        """
        with self._lock:
            logger.info(
                f"Saving {len(data)} bars for {symbol} {timeframe} "
                f"(mode={update_mode})"
            )

            # Validate data
            data = self._validate_dataframe(data, symbol)

            file_path = self._get_file_path(symbol, timeframe)

            # Handle update modes
            if update_mode in ('append', 'update') and file_path.exists():
                try:
                    existing = pd.read_parquet(file_path)

                    if update_mode == 'append':
                        # Simple append with duplicate removal
                        combined = pd.concat([existing, data])
                        combined = combined[~combined.index.duplicated(keep='last')]
                        data = combined.sort_index()
                    else:  # update
                        # Update overlapping, append new
                        combined = pd.concat([existing, data])
                        combined = combined[~combined.index.duplicated(keep='last')]
                        data = combined.sort_index()

                    logger.debug(
                        f"Combined with existing data: {len(existing)} + "
                        f"{len(data) - len(existing)} = {len(data)} bars"
                    )
                except Exception as e:
                    logger.error(
                        f"Error loading existing data for {symbol} {timeframe}: {e}, "
                        f"falling back to replace mode"
                    )

            # Write to Parquet
            try:
                data.to_parquet(
                    file_path,
                    compression=self.compression,
                    index=True,
                    engine='pyarrow',
                )

                # Update metadata
                self._save_metadata(symbol, timeframe, data, file_path)

                logger.info(
                    f"Successfully saved {len(data)} bars for {symbol} {timeframe} "
                    f"to {file_path}"
                )

                return file_path

            except Exception as e:
                logger.error(f"Error saving data for {symbol} {timeframe}: {e}")
                raise

    def _save_metadata(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
        file_path: Path,
    ) -> None:
        """Save metadata for dataset."""
        metadata = DatasetMetadata(
            symbol=symbol,
            timeframe=timeframe,
            start_date=data.index.min().to_pydatetime(),
            end_date=data.index.max().to_pydatetime(),
            num_bars=len(data),
            file_path=str(file_path),
            last_updated=datetime.now(),
            file_size_bytes=file_path.stat().st_size,
        )

        # Save to file
        metadata_path = self._get_metadata_path(symbol, timeframe)
        import json
        with open(metadata_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)

        # Update cache
        self._metadata_cache[(symbol, timeframe)] = metadata

    def load_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load OHLCV data for a single symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : str
            Timeframe identifier
        start_date : datetime, optional
            Filter data from this date (inclusive)
        end_date : datetime, optional
            Filter data to this date (inclusive)

        Returns:
        --------
        pd.DataFrame or None
            OHLCV data with DatetimeIndex, or None if not found
        """
        with self._lock:
            file_path = self._get_file_path(symbol, timeframe)

            if not file_path.exists():
                logger.warning(f"No data found for {symbol} {timeframe}")
                return None

            try:
                logger.debug(f"Loading data for {symbol} {timeframe} from {file_path}")
                df = pd.read_parquet(file_path)

                # Apply date filters
                if start_date is not None:
                    df = df[df.index >= start_date]
                if end_date is not None:
                    df = df[df.index <= end_date]

                logger.info(f"Loaded {len(df)} bars for {symbol} {timeframe}")
                return df

            except Exception as e:
                logger.error(f"Error loading data for {symbol} {timeframe}: {e}")
                return None

    def save_batch(
        self,
        data_dict: Dict[str, pd.DataFrame],
        timeframe: str,
        update_mode: str = 'replace',
    ) -> Dict[str, Path]:
        """
        Save data for multiple symbols.

        Parameters:
        -----------
        data_dict : dict
            Dictionary mapping symbols to DataFrames
        timeframe : str
            Timeframe identifier (same for all symbols)
        update_mode : str, default='replace'
            Update mode (replace/append/update)

        Returns:
        --------
        dict
            Dictionary mapping symbols to file paths
        """
        logger.info(
            f"Saving batch of {len(data_dict)} symbols for timeframe {timeframe}"
        )

        results = {}
        errors = []

        for symbol, data in data_dict.items():
            try:
                file_path = self.save_symbol_data(
                    symbol, timeframe, data, update_mode
                )
                results[symbol] = file_path
            except Exception as e:
                logger.error(f"Error saving {symbol}: {e}")
                errors.append((symbol, str(e)))

        if errors:
            logger.warning(
                f"Batch save completed with {len(errors)} errors: "
                f"{[s for s, _ in errors]}"
            )
        else:
            logger.info(f"Batch save completed successfully for {len(results)} symbols")

        return results

    def load_batch(
        self,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load data for multiple symbols.

        Parameters:
        -----------
        symbols : list
            List of stock symbols
        timeframe : str
            Timeframe identifier
        start_date : datetime, optional
            Filter from date
        end_date : datetime, optional
            Filter to date

        Returns:
        --------
        dict
            Dictionary mapping symbols to DataFrames (excludes missing data)
        """
        logger.info(
            f"Loading batch of {len(symbols)} symbols for timeframe {timeframe}"
        )

        results = {}

        for symbol in symbols:
            data = self.load_symbol_data(symbol, timeframe, start_date, end_date)
            if data is not None and not data.empty:
                results[symbol] = data

        logger.info(
            f"Batch load completed: {len(results)}/{len(symbols)} symbols loaded"
        )
        return results

    def get_metadata(
        self,
        symbol: str,
        timeframe: str,
        use_cache: bool = True,
    ) -> Optional[DatasetMetadata]:
        """
        Get metadata for a dataset.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : str
            Timeframe identifier
        use_cache : bool, default=True
            Use cached metadata if available

        Returns:
        --------
        DatasetMetadata or None
            Metadata if dataset exists, None otherwise
        """
        key = (symbol, timeframe)

        # Check cache
        if use_cache and key in self._metadata_cache:
            return self._metadata_cache[key]

        # Load from file
        metadata_path = self._get_metadata_path(symbol, timeframe)
        if not metadata_path.exists():
            return None

        try:
            import json
            with open(metadata_path, 'r') as f:
                data = json.load(f)
            metadata = DatasetMetadata.from_dict(data)
            self._metadata_cache[key] = metadata
            return metadata
        except Exception as e:
            logger.error(f"Error loading metadata for {symbol} {timeframe}: {e}")
            return None

    def list_symbols(self, timeframe: Optional[str] = None) -> List[str]:
        """
        List all symbols with stored data.

        Parameters:
        -----------
        timeframe : str, optional
            Filter by specific timeframe

        Returns:
        --------
        list
            List of symbols with data
        """
        symbols = set()

        for symbol_dir in self.data_dir.iterdir():
            if symbol_dir.is_dir() and symbol_dir.name != 'metadata':
                if timeframe:
                    # Check for specific timeframe
                    file_path = symbol_dir / f"{timeframe}.parquet"
                    if file_path.exists():
                        symbols.add(symbol_dir.name)
                else:
                    # Any timeframe
                    if any(f.suffix == '.parquet' for f in symbol_dir.iterdir()):
                        symbols.add(symbol_dir.name)

        return sorted(symbols)

    def list_timeframes(self, symbol: Optional[str] = None) -> List[str]:
        """
        List all timeframes with stored data.

        Parameters:
        -----------
        symbol : str, optional
            Filter by specific symbol

        Returns:
        --------
        list
            List of timeframe identifiers
        """
        timeframes = set()

        if symbol:
            # Specific symbol
            symbol_dir = self.data_dir / symbol
            if symbol_dir.exists() and symbol_dir.is_dir():
                for file_path in symbol_dir.iterdir():
                    if file_path.suffix == '.parquet':
                        timeframes.add(file_path.stem)
        else:
            # All symbols
            for symbol_dir in self.data_dir.iterdir():
                if symbol_dir.is_dir() and symbol_dir.name != 'metadata':
                    for file_path in symbol_dir.iterdir():
                        if file_path.suffix == '.parquet':
                            timeframes.add(file_path.stem)

        return sorted(timeframes)

    def delete_symbol_data(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
    ) -> bool:
        """
        Delete data for a symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : str, optional
            Specific timeframe to delete, or all if None

        Returns:
        --------
        bool
            True if deletion successful
        """
        with self._lock:
            try:
                if timeframe:
                    # Delete specific timeframe
                    file_path = self._get_file_path(symbol, timeframe)
                    metadata_path = self._get_metadata_path(symbol, timeframe)

                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Deleted {symbol} {timeframe} data")

                    if metadata_path.exists():
                        metadata_path.unlink()

                    # Remove from cache
                    self._metadata_cache.pop((symbol, timeframe), None)
                else:
                    # Delete all timeframes for symbol
                    symbol_dir = self.data_dir / symbol
                    if symbol_dir.exists():
                        import shutil
                        shutil.rmtree(symbol_dir)
                        logger.info(f"Deleted all data for {symbol}")

                    # Remove metadata files
                    for metadata_file in (self.data_dir / 'metadata').glob(f"{symbol}_*.json"):
                        metadata_file.unlink()

                    # Clear cache
                    keys_to_remove = [k for k in self._metadata_cache if k[0] == symbol]
                    for key in keys_to_remove:
                        del self._metadata_cache[key]

                return True

            except Exception as e:
                logger.error(f"Error deleting data for {symbol}: {e}")
                return False

    def get_storage_stats(self) -> Dict:
        """
        Get storage statistics.

        Returns:
        --------
        dict
            Statistics including total size, number of symbols, etc.
        """
        total_size = 0
        num_files = 0
        symbols = set()
        timeframes = set()

        for symbol_dir in self.data_dir.iterdir():
            if symbol_dir.is_dir() and symbol_dir.name != 'metadata':
                symbols.add(symbol_dir.name)
                for file_path in symbol_dir.iterdir():
                    if file_path.suffix == '.parquet':
                        total_size += file_path.stat().st_size
                        num_files += 1
                        timeframes.add(file_path.stem)

        return {
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'num_files': num_files,
            'num_symbols': len(symbols),
            'num_timeframes': len(timeframes),
            'symbols': sorted(symbols),
            'timeframes': sorted(timeframes),
        }


def create_historical_manager(
    data_dir: str = 'data/historical',
    **kwargs
) -> HistoricalDataManager:
    """
    Factory function to create HistoricalDataManager instance.

    Parameters:
    -----------
    data_dir : str, default='data/historical'
        Root directory for data storage
    **kwargs
        Additional arguments passed to HistoricalDataManager

    Returns:
    --------
    HistoricalDataManager
        Configured manager instance
    """
    return HistoricalDataManager(data_dir=data_dir, **kwargs)


# Create default singleton instance for convenient imports
# Usage: from src.data.historical_manager import historical_manager
historical_manager = HistoricalDataManager(data_dir='data/historical')
