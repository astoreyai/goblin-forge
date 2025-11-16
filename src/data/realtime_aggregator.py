"""
Real-time bar aggregation for multi-timeframe analysis.

This module provides aggregation of fine-grained bars (e.g., 5-second) to
higher timeframes (1m, 15m, 1h, 4h, 1d) for technical analysis.

Features:
- Real-time bar aggregation with OHLCV calculations
- Multiple timeframe support
- Proper bar boundary detection
- Thread-safe operations
- Incomplete bar handling
- Historical bar initialization

Author: Screener Trading System
Date: 2025-11-15
"""

from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from enum import Enum

import pandas as pd
from loguru import logger


class Timeframe(Enum):
    """Supported aggregation timeframes."""

    SEC_5 = '5sec'
    MIN_1 = '1min'
    MIN_5 = '5min'
    MIN_15 = '15min'
    HOUR_1 = '1h'
    HOUR_4 = '4h'
    DAY_1 = '1d'

    @property
    def seconds(self) -> int:
        """Get timeframe duration in seconds."""
        mapping = {
            '5sec': 5,
            '1min': 60,
            '5min': 300,
            '15min': 900,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400,
        }
        return mapping[self.value]

    @classmethod
    def from_string(cls, s: str) -> 'Timeframe':
        """Create Timeframe from string."""
        normalized = s.lower().replace(' ', '').replace('_', '')

        # Handle common variations
        variations = {
            '5s': cls.SEC_5,
            '5sec': cls.SEC_5,
            '5second': cls.SEC_5,
            '1m': cls.MIN_1,
            '1min': cls.MIN_1,
            '1minute': cls.MIN_1,
            '5m': cls.MIN_5,
            '5min': cls.MIN_5,
            '5minute': cls.MIN_5,
            '15m': cls.MIN_15,
            '15min': cls.MIN_15,
            '15minute': cls.MIN_15,
            '1h': cls.HOUR_1,
            '1hour': cls.HOUR_1,
            '4h': cls.HOUR_4,
            '4hour': cls.HOUR_4,
            '1d': cls.DAY_1,
            '1day': cls.DAY_1,
        }

        if normalized in variations:
            return variations[normalized]

        # Try exact match
        for tf in cls:
            if tf.value == normalized:
                return tf

        raise ValueError(f"Unknown timeframe: {s}")


