"""
Screening & Scoring Layer

Multi-stage screening pipeline for identifying trading opportunities:
1. Universe construction (S&P 500, NASDAQ 100, quality filters)
2. Coarse filtering (fast 1h screening, parallel processing)
3. SABR20 fine scoring (multi-TF analysis, 0-100 points)
4. Watchlist generation (A+/A/B/C grading)

Key Components:
---------------
universe : Universe construction and quality filtering
coarse_filter : Fast parallel screening (1000 symbols in <30s)
sabr_scorer : SABR20 proprietary scoring algorithm (6 components)
watchlist : Multi-timeframe analysis and setup classification

SABR20 Components:
------------------
1. Setup Strength (0-30 pts) : Multi-TF indicator confluence
2. Bottom Phase (0-22 pts) : Depth and cleanness of reversal
3. Accumulation Intensity (0-18 pts) : Stoch/RSI signal frequency ratio **NEW**
4. Trend Momentum (0-18 pts) : Strength of emerging trend
5. Risk/Reward (0-10 pts) : Distance to resistance vs stop
6. Volume Profile (0-2 pts) : Volume characteristics

Performance Target:
-------------------
Screen 1000 symbols in <30 seconds using parallel processing
"""

__all__ = ['universe', 'coarse_filter', 'sabr_scorer', 'watchlist']
