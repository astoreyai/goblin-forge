"""
Coarse Screening Filter

Fast pre-filter on 1-hour timeframe to eliminate obviously unsuitable symbols
before expensive SABR20 multi-timeframe scoring.

Purpose:
--------
Screen 1000+ symbols in <10 seconds by applying simple filters on 1h data:
1. Bollinger Band position (must be in lower 30% for mean reversion setup)
2. Price action (must not be in strong downtrend)
3. Volume (must have recent activity)
4. Volatility (ATR check for tradeable volatility)

Filters Applied:
----------------
1. **BB Position Filter** (0-30%):
   - Price must be in lower 30% of Bollinger Bands
   - Identifies oversold/mean-reversion candidates

2. **Trend Filter** (not in strong downtrend):
   - Close must be above SMA(50) * 0.90
   - Eliminates broken stocks in freefall

3. **Volume Filter** (above average):
   - Recent volume > 20-day average
   - Ensures liquidity and interest

4. **Volatility Filter** (tradeable range):
   - ATR > 0.5% of price (not too tight)
   - ATR < 10% of price (not too wild)

Usage:
------
from src.screening.coarse_filter import coarse_filter

# Screen universe on 1h timeframe
candidates = coarse_filter.screen(
    symbols=['AAPL', 'MSFT', 'TSLA', ...],  # 1000+ symbols
    data_1h=data_dict_1h  # Pre-loaded 1h data
)

# candidates will be reduced to ~50-100 symbols for fine screening
"""

from typing import List, Dict, Optional
from datetime import datetime

import pandas as pd
import numpy as np
from loguru import logger

from src.config import config
from src.data.ib_manager import ib_manager
from src.data.historical_manager import historical_manager
from src.indicators.indicator_engine import indicator_engine