@dataclass
class Bar:
    """OHLCV bar data."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool = False

    def __post_init__(self):
        """Validate bar data."""
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) < Low ({self.low})")
        if self.high < self.open or self.high < self.close:
            raise ValueError(f"High ({self.high}) < Open/Close")
        if self.low > self.open or self.low > self.close:
            raise ValueError(f"Low ({self.low}) > Open/Close")
        if self.volume < 0:
            raise ValueError(f"Negative volume: {self.volume}")

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'complete': self.complete,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Bar':
        """Create Bar from dictionary."""
        return cls(
            timestamp=data['timestamp'],
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            volume=data['volume'],
            complete=data.get('complete', False),
        )


@dataclass
class AggregatedBar:
    """Aggregated bar with metadata."""

    symbol: str
    timeframe: Timeframe
    bar: Bar
    num_source_bars: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


class RealtimeAggregator:
    """
    Aggregate real-time bars to multiple timeframes.

    This class takes fine-grained bars (e.g., 5-second) and aggregates them
    to higher timeframes (1m, 15m, 1h, 4h, 1d) using proper OHLCV calculations.

    Features:
    - Multi-timeframe aggregation
    - Proper bar boundary detection
    - Thread-safe operations
    - Callback support for complete bars
    - Incomplete bar tracking

    Parameters:
    -----------
    source_timeframe : Timeframe or str
        Source bar timeframe (e.g., Timeframe.SEC_5 or '5sec')
    target_timeframes : List[Timeframe] or List[str]
        Target timeframes to aggregate to
    on_bar_complete : Callable, optional
        Callback function called when a bar completes
        Signature: on_bar_complete(symbol: str, timeframe: Timeframe, bar: Bar)

    Examples:
    ---------
    >>> aggregator = RealtimeAggregator('5sec', ['1min', '15min', '1h'])
    >>> aggregator.add_bar('AAPL', bar_5sec)
    >>> bars = aggregator.get_current_bars('AAPL')
    """

    def __init__(
        self,
        source_timeframe: str = '5sec',
        target_timeframes: Optional[List[str]] = None,
        on_bar_complete: Optional[Callable] = None,
    ):
        """Initialize real-time aggregator."""
        # Parse timeframes
        self.source_tf = Timeframe.from_string(source_timeframe)

        if target_timeframes is None:
            target_timeframes = ['1min', '5min', '15min', '1h', '4h']

        self.target_tfs = [Timeframe.from_string(tf) for tf in target_timeframes]

        # Validate target timeframes are larger than source
        for tf in self.target_tfs:
            if tf.seconds <= self.source_tf.seconds:
                raise ValueError(
                    f"Target timeframe {tf.value} must be larger than "
                    f"source {self.source_tf.value}"
                )

        # Callback for complete bars
        self.on_bar_complete = on_bar_complete

        # Storage: {symbol: {timeframe: incomplete_bar}}
        self._incomplete_bars: Dict[str, Dict[Timeframe, Bar]] = defaultdict(dict)

        # Complete bars: {symbol: {timeframe: [bars]}}
        self._complete_bars: Dict[str, Dict[Timeframe, List[Bar]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Metadata
        self._bar_counts: Dict[str, Dict[Timeframe, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Thread safety
        self._lock = threading.RLock()

        logger.info(
            f"RealtimeAggregator initialized: {self.source_tf.value} → "
            f"{[tf.value for tf in self.target_tfs]}"
        )

    def _get_bar_boundary(self, timestamp: datetime, timeframe: Timeframe) -> datetime:
        """
        Get the start timestamp for the bar containing this timestamp.

        Parameters:
        -----------
        timestamp : datetime
            Timestamp to find bar boundary for
        timeframe : Timeframe
            Target timeframe

        Returns:
        --------
        datetime
            Start of the bar period
        """
        # Convert to unix timestamp
        ts = int(timestamp.timestamp())

        # Round down to bar boundary
        bar_seconds = timeframe.seconds
        bar_start = (ts // bar_seconds) * bar_seconds

        return datetime.fromtimestamp(bar_start, tz=timestamp.tzinfo)

    def _is_same_bar(
        self,
        ts1: datetime,
        ts2: datetime,
        timeframe: Timeframe
    ) -> bool:
        """Check if two timestamps belong to the same bar."""
        return self._get_bar_boundary(ts1, timeframe) == self._get_bar_boundary(ts2, timeframe)

    def add_bar(self, symbol: str, bar: Bar) -> Dict[Timeframe, Bar]:
        """
        Add a source bar and aggregate to target timeframes.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        bar : Bar
            Source bar to aggregate

        Returns:
        --------
        dict
            Dictionary of {timeframe: completed_bar} for any bars that completed
        """
        with self._lock:
            completed = {}

            for target_tf in self.target_tfs:
                completed_bar = self._aggregate_to_timeframe(symbol, bar, target_tf)
                if completed_bar:
                    completed[target_tf] = completed_bar

                    # Call callback if provided
                    if self.on_bar_complete:
                        try:
                            self.on_bar_complete(symbol, target_tf, completed_bar)
                        except Exception as e:
                            logger.error(
                                f"Error in on_bar_complete callback for {symbol} "
                                f"{target_tf.value}: {e}"
                            )

            return completed

    def _aggregate_to_timeframe(
        self,
        symbol: str,
        source_bar: Bar,
        target_tf: Timeframe
    ) -> Optional[Bar]:
        """
        Aggregate source bar to target timeframe.

        Returns completed bar if bar period finished, None otherwise.
        """
        # Get current incomplete bar for this symbol/timeframe
        current_incomplete = self._incomplete_bars[symbol].get(target_tf)

        # Check if this source bar starts a new target bar
        if current_incomplete is None:
            # First bar - start new incomplete bar
            bar_start = self._get_bar_boundary(source_bar.timestamp, target_tf)

            self._incomplete_bars[symbol][target_tf] = Bar(
                timestamp=bar_start,
                open=source_bar.open,
                high=source_bar.high,
                low=source_bar.low,
                close=source_bar.close,
                volume=source_bar.volume,
                complete=False,
            )

            self._bar_counts[symbol][target_tf] = 1

            logger.debug(
                f"Started new {target_tf.value} bar for {symbol} at {bar_start}"
            )

            return None

        # Check if source bar belongs to same target bar
        same_bar = self._is_same_bar(
            source_bar.timestamp,
            current_incomplete.timestamp,
            target_tf
        )

        if same_bar:
            # Update incomplete bar with new source bar data
            current_incomplete.high = max(current_incomplete.high, source_bar.high)
            current_incomplete.low = min(current_incomplete.low, source_bar.low)
            current_incomplete.close = source_bar.close
            current_incomplete.volume += source_bar.volume

            self._bar_counts[symbol][target_tf] += 1

            return None

        else:
            # Source bar starts a new target bar - complete the old one
            completed_bar = Bar(
                timestamp=current_incomplete.timestamp,
                open=current_incomplete.open,
                high=current_incomplete.high,
                low=current_incomplete.low,
                close=current_incomplete.close,
                volume=current_incomplete.volume,
                complete=True,
            )

            # Store completed bar
            self._complete_bars[symbol][target_tf].append(completed_bar)

            num_bars = self._bar_counts[symbol][target_tf]

            logger.debug(
                f"Completed {target_tf.value} bar for {symbol}: "
                f"{completed_bar.timestamp} (from {num_bars} source bars)"
            )

            # Update position prices if order_manager is available
            # Use the close price from the completed bar
            try:
                from src.execution.order_manager import order_manager
                order_manager.update_position_price(symbol, completed_bar.close)
            except ImportError:
                pass  # order_manager not available (testing scenario)
            except Exception as e:
                logger.warning(f"Failed to update position for {symbol}: {e}")

            # Start new incomplete bar
            bar_start = self._get_bar_boundary(source_bar.timestamp, target_tf)

            self._incomplete_bars[symbol][target_tf] = Bar(
                timestamp=bar_start,
                open=source_bar.open,
                high=source_bar.high,
                low=source_bar.low,
                close=source_bar.close,
                volume=source_bar.volume,
                complete=False,
            )

            self._bar_counts[symbol][target_tf] = 1

            return completed_bar

    def get_current_bars(
        self,
        symbol: str,
        include_incomplete: bool = True
    ) -> Dict[Timeframe, Bar]:
        """
        Get current bars for a symbol across all timeframes.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        include_incomplete : bool, default=True
            Include incomplete (current) bars

        Returns:
        --------
        dict
            Dictionary of {timeframe: bar}
        """
        with self._lock:
            bars = {}

            if include_incomplete:
                # Get incomplete bars
                for tf, bar in self._incomplete_bars[symbol].items():
                    bars[tf] = bar

            return bars

    def get_complete_bars(
        self,
        symbol: str,
        timeframe: Optional[Timeframe] = None,
        limit: Optional[int] = None
    ) -> Dict[Timeframe, List[Bar]]:
        """
        Get completed bars for a symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : Timeframe, optional
            Specific timeframe to get bars for
        limit : int, optional
            Maximum number of bars to return per timeframe

        Returns:
        --------
        dict
            Dictionary of {timeframe: [bars]}
        """
        with self._lock:
            if timeframe:
                bars = self._complete_bars[symbol].get(timeframe, [])
                if limit:
                    bars = bars[-limit:]
                return {timeframe: bars}
            else:
                result = {}
                for tf in self.target_tfs:
                    bars = self._complete_bars[symbol].get(tf, [])
                    if limit:
                        bars = bars[-limit:]
                    result[tf] = bars
                return result

    def to_dataframe(
        self,
        symbol: str,
        timeframe: Timeframe,
        include_incomplete: bool = False
    ) -> pd.DataFrame:
        """
        Convert bars to pandas DataFrame.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : Timeframe
            Target timeframe
        include_incomplete : bool, default=False
            Include the current incomplete bar

        Returns:
        --------
        pd.DataFrame
            OHLCV DataFrame with DatetimeIndex
        """
        with self._lock:
            # Get complete bars
            bars = self._complete_bars[symbol].get(timeframe, [])

            # Add incomplete bar if requested
            if include_incomplete:
                incomplete = self._incomplete_bars[symbol].get(timeframe)
                if incomplete:
                    bars = bars + [incomplete]

            if not bars:
                return pd.DataFrame(
                    columns=['open', 'high', 'low', 'close', 'volume']
                )

            # Convert to DataFrame
            data = {
                'timestamp': [b.timestamp for b in bars],
                'open': [b.open for b in bars],
                'high': [b.high for b in bars],
                'low': [b.low for b in bars],
                'close': [b.close for b in bars],
                'volume': [b.volume for b in bars],
            }

            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)

            return df

    def get_stats(self, symbol: str) -> Dict:
        """
        Get aggregation statistics for a symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol

        Returns:
        --------
        dict
            Statistics including bar counts, incomplete bars, etc.
        """
        with self._lock:
            stats = {
                'symbol': symbol,
                'source_timeframe': self.source_tf.value,
                'target_timeframes': [tf.value for tf in self.target_tfs],
                'complete_bars': {},
                'incomplete_bars': {},
                'source_bar_counts': {},
            }

            for tf in self.target_tfs:
                complete_count = len(self._complete_bars[symbol].get(tf, []))
                stats['complete_bars'][tf.value] = complete_count

                has_incomplete = tf in self._incomplete_bars[symbol]
                stats['incomplete_bars'][tf.value] = has_incomplete

                source_count = self._bar_counts[symbol].get(tf, 0)
                stats['source_bar_counts'][tf.value] = source_count

            return stats

    def clear_history(self, symbol: str, timeframe: Optional[Timeframe] = None):
        """
        Clear completed bar history.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : Timeframe, optional
            Specific timeframe to clear, or all if None
        """
        with self._lock:
            if timeframe:
                self._complete_bars[symbol][timeframe] = []
                logger.info(f"Cleared {timeframe.value} history for {symbol}")
            else:
                self._complete_bars[symbol] = defaultdict(list)
                logger.info(f"Cleared all history for {symbol}")

    def reset(self, symbol: Optional[str] = None):
        """
        Reset aggregator state.

        Parameters:
        -----------
        symbol : str, optional
            Specific symbol to reset, or all if None
        """
        with self._lock:
            if symbol:
                self._incomplete_bars.pop(symbol, None)
                self._complete_bars.pop(symbol, None)
                self._bar_counts.pop(symbol, None)
                logger.info(f"Reset aggregator for {symbol}")
            else:
                self._incomplete_bars.clear()
                self._complete_bars.clear()
                self._bar_counts.clear()
                logger.info("Reset aggregator for all symbols")


def create_aggregator(
    source_timeframe: str = '5sec',
    target_timeframes: Optional[List[str]] = None,
    **kwargs
) -> RealtimeAggregator:
    """
    Factory function to create RealtimeAggregator.

    Parameters:
    -----------
    source_timeframe : str, default='5sec'
        Source bar timeframe
    target_timeframes : List[str], optional
        Target timeframes to aggregate to
    **kwargs
        Additional arguments passed to RealtimeAggregator

    Returns:
    --------
    RealtimeAggregator
        Configured aggregator instance
    """
    return RealtimeAggregator(
        source_timeframe=source_timeframe,
        target_timeframes=target_timeframes,
        **kwargs
    )
