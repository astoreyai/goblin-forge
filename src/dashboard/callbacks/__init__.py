"""
Dashboard Callback Functions

Real-time update callbacks for dashboard components.

Callbacks:
----------
update_watchlist : Refresh watchlist every 15s
update_charts : Update charts on symbol selection or 60s timer
update_regime : Refresh regime indicators every 30min
update_positions : Update position panel every 5s
update_alerts : Check for new alerts and notifications

Performance:
------------
All callbacks must complete in <500ms to maintain responsiveness
Use async data loading and caching where possible
"""

__all__ = ['update_watchlist', 'update_charts', 'update_regime', 'update_positions', 'update_alerts']
