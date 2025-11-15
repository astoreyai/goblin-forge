"""
Real-Time Dashboard Layer

Web-based monitoring interface built with Dash/Plotly:
- Real-time watchlist with SABR20 scores
- Multi-timeframe charts (5m, 15m, 1h, 4h)
- Position tracking with P&L visualization
- Market regime indicators
- Alert notifications

Key Components:
---------------
app : Main Dash application
components/ : UI components (header, watchlist, charts, positions, alerts)
callbacks/ : Real-time update callbacks

Dashboard Layout:
-----------------
┌─────────────────────────────────────────────────┐
│ Header: Clock | Connection | Regime Indicator   │
├─────────────────────────────────────────────────┤
│ Regime Panel: VIX | Trend | Breadth             │
├───────────────────────┬─────────────────────────┤
│ Watchlist Table       │ Multi-TF Chart          │
│ (SABR20 scores)       │ (5m/15m/1h/4h tabs)     │
│                       │ + Accumulation Panel    │
├───────────────────────┴─────────────────────────┤
│ Positions Panel: Active Trades | P&L | Risk     │
├─────────────────────────────────────────────────┤
│ Alerts Panel: Recent Notifications              │
└─────────────────────────────────────────────────┘

Update Intervals:
-----------------
- Watchlist: 15 seconds
- Charts: 60 seconds (or on symbol selection)
- Regime: 30 minutes
- Positions: 5 seconds

Access:
-------
http://localhost:8050 (default)
"""

__all__ = ['app', 'components', 'callbacks']
