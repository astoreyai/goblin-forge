"""
Data infrastructure for Screener Trading System.

This package provides:
- IB Gateway connection and data fetching (ib_manager)
- Historical data storage with Parquet (historical_manager)
- Real-time bar aggregation (realtime_aggregator)
- Ticker download from US-Stock-Symbols (ticker_downloader)
- Trade database and journaling (trade_database)

Modules:
    ib_manager: Interactive Brokers API connection and data operations
    ticker_downloader: Download and manage trading universe tickers
    trade_database: SQLite-based trade journaling with performance analytics

Usage:
    >>> from src.data import IBDataManager, ConnectionState
    >>> manager = IBDataManager(port=4002, heartbeat_interval=30)
    >>> manager.connect()
    >>> print(f"State: {manager.state}")
    >>> print(f"Healthy: {manager.is_healthy()}")
    >>> metrics = manager.get_metrics()
    >>> manager.disconnect()

    >>> from src.data import trade_database
    >>> trade_id = trade_database.record_trade_entry(...)
    >>> stats = trade_database.get_performance_stats()
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
from .trade_database import (
    TradeDatabase,
    Trade,
    trade_database,
)

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
    'TradeDatabase',
    'Trade',
    'trade_database',
]
