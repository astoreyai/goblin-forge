"""
Technical Indicators Layer

Calculates all technical indicators used in the trading system:
- Bollinger Bands (20-period, 2 std dev)
- Stochastic RSI (14-period RSI, 14-period Stoch, 3/3 smoothing)
- MACD (12/26/9)
- RSI (14-period)
- ATR (14-period)
- **Accumulation Ratio** (Novel component - Stoch/RSI signal frequency)

Key Components:
---------------
calculator : IndicatorEngine class for TA-Lib integration
accumulation : Accumulation intensity analysis (SABR20 Component 3)
cache : IndicatorCache for TTL-based caching

Performance:
------------
- Vectorized operations (NumPy/Pandas)
- No Python loops for calculations
- In-memory caching (300s TTL default)
- Pre-compiled TA-Lib functions
"""

__all__ = ['calculator', 'accumulation', 'cache']
