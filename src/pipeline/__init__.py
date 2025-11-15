"""
Data Pipeline Orchestration Layer

Coordinates all system components and scheduled jobs:
- Pre-market data updates
- Intraday screening and watchlist generation
- Post-market data saves and reporting
- System health monitoring
- Graceful startup/shutdown

Key Components:
---------------
pipeline_manager : DataPipelineManager class for orchestration

Scheduled Jobs:
---------------
Pre-Market (6:00 AM):
- Update universe (fetch latest S&P 500, NASDAQ 100 components)
- Download overnight historical data for all symbols
- Update database with latest bars

Pre-Market (7:00 AM):
- Run comprehensive multi-timeframe screening
- Generate initial watchlist with SABR20 scores
- Update regime analysis

Intraday:
- Every 30 min: Update coarse screening
- Every 15 min: Update fine screening and watchlist
- Every 5 sec: Update position tracking
- Every 1 min: Check and update trailing stops

Post-Market (4:30 PM):
- Save real-time data to historical database
- Generate daily performance report
- Backup signal database
- Email/Slack summary

Error Handling:
---------------
All jobs include:
- Retry logic with exponential backoff
- Error logging with alerts
- Graceful degradation
- Health check monitoring
"""

__all__ = ['pipeline_manager']