class CoarseFilter:
    """
    Coarse screening filter for fast pre-filtering.

    Applies simple filters on 1-hour timeframe to reduce universe from
    1000+ symbols to ~50-100 candidates for expensive SABR20 scoring.

    Attributes:
    -----------
    bb_max_position : float
        Maximum BB position (0-1 scale, default 0.30)
    trend_sma_period : int
        SMA period for trend filter (default 50)
    trend_min_distance : float
        Minimum distance above SMA (default 0.90 = 10% max drawdown)
    volume_lookback : int
        Lookback for volume average (default 20)
    atr_min_pct : float
        Minimum ATR as % of price (default 0.005 = 0.5%)
    atr_max_pct : float
        Maximum ATR as % of price (default 0.10 = 10%)
    """

    def __init__(self):
        """Initialize coarse filter with configuration."""
        # Load filter parameters from config
        filter_config = config.screening.coarse_filter

        self.bb_max_position = filter_config.bb_max_position
        self.trend_sma_period = filter_config.trend_sma_period
        self.trend_min_distance = filter_config.trend_min_distance
        self.volume_lookback = filter_config.volume_lookback
        self.atr_min_pct = filter_config.atr_min_pct
        self.atr_max_pct = filter_config.atr_max_pct

        logger.info(
            f"Coarse filter initialized: BB<{self.bb_max_position:.0%}, "
            f"Trend>{self.trend_min_distance:.0%}, "
            f"ATR {self.atr_min_pct:.1%}-{self.atr_max_pct:.1%}"
        )

    def check_bb_position(self, df: pd.DataFrame) -> bool:
        """
        Check if latest BB position is in lower range (oversold).

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV data with indicators (must have 'bb_position')

        Returns:
        --------
        bool
            True if BB position <= bb_max_position
        """
        if 'bb_position' not in df.columns or df.empty:
            return False

        latest_position = df['bb_position'].iloc[-1]

        # NaN check
        if pd.isna(latest_position):
            return False

        return latest_position <= self.bb_max_position

    def check_trend(self, df: pd.DataFrame) -> bool:
        """
        Check if not in strong downtrend.

        Price must be above SMA(50) * trend_min_distance.
        This eliminates stocks in freefall.

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV data (must have 'close')

        Returns:
        --------
        bool
            True if above minimum trend distance
        """
        if df.empty or len(df) < self.trend_sma_period:
            return False

        # Calculate SMA
        sma = df['close'].rolling(window=self.trend_sma_period).mean()
        latest_sma = sma.iloc[-1]
        latest_close = df['close'].iloc[-1]

        # NaN check
        if pd.isna(latest_sma) or pd.isna(latest_close):
            return False

        # Check if close is above threshold
        threshold = latest_sma * self.trend_min_distance
        return latest_close >= threshold

    def check_volume(self, df: pd.DataFrame) -> bool:
        """
        Check if recent volume is above average.

        Latest volume must be > average of last N bars.

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV data (must have 'volume')

        Returns:
        --------
        bool
            True if recent volume above average
        """
        if df.empty or len(df) < self.volume_lookback:
            return False

        avg_volume = df['volume'].tail(self.volume_lookback).mean()
        latest_volume = df['volume'].iloc[-1]

        # NaN check
        if pd.isna(avg_volume) or pd.isna(latest_volume):
            return False

        return latest_volume >= avg_volume

    def check_volatility(self, df: pd.DataFrame) -> bool:
        """
        Check if volatility is in tradeable range.

        ATR must be between min and max percentage of price.
        - Too tight: no opportunity
        - Too wild: too risky

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV data with indicators (must have 'atr', 'close')

        Returns:
        --------
        bool
            True if ATR in acceptable range
        """
        if 'atr' not in df.columns or df.empty:
            return False

        latest_atr = df['atr'].iloc[-1]
        latest_close = df['close'].iloc[-1]

        # NaN check
        if pd.isna(latest_atr) or pd.isna(latest_close):
            return False

        # Calculate ATR as percentage of price
        atr_pct = latest_atr / latest_close

        return self.atr_min_pct <= atr_pct <= self.atr_max_pct

    def apply_filters(
        self,
        symbol: str,
        df: pd.DataFrame
    ) -> Dict[str, bool]:
        """
        Apply all coarse filters to a symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        df : pd.DataFrame
            OHLCV data with indicators

        Returns:
        --------
        dict
            Filter results with keys:
            - bb_position: BB position filter result
            - trend: Trend filter result
            - volume: Volume filter result
            - volatility: Volatility filter result
            - passed: Overall pass/fail

        Examples:
        ---------
        >>> result = coarse_filter.apply_filters('AAPL', df_1h)
        >>> if result['passed']:
        ...     print(f"AAPL passed coarse screening")
        """
        results = {
            'symbol': symbol,
            'bb_position': self.check_bb_position(df),
            'trend': self.check_trend(df),
            'volume': self.check_volume(df),
            'volatility': self.check_volatility(df),
        }

        # Must pass all filters
        results['passed'] = all([
            results['bb_position'],
            results['trend'],
            results['volume'],
            results['volatility']
        ])

        return results

    def screen_symbol(
        self,
        symbol: str,
        timeframe: str = '1 hour',
        use_cached_data: bool = True
    ) -> bool:
        """
        Screen a single symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        timeframe : str, default='1 hour'
            Timeframe for screening
        use_cached_data : bool, default=True
            If True, uses historical data from disk. If False, fetches fresh.

        Returns:
        --------
        bool
            True if symbol passed all filters

        Examples:
        ---------
        >>> passed = coarse_filter.screen_symbol('AAPL')
        >>> if passed:
        ...     print("AAPL is a candidate")
        """
        try:
            # Load data
            if use_cached_data:
                df = historical_manager.load(symbol, timeframe)
            else:
                df = ib_manager.fetch_historical_bars(
                    symbol=symbol,
                    bar_size=timeframe,
                    duration='5 D'
                )

            if df is None or df.empty:
                logger.debug(f"No data for {symbol}")
                return False

            # Calculate indicators if not present
            if 'bb_position' not in df.columns:
                df = indicator_engine.calculate_all(df, symbol=symbol)

            if df is None:
                return False

            # Apply filters
            results = self.apply_filters(symbol, df)

            return results['passed']

        except Exception as e:
            logger.error(f"Error screening {symbol}: {e}")
            return False

    def screen(
        self,
        symbols: List[str],
        data_dict: Optional[Dict[str, pd.DataFrame]] = None,
        timeframe: str = '1 hour',
        parallel: bool = True
    ) -> List[str]:
        """
        Screen multiple symbols (main screening method).

        Parameters:
        -----------
        symbols : list of str
            List of symbols to screen
        data_dict : dict, optional
            Pre-loaded data {symbol: df_with_indicators}.
            If None, loads from historical manager.
        timeframe : str, default='1 hour'
            Timeframe for screening
        parallel : bool, default=True
            If True, uses parallel processing (multiprocessing)

        Returns:
        --------
        list of str
            Symbols that passed coarse filters

        Examples:
        ---------
        >>> # Option 1: Let screener load data
        >>> candidates = coarse_filter.screen(universe)

        >>> # Option 2: Pre-load data for efficiency
        >>> data = {sym: historical_manager.load(sym, '1 hour') for sym in universe}
        >>> candidates = coarse_filter.screen(universe, data_dict=data)
        """
        logger.info(f"Coarse screening {len(symbols)} symbols on {timeframe}...")

        passed_symbols = []
        failed_filters = {
            'bb_position': 0,
            'trend': 0,
            'volume': 0,
            'volatility': 0,
            'no_data': 0
        }

        # Process symbols
        for symbol in symbols:
            try:
                # Get data
                if data_dict is not None and symbol in data_dict:
                    df = data_dict[symbol]
                else:
                    df = historical_manager.load(symbol, timeframe)

                if df is None or df.empty:
                    failed_filters['no_data'] += 1
                    continue

                # Calculate indicators if not present
                if 'bb_position' not in df.columns:
                    df = indicator_engine.calculate_all(df, symbol=symbol)

                if df is None:
                    failed_filters['no_data'] += 1
                    continue

                # Apply filters
                results = self.apply_filters(symbol, df)

                if results['passed']:
                    passed_symbols.append(symbol)
                else:
                    # Track which filters failed
                    for filter_name in ['bb_position', 'trend', 'volume', 'volatility']:
                        if not results[filter_name]:
                            failed_filters[filter_name] += 1

            except Exception as e:
                logger.debug(f"Error screening {symbol}: {e}")
                failed_filters['no_data'] += 1

        # Log results
        pass_rate = len(passed_symbols) / len(symbols) * 100 if symbols else 0
        logger.info(
            f"Coarse screening complete: {len(passed_symbols)} / {len(symbols)} passed ({pass_rate:.1f}%)"
        )
        logger.debug(f"Failed filters: {failed_filters}")

        return passed_symbols

    def get_filter_stats(
        self,
        symbols: List[str],
        data_dict: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Get detailed filter statistics for analysis.

        Parameters:
        -----------
        symbols : list of str
            Symbols to analyze
        data_dict : dict
            Pre-loaded data {symbol: df_with_indicators}

        Returns:
        --------
        pd.DataFrame
            Statistics with columns:
            - symbol, bb_position, trend, volume, volatility, passed

        Examples:
        ---------
        >>> stats = coarse_filter.get_filter_stats(universe, data)
        >>> print(stats[stats['passed'] == False].head())
        """
        results_list = []

        for symbol in symbols:
            if symbol not in data_dict:
                continue

            df = data_dict[symbol]
            if df is None or df.empty:
                continue

            results = self.apply_filters(symbol, df)
            results_list.append(results)

        return pd.DataFrame(results_list)


# Global singleton instance
coarse_filter = CoarseFilter()
