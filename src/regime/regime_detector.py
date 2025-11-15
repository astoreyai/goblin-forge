"""
Market Regime Analysis

Detects current market regime to adjust screening and risk management.

Regime Types:
-------------
1. Trending (Bullish/Bearish):
   - Clear directional movement
   - ADX > 25, price above/below moving averages
   - Best for trend-following strategies

2. Ranging (Choppy):
   - Sideways consolidation
   - ADX < 20, price oscillating around MAs
   - Best for mean-reversion strategies (our focus)

3. Volatile (High Uncertainty):
   - Large swings, high ATR
   - VIX > 25, ATR > historical average
   - Reduce position sizing, widen stops

Market Indicators:
------------------
- SPY (S&P 500 ETF): Primary market proxy
- QQQ (NASDAQ 100 ETF): Tech sector
- VIX: Volatility index
- ADX: Trend strength
- ATR: Range/volatility

Usage:
------
from src.regime.regime_detector import regime_detector

# Detect current regime
regime = regime_detector.detect_regime()
print(f"Market: {regime['type']} ({regime['strength']})")

# Adjust screening based on regime
if regime['type'] == 'ranging':
    # Ideal for mean-reversion
    screening_confidence = 'high'
elif regime['type'] == 'volatile':
    # Reduce position sizes
    risk_adjustment = 0.5
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

import pandas as pd
import numpy as np
from loguru import logger

from src.config import config
from src.data.ib_manager import ib_manager
from src.data.historical_manager import historical_manager
from src.indicators.indicator_engine import indicator_engine


class RegimeType(Enum):
    """Market regime types."""
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class RegimeDetector:
    """
    Market regime detection system.

    Analyzes market indices to determine current regime and adjust
    screening/risk parameters accordingly.

    Attributes:
    -----------
    market_symbols : list
        Market proxy symbols (SPY, QQQ, VIX)
    adx_trending_threshold : float
        ADX threshold for trending regime (default: 25)
    adx_ranging_threshold : float
        ADX threshold for ranging regime (default: 20)
    volatility_threshold : float
        VIX/ATR threshold for high volatility (default: 25)
    """

    def __init__(self):
        """Initialize regime detector with configuration."""
        # Market proxy symbols
        self.market_symbols = ['SPY', 'QQQ']  # S&P 500, NASDAQ 100
        self.vix_symbol = 'VIX'  # Volatility index

        # Thresholds from config
        regime_config = config.regime
        self.adx_trending_threshold = regime_config.adx_trending_threshold
        self.adx_ranging_threshold = regime_config.adx_ranging_threshold
        self.volatility_threshold = regime_config.volatility_threshold

        # Cache
        self.cache = {}

        logger.info("Regime detector initialized")

    def calculate_adx(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate ADX (Average Directional Index).

        ADX measures trend strength (0-100):
        - 0-20: Weak/no trend (ranging)
        - 20-25: Emerging trend
        - 25-50: Strong trend
        - 50+: Very strong trend

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV data
        period : int, default=14
            ADX calculation period

        Returns:
        --------
        pd.Series
            ADX values
        """
        import talib

        adx = talib.ADX(
            df['high'].values,
            df['low'].values,
            df['close'].values,
            timeperiod=period
        )

        return pd.Series(adx, index=df.index, name='adx')

    def get_market_data(
        self,
        symbol: str,
        timeframe: str = '1 day',
        duration: str = '3 M'
    ) -> Optional[pd.DataFrame]:
        """
        Get market data with indicators.

        Parameters:
        -----------
        symbol : str
            Market symbol (SPY, QQQ, VIX)
        timeframe : str
            Timeframe
        duration : str
            Historical duration

        Returns:
        --------
        pd.DataFrame or None
            Market data with indicators
        """
        try:
            # Check cache
            cache_key = f"{symbol}_{timeframe}"
            if cache_key in self.cache:
                cached_time = self.cache[cache_key]['timestamp']
                if (datetime.now() - cached_time).total_seconds() < 3600:  # 1 hour cache
                    return self.cache[cache_key]['data']

            # Try to load from historical manager first
            df = historical_manager.load(symbol, timeframe)

            # If not available or stale, fetch from IB
            if df is None or df.empty or (datetime.now() - df['date'].max()).days > 1:
                if ib_manager.is_connected():
                    df = ib_manager.fetch_historical_bars(
                        symbol=symbol,
                        bar_size=timeframe,
                        duration=duration
                    )

                    if df is not None and not df.empty:
                        # Save to historical manager
                        historical_manager.save(symbol, timeframe, df)

            if df is None or df.empty:
                logger.warning(f"No data available for {symbol}")
                return None

            # Calculate indicators
            df = indicator_engine.calculate_all(df, symbol=symbol)

            # Calculate ADX
            df['adx'] = self.calculate_adx(df)

            # Cache result
            self.cache[cache_key] = {
                'data': df,
                'timestamp': datetime.now()
            }

            return df

        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    def analyze_trend_strength(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Analyze trend strength using ADX and price position.

        Parameters:
        -----------
        df : pd.DataFrame
            Market data with indicators

        Returns:
        --------
        dict
            {'adx': float, 'trend_type': str, 'strength': str}
        """
        if df is None or df.empty:
            return {'adx': 0, 'trend_type': 'unknown', 'strength': 'none'}

        latest = df.iloc[-1]
        adx = latest.get('adx', 0)

        # Determine trend direction
        close = latest.get('close')
        sma_50 = df['close'].tail(50).mean()
        sma_200 = df['close'].tail(200).mean() if len(df) >= 200 else sma_50

        if pd.isna(close) or pd.isna(sma_50):
            trend_type = 'unknown'
        elif close > sma_50 and sma_50 > sma_200:
            trend_type = 'bullish'
        elif close < sma_50 and sma_50 < sma_200:
            trend_type = 'bearish'
        else:
            trend_type = 'neutral'

        # Determine strength
        if pd.isna(adx):
            strength = 'unknown'
        elif adx > 50:
            strength = 'very_strong'
        elif adx > self.adx_trending_threshold:
            strength = 'strong'
        elif adx > self.adx_ranging_threshold:
            strength = 'moderate'
        else:
            strength = 'weak'

        return {
            'adx': float(adx) if not pd.isna(adx) else 0,
            'trend_type': trend_type,
            'strength': strength,
            'sma_50': float(sma_50) if not pd.isna(sma_50) else None,
            'sma_200': float(sma_200) if not pd.isna(sma_200) else None
        }

    def analyze_volatility(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Analyze market volatility using ATR and historical comparison.

        Parameters:
        -----------
        df : pd.DataFrame
            Market data with ATR indicator

        Returns:
        --------
        dict
            {'atr': float, 'atr_pct': float, 'volatility_level': str}
        """
        if df is None or df.empty:
            return {'atr': 0, 'atr_pct': 0, 'volatility_level': 'unknown'}

        latest = df.iloc[-1]
        atr = latest.get('atr', 0)
        close = latest.get('close', 100)

        # ATR as percentage of price
        atr_pct = (atr / close) * 100 if close > 0 else 0

        # Compare to historical average
        avg_atr_pct = (df['atr'] / df['close'] * 100).tail(50).mean()

        if pd.isna(atr_pct) or pd.isna(avg_atr_pct):
            volatility_level = 'unknown'
        elif atr_pct > avg_atr_pct * 1.5:
            volatility_level = 'high'
        elif atr_pct > avg_atr_pct * 1.2:
            volatility_level = 'elevated'
        elif atr_pct > avg_atr_pct * 0.8:
            volatility_level = 'normal'
        else:
            volatility_level = 'low'

        return {
            'atr': float(atr) if not pd.isna(atr) else 0,
            'atr_pct': float(atr_pct) if not pd.isna(atr_pct) else 0,
            'avg_atr_pct': float(avg_atr_pct) if not pd.isna(avg_atr_pct) else 0,
            'volatility_level': volatility_level
        }

    def classify_regime(
        self,
        trend_analysis: Dict[str, Any],
        volatility_analysis: Dict[str, Any]
    ) -> RegimeType:
        """
        Classify market regime based on trend and volatility analysis.

        Parameters:
        -----------
        trend_analysis : dict
            Trend strength analysis
        volatility_analysis : dict
            Volatility analysis

        Returns:
        --------
        RegimeType
            Classified regime
        """
        adx = trend_analysis['adx']
        trend_type = trend_analysis['trend_type']
        volatility_level = volatility_analysis['volatility_level']

        # High volatility regime
        if volatility_level in ['high', 'elevated']:
            return RegimeType.VOLATILE

        # Trending regimes
        if adx >= self.adx_trending_threshold:
            if trend_type == 'bullish':
                return RegimeType.TRENDING_BULLISH
            elif trend_type == 'bearish':
                return RegimeType.TRENDING_BEARISH

        # Ranging regime (best for our mean-reversion strategy)
        if adx < self.adx_ranging_threshold:
            return RegimeType.RANGING

        # Default to unknown
        return RegimeType.UNKNOWN

    def detect_regime(
        self,
        use_cached: bool = True
    ) -> Dict[str, Any]:
        """
        Detect current market regime.

        Main method for regime detection. Analyzes SPY and QQQ to determine
        overall market condition.

        Parameters:
        -----------
        use_cached : bool, default=True
            Use cached data if available

        Returns:
        --------
        dict
            Complete regime analysis with keys:
            - type: RegimeType enum
            - type_str: String representation
            - confidence: float (0-1)
            - spy_analysis: SPY analysis
            - qqq_analysis: QQQ analysis
            - volatility: Volatility analysis
            - recommendation: Trading recommendation
            - timestamp: Analysis timestamp

        Examples:
        ---------
        >>> regime = regime_detector.detect_regime()
        >>> print(f"Regime: {regime['type_str']}")
        >>> if regime['type'] == RegimeType.RANGING:
        ...     print("Ideal for mean-reversion strategies")
        """
        logger.info("Detecting market regime...")

        try:
            # Analyze SPY (S&P 500)
            spy_df = self.get_market_data('SPY')
            if spy_df is not None:
                spy_trend = self.analyze_trend_strength(spy_df)
                spy_volatility = self.analyze_volatility(spy_df)
            else:
                spy_trend = {'adx': 0, 'trend_type': 'unknown', 'strength': 'unknown'}
                spy_volatility = {'atr': 0, 'atr_pct': 0, 'volatility_level': 'unknown'}

            # Analyze QQQ (NASDAQ 100)
            qqq_df = self.get_market_data('QQQ')
            if qqq_df is not None:
                qqq_trend = self.analyze_trend_strength(qqq_df)
                qqq_volatility = self.analyze_volatility(qqq_df)
            else:
                qqq_trend = {'adx': 0, 'trend_type': 'unknown', 'strength': 'unknown'}
                qqq_volatility = {'atr': 0, 'atr_pct': 0, 'volatility_level': 'unknown'}

            # Classify regime based on SPY (primary)
            regime_type = self.classify_regime(spy_trend, spy_volatility)

            # Calculate confidence based on SPY/QQQ agreement
            qqq_regime = self.classify_regime(qqq_trend, qqq_volatility)
            confidence = 1.0 if regime_type == qqq_regime else 0.7

            # Generate recommendation
            recommendation = self._generate_recommendation(
                regime_type,
                spy_trend,
                spy_volatility
            )

            result = {
                'type': regime_type,
                'type_str': regime_type.value,
                'confidence': confidence,
                'spy_analysis': {
                    'trend': spy_trend,
                    'volatility': spy_volatility
                },
                'qqq_analysis': {
                    'trend': qqq_trend,
                    'volatility': qqq_volatility
                },
                'recommendation': recommendation,
                'timestamp': datetime.now()
            }

            logger.info(
                f"Regime detected: {regime_type.value} "
                f"(confidence: {confidence:.0%})"
            )

            return result

        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return {
                'type': RegimeType.UNKNOWN,
                'type_str': 'unknown',
                'confidence': 0.0,
                'spy_analysis': {},
                'qqq_analysis': {},
                'recommendation': {},
                'timestamp': datetime.now(),
                'error': str(e)
            }

    def _generate_recommendation(
        self,
        regime_type: RegimeType,
        trend_analysis: Dict[str, Any],
        volatility_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate trading recommendations based on regime.

        Parameters:
        -----------
        regime_type : RegimeType
            Detected regime
        trend_analysis : dict
            Trend analysis
        volatility_analysis : dict
            Volatility analysis

        Returns:
        --------
        dict
            Trading recommendations
        """
        if regime_type == RegimeType.RANGING:
            return {
                'strategy_suitability': 'excellent',
                'position_sizing': 'normal',
                'risk_adjustment': 1.0,
                'notes': 'Ideal for mean-reversion strategies. Normal position sizing.'
            }

        elif regime_type == RegimeType.TRENDING_BULLISH:
            return {
                'strategy_suitability': 'good',
                'position_sizing': 'normal',
                'risk_adjustment': 1.0,
                'notes': 'Bullish trend supports reversals. Watch for pullbacks to moving averages.'
            }

        elif regime_type == RegimeType.TRENDING_BEARISH:
            return {
                'strategy_suitability': 'moderate',
                'position_sizing': 'reduced',
                'risk_adjustment': 0.75,
                'notes': 'Bearish trend. Reduce position sizing, focus on strongest setups only.'
            }

        elif regime_type == RegimeType.VOLATILE:
            return {
                'strategy_suitability': 'poor',
                'position_sizing': 'minimal',
                'risk_adjustment': 0.5,
                'notes': 'High volatility. Reduce position sizing 50%, widen stops, or stay in cash.'
            }

        else:
            return {
                'strategy_suitability': 'unknown',
                'position_sizing': 'reduced',
                'risk_adjustment': 0.5,
                'notes': 'Regime unclear. Use caution and reduced position sizing.'
            }

    def get_risk_adjustment_factor(self) -> float:
        """
        Get risk adjustment factor based on current regime.

        Returns multiplier for position sizing:
        - Ranging: 1.0 (normal)
        - Trending Bullish: 1.0
        - Trending Bearish: 0.75
        - Volatile: 0.5
        - Unknown: 0.5

        Returns:
        --------
        float
            Risk adjustment factor (0.0-1.0)

        Examples:
        ---------
        >>> factor = regime_detector.get_risk_adjustment_factor()
        >>> position_size = base_position_size * factor
        """
        regime = self.detect_regime()
        return regime['recommendation'].get('risk_adjustment', 0.5)


# Global singleton instance
regime_detector = RegimeDetector()
