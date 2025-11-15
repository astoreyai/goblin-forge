"""
Market Regime Analysis Layer

Assesses market environment to adjust trading behavior:
- VIX-based volatility classification
- Multi-index trend consensus (SPY, QQQ, IWM, DIA)
- Market breadth (A/D line, new highs/lows)
- Position size multipliers based on regime

Key Components:
---------------
analyzer : Market environment assessment functions
monitor : RegimeMonitor class for real-time tracking

Regime Types:
-------------
Volatility:
- Low (VIX < 15) : Favorable, 1.0x position size
- Medium (VIX 15-25) : Normal, 1.0x position size
- High (VIX 25-40) : Cautious, 0.75x position size
- Extreme (VIX > 40) : Defensive, 0.5x position size

Trend:
- Bull (consensus up) : Favorable for longs
- Bear (consensus down) : Hostile, reduce exposure
- Mixed : Neutral, selective trading

Update Frequency:
-----------------
Every 30 minutes during market hours
"""

__all__ = ['analyzer', 'monitor']
