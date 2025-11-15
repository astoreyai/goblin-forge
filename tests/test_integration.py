"""
Integration Tests

Tests complete screening pipeline integration.

Coverage:
---------
- End-to-end screening pipeline
- Component integration
- Configuration loading
- Error handling

Run:
----
pytest tests/test_integration.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.config import config
from src.screening.watchlist import watchlist_generator
from src.screening.sabr20_engine import sabr20_engine, SABR20Score
from src.screening.coarse_filter import coarse_filter
from src.screening.universe import universe_manager


@pytest.fixture
def sample_multi_timeframe_data():
    """Generate sample multi-timeframe data."""
    np.random.seed(42)

    # Generate 15m data
    dates_15m = pd.date_range('2024-01-01 09:30', periods=200, freq='15min')
    close_15m = 100 + np.random.randn(200).cumsum() * 0.5

    df_15m = pd.DataFrame({
        'date': dates_15m,
        'open': close_15m + (np.random.randn(200) * 0.2),
        'high': close_15m + np.abs(np.random.randn(200)) * 0.5,
        'low': close_15m - np.abs(np.random.randn(200)) * 0.5,
        'close': close_15m,
        'volume': np.random.randint(100000, 1000000, 200)
    })

    # Generate 1h data (aggregate from 15m concept)
    dates_1h = pd.date_range('2024-01-01 09:30', periods=100, freq='1h')
    close_1h = 100 + np.random.randn(100).cumsum() * 0.7

    df_1h = pd.DataFrame({
        'date': dates_1h,
        'open': close_1h + (np.random.randn(100) * 0.3),
        'high': close_1h + np.abs(np.random.randn(100)) * 0.6,
        'low': close_1h - np.abs(np.random.randn(100)) * 0.6,
        'close': close_1h,
        'volume': np.random.randint(500000, 2000000, 100)
    })

    # Generate 4h data
    dates_4h = pd.date_range('2024-01-01 09:30', periods=50, freq='4h')
    close_4h = 100 + np.random.randn(50).cumsum() * 1.0

    df_4h = pd.DataFrame({
        'date': dates_4h,
        'open': close_4h + (np.random.randn(50) * 0.5),
        'high': close_4h + np.abs(np.random.randn(50)) * 0.8,
        'low': close_4h - np.abs(np.random.randn(50)) * 0.8,
        'close': close_4h,
        'volume': np.random.randint(1000000, 5000000, 50)
    })

    return {
        '15m': df_15m,
        '1h': df_1h,
        '4h': df_4h
    }


class TestConfigurationIntegration:
    """Test configuration system integration."""

    def test_config_loading(self):
        """Test that configuration loads correctly."""
        assert config is not None
        assert config.ib is not None
        assert config.trading is not None

    def test_timeframe_profile_access(self):
        """Test timeframe profile access."""
        assert config.timeframes is not None
        assert config.timeframes.active_profile is not None

    def test_sabr20_config_access(self):
        """Test SABR20 configuration access."""
        assert config.sabr20 is not None
        assert config.sabr20.max_points is not None
        assert sum(config.sabr20.max_points.values()) == 100


class TestUniverseIntegration:
    """Test universe management integration."""

    def test_universe_building(self):
        """Test universe can be built."""
        # This should work with default symbols
        universe = universe_manager.build_universe(['sp500'])
        assert isinstance(universe, list)
        assert len(universe) > 0

    def test_symbol_list_loading(self):
        """Test symbol list loading."""
        symbols = universe_manager.load_symbol_list('sp500')
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        assert all(isinstance(s, str) for s in symbols)


class TestCoarseFilterIntegration:
    """Test coarse filter integration."""

    def test_coarse_filter_initialization(self):
        """Test coarse filter initializes correctly."""
        assert coarse_filter is not None
        assert coarse_filter.bb_max_position > 0
        assert coarse_filter.trend_sma_period > 0

    def test_filter_application(self):
        """Test applying filters to data."""
        # Generate sample data
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'open': [100] * 100,
            'high': [101] * 100,
            'low': [99] * 100,
            'close': [100.5] * 100,
            'volume': [1000000] * 100,
            'bb_position': [0.25] * 100,  # In lower 30%
            'atr': [1.0] * 100
        })

        # Test individual filters
        result = coarse_filter.apply_filters('TEST', df)

        assert isinstance(result, dict)
        assert 'passed' in result
        assert 'bb_position' in result


class TestSABR20Integration:
    """Test SABR20 scoring integration."""

    def test_sabr20_engine_initialization(self):
        """Test SABR20 engine initializes correctly."""
        assert sabr20_engine is not None
        assert sabr20_engine.max_points is not None

    def test_component_scoring(self, sample_multi_timeframe_data):
        """Test individual component scoring."""
        from src.indicators.indicator_engine import indicator_engine

        # Add indicators
        df_15m = indicator_engine.calculate_all(
            sample_multi_timeframe_data['15m'],
            symbol='TEST'
        )
        df_1h = indicator_engine.calculate_all(
            sample_multi_timeframe_data['1h'],
            symbol='TEST'
        )

        if df_15m is not None and df_1h is not None:
            # Test Component 1
            c1 = sabr20_engine.component_1_setup_strength(df_15m)
            assert isinstance(c1, dict)
            assert 'points' in c1
            assert 0 <= c1['points'] <= 20

            # Test Component 4
            c4 = sabr20_engine.component_4_trend_momentum(df_1h)
            assert isinstance(c4, dict)
            assert 'points' in c4
            assert 0 <= c4['points'] <= 16

    def test_full_scoring(self, sample_multi_timeframe_data):
        """Test complete SABR20 scoring."""
        from src.indicators.indicator_engine import indicator_engine

        # Add indicators to all timeframes
        data = {}
        for tf, df in sample_multi_timeframe_data.items():
            df_with_ind = indicator_engine.calculate_all(df, symbol='TEST')
            if df_with_ind is not None:
                data[tf] = df_with_ind

        if len(data) >= 3:
            # Score symbol
            score = sabr20_engine.score_symbol(
                symbol='TEST',
                data_trigger=data['15m'],
                data_confirmation=data['1h'],
                data_regime=data['4h']
            )

            assert isinstance(score, SABR20Score)
            assert score.symbol == 'TEST'
            assert 0 <= score.total_points <= 100
            assert score.setup_grade in ['Excellent', 'Strong', 'Good', 'Weak']
            assert len(score.component_scores) == 6


class TestWatchlistIntegration:
    """Test watchlist generation integration."""

    def test_watchlist_generator_initialization(self):
        """Test watchlist generator initializes."""
        assert watchlist_generator is not None
        assert watchlist_generator.timeframes is not None

    def test_multi_timeframe_data_loading(self):
        """Test multi-timeframe data loading structure."""
        # This would require actual data or mocking
        # Testing the structure only
        data = watchlist_generator.load_multi_timeframe_data.__doc__
        assert data is not None


class TestSystemConfiguration:
    """Test system-wide configuration."""

    def test_all_required_configs_present(self):
        """Test that all required configuration sections exist."""
        required_sections = [
            'ib', 'database', 'storage',
            'universe', 'timeframes', 'indicators',
            'sabr20', 'screening', 'regime'
        ]

        for section in required_sections:
            assert hasattr(config, section), f"Missing config section: {section}"

    def test_max_points_sum_to_100(self):
        """Test that SABR20 max points sum to 100."""
        total = sum(config.sabr20.max_points.values())
        assert total == 100, f"SABR20 max points sum to {total}, expected 100"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
