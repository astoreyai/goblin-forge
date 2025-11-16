"""
Test Real-time Position Tracking with Live P&L Updates

Tests comprehensive position tracking functionality including:
- Position P&L calculations (long/short, profit/loss)
- Real-time price updates from aggregator
- Portfolio-level P&L aggregation
- Risk calculations
- DataFrame outputs

Author: Screener Trading System
Date: 2025-11-15
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.execution.order_manager import (
    Position,
    ClosedTrade,
    OrderManager,
    order_manager
)
from src.data.realtime_aggregator import (
    RealtimeAggregator,
    Bar,
    Timeframe
)


class TestPositionPnLCalculations:
    """Test Position P&L property calculations."""

    @pytest.fixture
    def long_position(self):
        """Create sample long position."""
        return Position(
            symbol='AAPL',
            side='BUY',
            quantity=100,
            entry_price=150.00,
            entry_time=datetime.now(),
            stop_price=147.00,
            target_price=156.00,
            current_price=150.00,  # Initially at entry
            last_update=datetime.now()
        )

    @pytest.fixture
    def short_position(self):
        """Create sample short position."""
        return Position(
            symbol='TSLA',
            side='SELL',
            quantity=50,
            entry_price=200.00,
            entry_time=datetime.now(),
            stop_price=204.00,
            target_price=190.00,
            current_price=200.00,
            last_update=datetime.now()
        )

    def test_unrealized_pnl_long_position_profit(self, long_position):
        """Test unrealized P&L for long position in profit."""
        long_position.current_price = 153.00  # $3 profit per share

        expected_pnl = (153.00 - 150.00) * 100  # $300
        assert long_position.unrealized_pnl == expected_pnl
        assert long_position.unrealized_pnl == 300.0

    def test_unrealized_pnl_long_position_loss(self, long_position):
        """Test unrealized P&L for long position in loss."""
        long_position.current_price = 148.00  # $2 loss per share

        expected_pnl = (148.00 - 150.00) * 100  # -$200
        assert long_position.unrealized_pnl == expected_pnl
        assert long_position.unrealized_pnl == -200.0

    def test_unrealized_pnl_long_position_breakeven(self, long_position):
        """Test unrealized P&L for long position at breakeven."""
        long_position.current_price = 150.00

        assert long_position.unrealized_pnl == 0.0

    def test_unrealized_pnl_short_position_profit(self, short_position):
        """Test unrealized P&L for short position in profit."""
        short_position.current_price = 195.00  # $5 profit per share (sold at 200, now 195)

        expected_pnl = (200.00 - 195.00) * 50  # $250
        assert short_position.unrealized_pnl == expected_pnl
        assert short_position.unrealized_pnl == 250.0

    def test_unrealized_pnl_short_position_loss(self, short_position):
        """Test unrealized P&L for short position in loss."""
        short_position.current_price = 205.00  # $5 loss per share

        expected_pnl = (200.00 - 205.00) * 50  # -$250
        assert short_position.unrealized_pnl == expected_pnl
        assert short_position.unrealized_pnl == -250.0

    def test_unrealized_pnl_short_position_breakeven(self, short_position):
        """Test unrealized P&L for short position at breakeven."""
        short_position.current_price = 200.00

        assert short_position.unrealized_pnl == 0.0

    def test_unrealized_pnl_zero_current_price(self, long_position):
        """Test unrealized P&L with zero current price (not yet updated)."""
        long_position.current_price = 0.0

        assert long_position.unrealized_pnl == 0.0

    def test_unrealized_pnl_pct_long_profit(self, long_position):
        """Test unrealized P&L percentage for long position in profit."""
        long_position.current_price = 153.00  # $3 profit = 2%

        # 300 / (150 * 100) = 2%
        assert long_position.unrealized_pnl_pct == pytest.approx(2.0)

    def test_unrealized_pnl_pct_long_loss(self, long_position):
        """Test unrealized P&L percentage for long position in loss."""
        long_position.current_price = 148.00  # $2 loss = -1.33%

        # -200 / (150 * 100) = -1.33%
        assert long_position.unrealized_pnl_pct == pytest.approx(-1.3333, rel=0.01)

    def test_unrealized_pnl_pct_short_profit(self, short_position):
        """Test unrealized P&L percentage for short position in profit."""
        short_position.current_price = 190.00  # $10 profit = 10%

        # 500 / (200 * 50) = 5%
        assert short_position.unrealized_pnl_pct == pytest.approx(5.0)

    def test_unrealized_pnl_pct_zero_entry_price(self):
        """Test unrealized P&L percentage with zero entry price (edge case)."""
        position = Position(
            symbol='TEST',
            side='BUY',
            quantity=100,
            entry_price=0.0,  # Invalid but test edge case
            entry_time=datetime.now(),
            current_price=10.0
        )

        assert position.unrealized_pnl_pct == 0.0

    def test_current_risk_long_position(self, long_position):
        """Test current risk calculation for long position."""
        long_position.current_price = 151.00

        # Risk = (current - stop) * quantity
        expected_risk = (151.00 - 147.00) * 100  # $400
        assert long_position.current_risk == expected_risk
        assert long_position.current_risk == 400.0

    def test_current_risk_short_position(self, short_position):
        """Test current risk calculation for short position."""
        short_position.current_price = 198.00

        # Risk = (stop - current) * quantity
        expected_risk = (204.00 - 198.00) * 50  # $300
        assert short_position.current_risk == expected_risk
        assert short_position.current_risk == 300.0

    def test_current_risk_no_stop_price(self, long_position):
        """Test current risk with no stop price set."""
        long_position.stop_price = None
        long_position.current_price = 151.00

        assert long_position.current_risk == 0.0

    def test_current_risk_at_stop(self, long_position):
        """Test current risk when price is at stop (zero risk)."""
        long_position.current_price = 147.00  # At stop

        assert long_position.current_risk == 0.0

    def test_current_risk_below_stop_long(self, long_position):
        """Test current risk when price is below stop for long (negative)."""
        long_position.current_price = 145.00  # Below stop

        # Risk = (145 - 147) * 100 = -200
        assert long_position.current_risk == -200.0


class TestOrderManagerPositionUpdates:
    """Test OrderManager position price updates."""

    @pytest.fixture
    def manager(self):
        """Create fresh OrderManager instance."""
        mgr = OrderManager()
        mgr.positions.clear()
        mgr.closed_trades.clear()
        return mgr

    @pytest.fixture
    def sample_position(self):
        """Create sample position."""
        return Position(
            symbol='AAPL',
            side='BUY',
            quantity=100,
            entry_price=150.00,
            entry_time=datetime.now(),
            stop_price=147.00,
            target_price=156.00,
            current_price=150.00
        )

    def test_update_position_price(self, manager, sample_position):
        """Test updating position price."""
        manager.positions['AAPL'] = sample_position

        # Update price
        manager.update_position_price('AAPL', 152.50)

        assert manager.positions['AAPL'].current_price == 152.50
        assert manager.positions['AAPL'].last_update is not None
        assert manager.positions['AAPL'].unrealized_pnl == pytest.approx(250.0)

    def test_update_position_price_multiple_updates(self, manager, sample_position):
        """Test multiple price updates."""
        manager.positions['AAPL'] = sample_position

        # First update
        manager.update_position_price('AAPL', 151.00)
        assert manager.positions['AAPL'].current_price == 151.00
        first_update_time = manager.positions['AAPL'].last_update

        # Second update
        import time
        time.sleep(0.01)  # Ensure time difference
        manager.update_position_price('AAPL', 152.00)
        assert manager.positions['AAPL'].current_price == 152.00
        assert manager.positions['AAPL'].last_update > first_update_time

    def test_update_nonexistent_position(self, manager):
        """Test updating price for non-existent position (should not error)."""
        # Should not raise exception
        manager.update_position_price('NONEXISTENT', 100.00)

        # Position should not be created
        assert 'NONEXISTENT' not in manager.positions

    def test_update_position_price_with_negative_price(self, manager, sample_position):
        """Test updating with negative price (edge case)."""
        manager.positions['AAPL'] = sample_position

        # Negative price should still update (validation is elsewhere)
        manager.update_position_price('AAPL', -10.00)
        assert manager.positions['AAPL'].current_price == -10.00

    def test_update_position_price_with_zero(self, manager, sample_position):
        """Test updating with zero price."""
        manager.positions['AAPL'] = sample_position

        manager.update_position_price('AAPL', 0.0)
        assert manager.positions['AAPL'].current_price == 0.0
        assert manager.positions['AAPL'].unrealized_pnl == 0.0


class TestPortfolioPnL:
    """Test portfolio-level P&L aggregation."""

    @pytest.fixture
    def manager(self):
        """Create fresh OrderManager instance."""
        mgr = OrderManager()
        mgr.positions.clear()
        mgr.closed_trades.clear()
        return mgr

    def test_portfolio_pnl_empty(self, manager):
        """Test portfolio P&L with no positions."""
        pnl = manager.get_portfolio_pnl()

        assert pnl['realized_pnl'] == 0.0
        assert pnl['unrealized_pnl'] == 0.0
        assert pnl['total_pnl'] == 0.0
        assert pnl['positions_count'] == 0
        assert pnl['winning_positions'] == 0
        assert pnl['losing_positions'] == 0

    def test_portfolio_pnl_single_position(self, manager):
        """Test portfolio P&L with single position."""
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=153.00,
            entry_time=datetime.now()
        )

        pnl = manager.get_portfolio_pnl()

        assert pnl['unrealized_pnl'] == pytest.approx(300.0)
        assert pnl['positions_count'] == 1
        assert pnl['winning_positions'] == 1
        assert pnl['losing_positions'] == 0

    def test_portfolio_pnl_multiple_positions(self, manager):
        """Test portfolio P&L with multiple positions."""
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=153.00,  # +$300
            entry_time=datetime.now()
        )
        manager.positions['TSLA'] = Position(
            symbol='TSLA', side='BUY', quantity=50,
            entry_price=200.00, current_price=198.00,  # -$100
            entry_time=datetime.now()
        )
        manager.positions['MSFT'] = Position(
            symbol='MSFT', side='BUY', quantity=75,
            entry_price=300.00, current_price=304.00,  # +$300
            entry_time=datetime.now()
        )

        pnl = manager.get_portfolio_pnl()

        assert pnl['unrealized_pnl'] == pytest.approx(500.0)  # 300 - 100 + 300
        assert pnl['positions_count'] == 3
        assert pnl['winning_positions'] == 2
        assert pnl['losing_positions'] == 1

    def test_portfolio_pnl_with_closed_trades(self, manager):
        """Test portfolio P&L including closed trades."""
        # Add open position
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=153.00,  # +$300 unrealized
            entry_time=datetime.now()
        )

        # Add closed trades
        manager.closed_trades.append(ClosedTrade(
            symbol='MSFT', side='BUY', quantity=50,
            entry_price=300.00, exit_price=310.00,
            entry_time=datetime.now(), exit_time=datetime.now(),
            pnl=500.00, pnl_pct=3.33  # +$500 realized
        ))
        manager.closed_trades.append(ClosedTrade(
            symbol='GOOGL', side='BUY', quantity=25,
            entry_price=2800.00, exit_price=2750.00,
            entry_time=datetime.now(), exit_time=datetime.now(),
            pnl=-1250.00, pnl_pct=-1.79  # -$1250 realized
        ))

        pnl = manager.get_portfolio_pnl()

        assert pnl['unrealized_pnl'] == pytest.approx(300.0)
        assert pnl['realized_pnl'] == pytest.approx(-750.0)  # 500 - 1250
        assert pnl['total_pnl'] == pytest.approx(-450.0)  # 300 - 750
        assert pnl['positions_count'] == 1
        assert pnl['closed_trades_count'] == 2
        assert pnl['winning_trades'] == 1
        assert pnl['losing_trades'] == 1

    def test_portfolio_pnl_all_breakeven(self, manager):
        """Test portfolio P&L with all positions at breakeven."""
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=150.00,
            entry_time=datetime.now()
        )
        manager.positions['TSLA'] = Position(
            symbol='TSLA', side='SELL', quantity=50,
            entry_price=200.00, current_price=200.00,
            entry_time=datetime.now()
        )

        pnl = manager.get_portfolio_pnl()

        assert pnl['unrealized_pnl'] == 0.0
        assert pnl['winning_positions'] == 0
        assert pnl['losing_positions'] == 0


class TestPositionsDataFrame:
    """Test DataFrame output for positions."""

    @pytest.fixture
    def manager(self):
        """Create fresh OrderManager instance."""
        mgr = OrderManager()
        mgr.positions.clear()
        return mgr

    def test_get_positions_dataframe_empty(self, manager):
        """Test DataFrame output with no positions."""
        df = manager.get_positions_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_get_positions_dataframe_single_position(self, manager):
        """Test DataFrame output with single position."""
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=153.00,
            stop_price=147.00, target_price=156.00,
            entry_time=datetime.now()
        )

        df = manager.get_positions_dataframe()

        assert len(df) == 1
        assert df.iloc[0]['symbol'] == 'AAPL'
        assert df.iloc[0]['side'] == 'BUY'
        assert df.iloc[0]['quantity'] == 100
        assert df.iloc[0]['entry_price'] == 150.00
        assert df.iloc[0]['current_price'] == 153.00
        assert df.iloc[0]['unrealized_pnl'] == pytest.approx(300.0)
        assert df.iloc[0]['unrealized_pnl_pct'] == pytest.approx(2.0)

    def test_get_positions_dataframe_multiple_positions(self, manager):
        """Test DataFrame output with multiple positions."""
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=153.00,
            entry_time=datetime.now()
        )
        manager.positions['TSLA'] = Position(
            symbol='TSLA', side='SELL', quantity=50,
            entry_price=200.00, current_price=195.00,
            entry_time=datetime.now()
        )

        df = manager.get_positions_dataframe()

        assert len(df) == 2
        assert set(df['symbol']) == {'AAPL', 'TSLA'}
        assert 'unrealized_pnl' in df.columns
        assert 'unrealized_pnl_pct' in df.columns
        assert 'current_risk' in df.columns

    def test_get_positions_dataframe_columns(self, manager):
        """Test that DataFrame has all expected columns."""
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=153.00,
            entry_time=datetime.now()
        )

        df = manager.get_positions_dataframe()

        expected_columns = [
            'symbol', 'side', 'quantity', 'entry_price', 'current_price',
            'stop_price', 'target_price', 'unrealized_pnl', 'unrealized_pnl_pct',
            'current_risk', 'entry_time', 'last_update'
        ]

        for col in expected_columns:
            assert col in df.columns


class TestRealtimeAggregatorIntegration:
    """Test integration between RealtimeAggregator and OrderManager."""

    @pytest.fixture
    def aggregator(self):
        """Create RealtimeAggregator instance."""
        return RealtimeAggregator(
            source_timeframe='5sec',
            target_timeframes=['1min', '5min']
        )

    @pytest.fixture
    def manager(self):
        """Use global order_manager singleton and clear positions."""
        order_manager.positions.clear()
        return order_manager

    def test_aggregator_updates_position_on_bar_complete(self, aggregator, manager):
        """Test that aggregator updates position prices when bars complete."""
        # Add position to manager
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=150.00,
            entry_time=datetime.now()
        )

        # Add bars to trigger aggregation
        # Create 12 bars @ 5sec each = 60 seconds = 1 complete 1min bar
        base_time = datetime(2025, 11, 15, 9, 30, 0)

        for i in range(13):  # 13 bars to complete one 1min bar
            bar = Bar(
                timestamp=base_time + timedelta(seconds=i*5),
                open=150.00 + i*0.1,
                high=150.10 + i*0.1,
                low=149.90 + i*0.1,
                close=150.00 + i*0.1,
                volume=1000,
                complete=True
            )
            aggregator.add_bar('AAPL', bar)

        # Position should be updated with close price from completed bar
        # Last completed bar would be at i=11 (12th bar completes the 1min bar)
        # close = 150.00 + 11*0.1 = 151.10
        assert manager.positions['AAPL'].current_price == pytest.approx(151.10, abs=0.2)
        assert manager.positions['AAPL'].last_update is not None

    def test_aggregator_handles_missing_position_gracefully(self, aggregator):
        """Test that aggregator doesn't error when position doesn't exist."""
        # Add bar for symbol with no position
        bar = Bar(
            timestamp=datetime.now(),
            open=150.00,
            high=150.50,
            low=149.50,
            close=150.25,
            volume=1000,
            complete=True
        )

        # Should not raise exception
        aggregator.add_bar('NONEXISTENT', bar)

    def test_aggregator_updates_multiple_positions(self, aggregator, manager):
        """Test aggregator updating multiple positions."""
        # Add multiple positions
        manager.positions['AAPL'] = Position(
            symbol='AAPL', side='BUY', quantity=100,
            entry_price=150.00, current_price=150.00,
            entry_time=datetime.now()
        )
        manager.positions['TSLA'] = Position(
            symbol='TSLA', side='BUY', quantity=50,
            entry_price=200.00, current_price=200.00,
            entry_time=datetime.now()
        )

        base_time = datetime(2025, 11, 15, 9, 30, 0)

        # Add bars for both symbols
        for symbol, price in [('AAPL', 150.0), ('TSLA', 200.0)]:
            for i in range(13):
                bar = Bar(
                    timestamp=base_time + timedelta(seconds=i*5),
                    open=price + i*0.1,
                    high=price + 0.10 + i*0.1,
                    low=price - 0.10 + i*0.1,
                    close=price + i*0.1,
                    volume=1000,
                    complete=True
                )
                aggregator.add_bar(symbol, bar)

        # Both positions should be updated
        assert manager.positions['AAPL'].current_price > 150.0
        assert manager.positions['TSLA'].current_price > 200.0
        assert manager.positions['AAPL'].last_update is not None
        assert manager.positions['TSLA'].last_update is not None


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_position_with_very_large_quantity(self):
        """Test position with very large quantity."""
        position = Position(
            symbol='TEST',
            side='BUY',
            quantity=1000000,  # 1 million shares
            entry_price=10.00,
            current_price=10.01,
            entry_time=datetime.now()
        )

        # P&L should handle large numbers
        assert position.unrealized_pnl == pytest.approx(10000.0)

    def test_position_with_very_small_price_change(self):
        """Test position with very small price change."""
        position = Position(
            symbol='TEST',
            side='BUY',
            quantity=100,
            entry_price=150.0000,
            current_price=150.0001,
            entry_time=datetime.now()
        )

        # Should handle small price changes
        assert position.unrealized_pnl == pytest.approx(0.01, abs=0.001)

    def test_position_timestamp_handling(self):
        """Test position timestamp handling."""
        entry_time = datetime(2025, 11, 15, 9, 30, 0)
        position = Position(
            symbol='TEST',
            side='BUY',
            quantity=100,
            entry_price=150.00,
            current_price=150.00,
            entry_time=entry_time
        )

        assert position.entry_time == entry_time
        assert position.last_update is None  # Not yet updated

        # Simulate update
        position.last_update = datetime(2025, 11, 15, 9, 31, 0)
        assert position.last_update > position.entry_time

    def test_portfolio_pnl_division_by_zero_protection(self):
        """Test that portfolio P&L doesn't fail with zero positions."""
        manager = OrderManager()
        manager.positions.clear()

        pnl = manager.get_portfolio_pnl()

        # Should not raise division by zero
        assert pnl['positions_count'] == 0
        assert pnl['winning_positions'] == 0
