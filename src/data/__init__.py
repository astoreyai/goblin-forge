"""
Data infrastructure for Screener Trading System.

This package provides:
- IB Gateway connection and data fetching (ib_manager)
- Historical data storage with Parquet (historical_manager)
- Real-time bar aggregation (realtime_aggregator)
- Ticker download from US-Stock-Symbols (ticker_downloader)

Modules:
    ib_manager: Interactive Brokers API connection and data operations
    ticker_downloader: Download and manage trading universe tickers

Usage:
    >>> from src.data import IBDataManager, ConnectionState
    >>> manager = IBDataManager(port=4002, heartbeat_interval=30)
    >>> manager.connect()
    >>> print(f"State: {manager.state}")
    >>> print(f"Healthy: {manager.is_healthy()}")
    >>> metrics = manager.get_metrics()
    >>> manager.disconnect()
"""

from .ib_manager import (
    IBDataManager,
    ConnectionState,
    ConnectionMetrics,
    create_ib_manager,
    ib_manager,
)
from .historical_manager import (
    HistoricalDataManager,
    DatasetMetadata,
    create_historical_manager,
    historical_manager,
)
from .realtime_aggregator import (
    RealtimeAggregator,
    Bar,
    Timeframe,
    AggregatedBar,
    create_aggregator,
)
from .ticker_downloader import TickerDownloader

__all__ = [
    'IBDataManager',
    'ConnectionState',
    'ConnectionMetrics',
    'create_ib_manager',
    'ib_manager',
    'HistoricalDataManager',
    'DatasetMetadata',
    'create_historical_manager',
    'historical_manager',
    'RealtimeAggregator',
    'Bar',
    'Timeframe',
    'AggregatedBar',
    'create_aggregator',
    'TickerDownloader',
]
