"""
Screener Test Suite

Comprehensive testing for all system components.

Test Coverage Requirements:
----------------------------
- Minimum 80% code coverage across all modules
- All indicator calculations verified against known values
- SABR20 scoring validated on sample data
- Risk validation tested with edge cases
- IB API integration tested with paper account

Test Categories:
----------------
Unit Tests:
- test_indicators.py : Indicator calculation accuracy
- test_accumulation.py : Accumulation ratio logic
- test_screening.py : Coarse and fine screening
- test_sabr_scoring.py : SABR20 component scoring
- test_regime.py : Regime classification
- test_execution.py : Order validation and placement
- test_risk.py : Risk calculation and limits

Integration Tests:
- test_data_pipeline.py : End-to-end data flow
- test_screening_pipeline.py : Full screening workflow
- test_dashboard.py : Dashboard rendering and updates
- test_trade_flow.py : Complete trade execution cycle

Performance Tests:
- test_performance.py : Screening speed benchmarks
- test_memory.py : Memory stability over 24h
- test_database.py : Query performance (<100ms)

Running Tests:
--------------
# All tests
pytest tests/ -v --cov=src --cov-report=html

# Specific module
pytest tests/test_indicators.py -v

# With coverage threshold
pytest tests/ --cov=src --cov-fail-under=80
"""

__all__ = []
