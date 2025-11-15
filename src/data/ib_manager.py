"""
Interactive Brokers Data Manager for Screener Trading System.

Comprehensive IB Gateway connection manager with:
- Persistent connection with automatic reconnection
- Heartbeat monitoring and health checks
- Historical and real-time data fetching
- Rate limiting and request queuing
- Full resource cleanup
- Extensive error handling

Classes:
    IBDataManager: Production-ready IB Gateway manager
    ConnectionState: Enum for connection states

Usage:
    >>> from src.data.ib_manager import IBDataManager
    >>> manager = IBDataManager(port=4002)
    >>> manager.connect()
    >>> if manager.is_healthy():
    ...     data = manager.fetch_historical_bars('AAPL', '15 mins', '5 D')
    >>> manager.disconnect()
"""

from __future__ import annotations

import time
import threading
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable, Any
from collections import deque
from dataclasses import dataclass

from ib_insync import IB, Stock, util
from loguru import logger
import pandas as pd


class ConnectionState(Enum):
    """IB Gateway connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ConnectionMetrics:
    """Metrics for connection monitoring."""
    connect_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    reconnect_count: int = 0
    error_count: int = 0
    requests_sent: int = 0
    bytes_received: int = 0
    last_error: Optional[str] = None


class IBDataManager:
    """
    Comprehensive manager for Interactive Brokers API connections.

    Features:
    - Persistent connection with automatic reconnection
    - Heartbeat monitoring with configurable intervals
    - Rate-limited historical data fetching
    - Real-time data streaming with subscription management
    - Full cleanup and resource management
    - Comprehensive error handling and retry logic
    - Connection health monitoring and metrics

    Attributes:
        host (str): IB Gateway hostname
        port (int): IB Gateway port (4002 paper, 4001 live via IBC)
        client_id (int): Unique client identifier
        timeout (int): Connection timeout in seconds
        state (ConnectionState): Current connection state
        metrics (ConnectionMetrics): Connection metrics

    Example:
        >>> manager = IBDataManager(port=4002, heartbeat_interval=30)
        >>> manager.connect()
        >>> print(f"Healthy: {manager.is_healthy()}")
        >>> data = manager.fetch_historical_bars('AAPL', '15 mins', '5 D')
        >>> manager.disconnect()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        client_id: int = 1,
        timeout: int = 20,
        reconnect_enabled: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_delay: int = 5,
        heartbeat_interval: int = 30,
        heartbeat_enabled: bool = True,
        rate_limit_delay: float = 0.5,
    ):
        """
        Initialize comprehensive IB Data Manager.

        Parameters:
            host: IB Gateway hostname
            port: IB Gateway port
                  - 4002: Paper trading via IBC (RECOMMENDED)
                  - 4001: Live trading via IBC
                  - 7497: TWS paper trading
                  - 7496: TWS live trading
            client_id: Unique client ID (1-32)
            timeout: Connection timeout in seconds
            reconnect_enabled: Enable automatic reconnection
            max_reconnect_attempts: Maximum reconnection attempts (0 = infinite)
            reconnect_delay: Delay between reconnect attempts (seconds)
            heartbeat_interval: Seconds between heartbeat checks
            heartbeat_enabled: Enable heartbeat monitoring
            rate_limit_delay: Delay between IB API requests (seconds)
        """
        # Connection parameters
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout

        # Reconnection configuration
        self.reconnect_enabled = reconnect_enabled
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        # Heartbeat configuration
        self.heartbeat_enabled = heartbeat_enabled
        self.heartbeat_interval = heartbeat_interval

        # Rate limiting
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.ib: Optional[IB] = None
        self.metrics = ConnectionMetrics()

        # Heartbeat thread
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop_event = threading.Event()

        # Subscription tracking
        self._active_subscriptions: Dict[str, Any] = {}

        # Thread safety
        self._lock = threading.RLock()

        logger.info(
            f"IBDataManager initialized: {host}:{port} client_id={client_id} "
            f"reconnect={reconnect_enabled} heartbeat={heartbeat_enabled}"
        )

    def connect(self, retry: bool = True) -> bool:
        """
        Connect to IB Gateway with retry logic.

        Establishes connection and starts heartbeat monitoring if enabled.
        Supports automatic retry on failure.

        Parameters:
            retry: Enable retry on connection failure

        Returns:
            bool: True if connected successfully

        Raises:
            ConnectionRefusedError: If IB Gateway not running (when retry=False)
            TimeoutError: If connection timeout (when retry=False)
        """
        with self._lock:
            if self.is_connected():
                logger.warning("Already connected to IB Gateway")
                return True

            self.state = ConnectionState.CONNECTING
            attempt = 0
            max_attempts = self.max_reconnect_attempts if retry else 1

            while max_attempts == 0 or attempt < max_attempts:
                attempt += 1
                try:
                    logger.info(
                        f"Connecting to IB Gateway at {self.host}:{self.port} "
                        f"(attempt {attempt}/{max_attempts if max_attempts > 0 else '∞'})..."
                    )

                    self.ib = IB()
                    self.ib.connect(
                        host=self.host,
                        port=self.port,
                        clientId=self.client_id,
                        timeout=self.timeout,
                    )

                    if self.ib.isConnected():
                        self.state = ConnectionState.CONNECTED
                        self.metrics.connect_time = datetime.now()
                        self.metrics.last_heartbeat = datetime.now()

                        # Set up disconnection callback
                        self.ib.disconnectedEvent += self._on_disconnected

                        logger.success(
                            f"✅ Connected to IB Gateway "
                            f"(server v{self.ib.client.serverVersion()})"
                        )

                        # Start heartbeat monitoring
                        if self.heartbeat_enabled:
                            self._start_heartbeat()

                        return True
                    else:
                        raise ConnectionError("isConnected() returned False")

                except ConnectionRefusedError as e:
                    self.state = ConnectionState.ERROR
                    self.metrics.error_count += 1
                    self.metrics.last_error = f"Connection refused: {e}"

                    if not retry:
                        # No retry requested, raise immediately
                        logger.error(
                            f"Connection refused - is IB Gateway running on port {self.port}? "
                            f"Start with: ./scripts/start_ib_gateway.sh paper"
                        )
                        raise

                    if max_attempts > 0 and attempt >= max_attempts:
                        # Retries exhausted, return False instead of raising
                        logger.error(
                            f"Connection refused after {attempt} attempts - "
                            f"is IB Gateway running on port {self.port}?"
                        )
                        break

                    logger.warning(
                        f"Connection refused, retrying in {self.reconnect_delay}s..."
                    )
                    time.sleep(self.reconnect_delay)

                except TimeoutError as e:
                    self.state = ConnectionState.ERROR
                    self.metrics.error_count += 1
                    self.metrics.last_error = f"Timeout: {e}"

                    if not retry:
                        logger.error(
                            f"Connection timeout after {self.timeout}s - "
                            f"IB Gateway may be starting up"
                        )
                        raise

                    if max_attempts > 0 and attempt >= max_attempts:
                        logger.error(
                            f"Connection timeout after {attempt} attempts"
                        )
                        break

                    logger.warning(
                        f"Connection timeout, retrying in {self.reconnect_delay}s..."
                    )
                    time.sleep(self.reconnect_delay)

                except Exception as e:
                    self.state = ConnectionState.ERROR
                    self.metrics.error_count += 1
                    self.metrics.last_error = str(e)

                    if not retry:
                        logger.error(
                            f"Failed to connect: {type(e).__name__}: {e}"
                        )
                        raise

                    if max_attempts > 0 and attempt >= max_attempts:
                        logger.error(
                            f"Failed to connect after {attempt} attempts: {type(e).__name__}: {e}"
                        )
                        break

                    logger.warning(
                        f"Connection failed: {e}, retrying in {self.reconnect_delay}s..."
                    )
                    time.sleep(self.reconnect_delay)

            # All attempts exhausted
            self.state = ConnectionState.ERROR
            logger.error(f"Failed to connect after {attempt} attempts")
            return False

    def disconnect(self) -> None:
        """
        Disconnect from IB Gateway with full cleanup.

        Performs complete cleanup:
        1. Stops heartbeat monitoring
        2. Cancels all active subscriptions
        3. Disconnects from IB Gateway
        4. Releases all resources
        """
        with self._lock:
            logger.info("Disconnecting from IB Gateway...")

            # Stop heartbeat
            if self._heartbeat_thread is not None:
                self._stop_heartbeat()

            # Cancel all subscriptions
            if self.ib and self.ib.isConnected():
                self._cancel_all_subscriptions()

            # Disconnect from IB
            if self.ib:
                try:
                    if self.ib.isConnected():
                        self.ib.disconnect()
                        logger.success("✅ Disconnected from IB Gateway")
                except Exception as e:
                    logger.error(f"Error during disconnect: {e}")
                finally:
                    self.ib = None

            self.state = ConnectionState.DISCONNECTED
            self._active_subscriptions.clear()

    def is_connected(self) -> bool:
        """
        Check if currently connected to IB Gateway.

        Returns:
            bool: True if connected and healthy
        """
        if self.ib is None:
            return False
        return self.ib.isConnected() and self.state == ConnectionState.CONNECTED

    def is_healthy(self) -> bool:
        """
        Check connection health including heartbeat.

        Returns:
            bool: True if connected and heartbeat is recent
        """
        if not self.is_connected():
            return False

        if self.heartbeat_enabled and self.metrics.last_heartbeat:
            heartbeat_age = (datetime.now() - self.metrics.last_heartbeat).total_seconds()
            # Allow 2x heartbeat interval before declaring unhealthy
            if heartbeat_age > (self.heartbeat_interval * 2):
                logger.warning(
                    f"Heartbeat stale: {heartbeat_age:.1f}s since last check"
                )
                return False

        return True

    def _start_heartbeat(self) -> None:
        """Start heartbeat monitoring thread."""
        if self._heartbeat_thread is not None:
            logger.warning("Heartbeat thread already running")
            return

        self._heartbeat_stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="IBHeartbeat",
            daemon=True
        )
        self._heartbeat_thread.start()
        logger.info(f"Heartbeat monitoring started (interval={self.heartbeat_interval}s)")

    def _stop_heartbeat(self) -> None:
        """Stop heartbeat monitoring thread."""
        if self._heartbeat_thread is None:
            return

        logger.info("Stopping heartbeat monitoring...")
        self._heartbeat_stop_event.set()

        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5.0)

        self._heartbeat_thread = None
        logger.info("Heartbeat monitoring stopped")

    def _heartbeat_loop(self) -> None:
        """
        Heartbeat monitoring loop (runs in background thread).

        Periodically checks connection health and triggers reconnection
        if connection is lost.
        """
        logger.debug("Heartbeat loop started")

        while not self._heartbeat_stop_event.is_set():
            try:
                if self.ib and self.ib.isConnected():
                    # Check connection by requesting current time
                    try:
                        current_time = self.ib.reqCurrentTime()
                        self.metrics.last_heartbeat = datetime.now()
                        logger.debug(f"Heartbeat OK (IB time: {current_time})")
                    except Exception as e:
                        logger.warning(f"Heartbeat check failed: {e}")
                        # Connection may be dead, trigger reconnect
                        if self.reconnect_enabled:
                            self._trigger_reconnect()
                else:
                    logger.warning("Heartbeat: not connected")
                    if self.reconnect_enabled and self.state != ConnectionState.RECONNECTING:
                        self._trigger_reconnect()

            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

            # Wait for next heartbeat or stop signal
            self._heartbeat_stop_event.wait(self.heartbeat_interval)

        logger.debug("Heartbeat loop stopped")

    def _on_disconnected(self) -> None:
        """
        Callback when IB Gateway disconnects unexpectedly.

        Triggered by ib_insync disconnection event.
        """
        logger.warning("⚠️  IB Gateway disconnected unexpectedly")
        self.state = ConnectionState.DISCONNECTED

        if self.reconnect_enabled:
            self._trigger_reconnect()

    def _trigger_reconnect(self) -> None:
        """Trigger reconnection in background thread."""
        if self.state == ConnectionState.RECONNECTING:
            logger.debug("Reconnection already in progress")
            return

        self.state = ConnectionState.RECONNECTING
        self.metrics.reconnect_count += 1

        logger.info(f"Triggering reconnection (attempt #{self.metrics.reconnect_count})...")

        # Reconnect in background to avoid blocking
        reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            name="IBReconnect",
            daemon=True
        )
        reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        """Reconnection loop (runs in background thread)."""
        try:
            # Clean up existing connection
            if self.ib:
                try:
                    self.ib.disconnect()
                except Exception:
                    pass
                self.ib = None

            # Attempt reconnection
            success = self.connect(retry=True)

            if success:
                logger.success("✅ Reconnection successful")
            else:
                logger.error("❌ Reconnection failed")
                self.state = ConnectionState.ERROR

        except Exception as e:
            logger.error(f"Reconnection loop error: {e}")
            self.state = ConnectionState.ERROR

    def _cancel_all_subscriptions(self) -> None:
        """Cancel all active market data subscriptions."""
        if not self._active_subscriptions:
            return

        logger.info(f"Canceling {len(self._active_subscriptions)} active subscriptions...")

        for symbol, contract in self._active_subscriptions.items():
            try:
                self.ib.cancelMktData(contract)
                logger.debug(f"Canceled subscription for {symbol}")
            except Exception as e:
                logger.warning(f"Error canceling subscription for {symbol}: {e}")

        self._active_subscriptions.clear()

    def _rate_limit_wait(self) -> None:
        """
        Enforce rate limiting between IB API requests.

        IB enforces strict rate limits. This ensures we don't exceed them.
        """
        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.3f}s")
            time.sleep(wait_time)

        self._last_request_time = time.time()

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get connection metrics.

        Returns:
            dict: Connection metrics including uptime, error count, etc.
        """
        uptime = None
        if self.metrics.connect_time:
            uptime = (datetime.now() - self.metrics.connect_time).total_seconds()

        return {
            "state": self.state.value,
            "connected": self.is_connected(),
            "healthy": self.is_healthy(),
            "uptime_seconds": uptime,
            "reconnect_count": self.metrics.reconnect_count,
            "error_count": self.metrics.error_count,
            "requests_sent": self.metrics.requests_sent,
            "last_error": self.metrics.last_error,
            "last_heartbeat": self.metrics.last_heartbeat.isoformat() if self.metrics.last_heartbeat else None,
        }

    # ========================================================================
    # DATA FETCHING METHODS
    # ========================================================================

    def fetch_historical_bars(
        self,
        symbol: str,
        bar_size: str = '15 mins',
        duration: str = '5 D',
        what_to_show: str = 'TRADES',
        use_rth: bool = True,
        exchange: str = 'SMART',
        currency: str = 'USD',
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV bars for a symbol with validation.

        Parameters:
            symbol: Stock symbol (e.g., 'AAPL', 'MSFT')
            bar_size: Bar size
                      - Valid: '1 secs', '5 secs', '10 secs', '15 secs', '30 secs'
                      - '1 min', '2 mins', '3 mins', '5 mins', '10 mins', '15 mins'
                      - '20 mins', '30 mins', '1 hour', '2 hours', '3 hours', '4 hours'
                      - '8 hours', '1 day', '1 week', '1 month'
            duration: How far back to fetch
                      - Format: '<integer> <unit>'
                      - Units: S (seconds), D (days), W (weeks), M (months), Y (years)
                      - Examples: '5 D', '2 W', '1 M', '1 Y'
            what_to_show: Data type to show
                          - 'TRADES': Actual trades
                          - 'MIDPOINT': Bid/ask midpoint
                          - 'BID': Bid prices
                          - 'ASK': Ask prices
            use_rth: Use Regular Trading Hours only (9:30-16:00 ET)
            exchange: Exchange routing (default: 'SMART')
            currency: Currency (default: 'USD')

        Returns:
            pd.DataFrame: OHLCV data with columns:
                         - date: Timestamp (index)
                         - open: Open price
                         - high: High price
                         - low: Low price
                         - close: Close price
                         - volume: Trading volume
                         - barCount: Number of trades (if available)
                         - average: VWAP (if available)

        Raises:
            ConnectionError: If not connected to IB Gateway
            ValueError: If symbol invalid or data validation fails
            TimeoutError: If request times out

        Example:
            >>> manager = IBDataManager()
            >>> manager.connect()
            >>> df = manager.fetch_historical_bars('AAPL', '15 mins', '5 D')
            >>> print(df.head())
                                open    high     low   close    volume
            2025-11-10 09:30:00  150.2  150.5  150.1  150.4  1234567
            ...
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to IB Gateway - call connect() first")

        # Enforce rate limiting
        self._rate_limit_wait()

        try:
            logger.info(
                f"Fetching historical bars: {symbol} {bar_size} {duration} "
                f"(what={what_to_show}, rth={use_rth})"
            )

            # Qualify contract
            contract = self._qualify_contract(symbol, exchange, currency)

            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',  # Empty string = current time
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=1,  # Format as yyyyMMdd HH:mm:ss
                keepUpToDate=False,  # One-time fetch, not streaming
            )

            # Convert to DataFrame
            if not bars:
                raise ValueError(f"No historical data returned for {symbol}")

            df = util.df(bars)

            # Validate data
            df = self._validate_bars(df, symbol)

            # Update metrics
            self.metrics.requests_sent += 1

            logger.success(
                f"✅ Fetched {len(df)} bars for {symbol} "
                f"({df.index[0]} to {df.index[-1]})"
            )

            return df

        except ValueError as e:
            logger.error(f"Invalid data for {symbol}: {e}")
            raise

        except Exception as e:
            logger.error(f"Failed to fetch historical bars for {symbol}: {e}")
            self.metrics.error_count += 1
            self.metrics.last_error = f"Historical fetch error: {e}"
            raise

    def _qualify_contract(
        self,
        symbol: str,
        exchange: str = 'SMART',
        currency: str = 'USD',
    ) -> Stock:
        """
        Qualify a stock contract with IB.

        Parameters:
            symbol: Stock symbol
            exchange: Exchange routing
            currency: Currency

        Returns:
            Stock: Qualified contract

        Raises:
            ValueError: If contract cannot be qualified
        """
        contract = Stock(symbol, exchange, currency)

        logger.debug(f"Qualifying contract for {symbol}...")

        qualified = self.ib.qualifyContracts(contract)

        if not qualified:
            raise ValueError(
                f"Could not qualify contract for {symbol} - "
                f"symbol may be invalid or delisted"
            )

        contract = qualified[0]

        logger.debug(
            f"✅ Qualified: {contract.symbol} on {contract.primaryExchange}"
        )

        return contract

    def _validate_bars(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Validate and clean OHLCV bar data.

        Checks:
        - Required columns present
        - No missing values in OHLC
        - OHLC consistency (High >= Low, etc.)
        - No duplicate timestamps
        - Chronological order

        Parameters:
            df: DataFrame with bar data
            symbol: Symbol (for error messages)

        Returns:
            pd.DataFrame: Validated and cleaned data

        Raises:
            ValueError: If validation fails
        """
        if df.empty:
            raise ValueError(f"Empty DataFrame for {symbol}")

        # Check required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Missing required columns for {symbol}: {missing_cols}"
            )

        # Set datetime index if not already
        if 'date' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df = df.set_index('date')

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(f"No datetime index for {symbol}")

        # Check for duplicates
        if df.index.duplicated().any():
            logger.warning(f"Duplicate timestamps found for {symbol}, dropping...")
            df = df[~df.index.duplicated(keep='first')]

        # Sort chronologically
        df = df.sort_index()

        # Validate OHLC consistency
        invalid_bars = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        )

        if invalid_bars.any():
            num_invalid = invalid_bars.sum()
            logger.warning(
                f"Found {num_invalid} invalid OHLC bars for {symbol}, dropping..."
            )
            df = df[~invalid_bars]

        # Check for missing values in critical columns
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            logger.warning(
                f"Missing values in {symbol}: {null_counts[null_counts > 0].to_dict()}"
            )
            # Drop rows with missing OHLC
            df = df.dropna(subset=['open', 'high', 'low', 'close'])

        # Ensure volume is non-negative
        if (df['volume'] < 0).any():
            logger.warning(f"Negative volume found for {symbol}, setting to 0")
            df.loc[df['volume'] < 0, 'volume'] = 0

        logger.debug(f"✅ Validated {len(df)} bars for {symbol}")

        return df

    def __enter__(self):
        """Context manager entry - connect to IB Gateway."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect with full cleanup."""
        self.disconnect()

    def __repr__(self) -> str:
        """String representation of IBDataManager."""
        return (
            f"IBDataManager(host={self.host}, port={self.port}, "
            f"client_id={self.client_id}, state={self.state.value}, "
            f"healthy={self.is_healthy()})"
        )

    def __del__(self):
        """Destructor - ensure cleanup on garbage collection."""
        try:
            if self.is_connected():
                logger.warning("IBDataManager deleted while still connected - cleaning up")
                self.disconnect()
        except Exception:
            pass


# Convenience function
def create_ib_manager(
    port: int = 4002,
    client_id: int = 1,
    auto_connect: bool = True,
    heartbeat_interval: int = 30,
) -> IBDataManager:
    """
    Create and optionally connect to IB Gateway.

    Parameters:
        port: IB Gateway port (4002 paper, 4001 live via IBC)
        client_id: Unique client ID
        auto_connect: Connect immediately
        heartbeat_interval: Heartbeat check interval (seconds)

    Returns:
        IBDataManager: Configured manager instance

    Example:
        >>> manager = create_ib_manager(port=4002, heartbeat_interval=60)
        >>> print(manager.is_healthy())
    """
    manager = IBDataManager(
        port=port,
        client_id=client_id,
        heartbeat_interval=heartbeat_interval
    )
    if auto_connect:
        manager.connect()
    return manager
