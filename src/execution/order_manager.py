"""
Trade Execution and Order Management

Handles order validation, submission, and tracking with strict risk controls.

Safety Controls:
----------------
1. Global kill switch (allow_execution in config)
2. Paper trading enforcement
3. Position size limits (1% risk per trade, 3% total)
4. Order validation before submission
5. Duplicate order prevention

Order Flow:
-----------
1. Validate setup (SABR20 score, regime compatibility)
2. Calculate position size based on risk
3. Validate against risk limits
4. Submit order to IB
5. Track position

Usage:
------
from src.execution.order_manager import order_manager

# Validate and submit order
order = order_manager.create_order_from_setup(
    setup=sabr20_score,
    account_value=100000
)

if order:
    result = order_manager.submit_order(order)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import pandas as pd
from loguru import logger
from ib_insync import Stock, Order, Trade

from src.config import config
from src.data.ib_manager import ib_manager
from src.screening.sabr20_engine import SABR20Score
from src.regime.regime_detector import regime_detector


class OrderStatus(Enum):
    """Order status types."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class TradeOrder:
    """
    Trade order representation.

    Attributes:
    -----------
    symbol : str
        Stock symbol
    action : str
        'BUY' or 'SELL'
    quantity : int
        Number of shares
    entry_price : float
        Target entry price
    stop_loss : float
        Stop loss price
    take_profit : float
        Take profit price
    risk_amount : float
        Dollar risk amount
    position_size_pct : float
        Position size as % of account
    sabr20_score : float
        SABR20 score that triggered this order
    timestamp : datetime
        Order creation time
    order_id : int or None
        IB order ID (after submission)
    status : OrderStatus
        Current status
    """
    symbol: str
    action: str
    quantity: int
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    position_size_pct: float
    sabr20_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    order_id: Optional[int] = None
    status: OrderStatus = OrderStatus.PENDING


class OrderManager:
    """
    Order management and execution system.

    Validates and submits orders with strict risk controls.

    Attributes:
    -----------
    max_risk_per_trade : float
        Maximum risk per trade as % of account
    max_total_risk : float
        Maximum total risk across all positions
    max_positions : int
        Maximum concurrent positions
    allow_execution : bool
        Master kill switch for live trading
    """

    def __init__(self):
        """Initialize order manager with configuration."""
        # Load execution configuration
        exec_config = config.trading.execution

        self.allow_execution = exec_config.allow_execution
        self.require_paper_trading = exec_config.require_paper_trading_mode
        self.max_risk_per_trade = exec_config.max_risk_per_trade_pct / 100
        self.max_total_risk = exec_config.max_total_risk_pct / 100
        self.max_positions = exec_config.max_concurrent_positions

        # Active positions tracking
        self.active_positions: Dict[str, TradeOrder] = {}
        self.order_history: List[TradeOrder] = []

        # Safety check
        if self.allow_execution:
            logger.warning("⚠️  LIVE EXECUTION ENABLED - Orders will be submitted!")
        else:
            logger.info("✅ Execution disabled (SCREENER-ONLY mode)")

        logger.info(
            f"Order manager initialized: "
            f"max_risk={self.max_risk_per_trade:.1%}, "
            f"max_total={self.max_total_risk:.1%}, "
            f"max_positions={self.max_positions}"
        )

    def validate_execution_allowed(self) -> bool:
        """
        Validate that execution is allowed.

        Checks:
        1. allow_execution flag
        2. IB connection status
        3. Paper trading requirement

        Returns:
        --------
        bool
            True if execution allowed
        """
        if not self.allow_execution:
            logger.warning("Execution blocked: allow_execution=False in config")
            return False

        if not ib_manager.is_connected():
            logger.error("Execution blocked: IB not connected")
            return False

        # Check paper trading requirement
        if self.require_paper_trading:
            # Get account info
            try:
                account_values = ib_manager.ib.accountValues()
                account_type = ib_manager.ib.accountSummary()

                # This is a simplification - in reality, you'd check port number
                # Port 7497 = TWS Paper, 7496 = TWS Live
                if ib_manager.profile.port not in [7497, 4002]:  # Paper trading ports
                    logger.error(
                        "Execution blocked: Paper trading required but connected to live port"
                    )
                    return False
            except Exception as e:
                logger.error(f"Error checking account type: {e}")
                return False

        return True

    def calculate_position_size(
        self,
        account_value: float,
        entry_price: float,
        stop_loss: float,
        regime_adjustment: float = 1.0
    ) -> Dict[str, Any]:
        """
        Calculate position size based on risk parameters.

        Uses fixed fractional position sizing:
        Position Size = (Account × Risk %) / (Entry - Stop)

        Parameters:
        -----------
        account_value : float
            Total account value
        entry_price : float
            Entry price
        stop_loss : float
            Stop loss price
        regime_adjustment : float, default=1.0
            Risk adjustment factor from regime detector (0.0-1.0)

        Returns:
        --------
        dict
            {'quantity': int, 'risk_amount': float, 'position_value': float, 'position_pct': float}
        """
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share <= 0:
            logger.error("Invalid stop loss: must be below entry for longs")
            return {'quantity': 0, 'risk_amount': 0, 'position_value': 0, 'position_pct': 0}

        # Adjusted risk percentage
        adjusted_risk_pct = self.max_risk_per_trade * regime_adjustment

        # Calculate risk amount
        risk_amount = account_value * adjusted_risk_pct

        # Calculate quantity
        quantity = int(risk_amount / risk_per_share)

        # Calculate actual position value and percentage
        position_value = quantity * entry_price
        position_pct = position_value / account_value

        logger.debug(
            f"Position sizing: qty={quantity}, value=${position_value:.2f} "
            f"({position_pct:.1%}), risk=${risk_amount:.2f}"
        )

        return {
            'quantity': quantity,
            'risk_amount': risk_amount,
            'position_value': position_value,
            'position_pct': position_pct
        }

    def validate_risk_limits(
        self,
        new_risk_amount: float,
        account_value: float
    ) -> bool:
        """
        Validate that new order doesn't exceed risk limits.

        Checks:
        1. Individual trade risk <= max_risk_per_trade
        2. Total portfolio risk <= max_total_risk
        3. Position count <= max_positions

        Parameters:
        -----------
        new_risk_amount : float
            Risk amount for new order
        account_value : float
            Total account value

        Returns:
        --------
        bool
            True if within limits
        """
        # Check individual trade risk
        new_trade_risk_pct = new_risk_amount / account_value
        if new_trade_risk_pct > self.max_risk_per_trade:
            logger.warning(
                f"Order rejected: trade risk {new_trade_risk_pct:.1%} "
                f"exceeds limit {self.max_risk_per_trade:.1%}"
            )
            return False

        # Calculate current total risk
        current_total_risk = sum(
            pos.risk_amount for pos in self.active_positions.values()
        )
        new_total_risk = current_total_risk + new_risk_amount
        new_total_risk_pct = new_total_risk / account_value

        if new_total_risk_pct > self.max_total_risk:
            logger.warning(
                f"Order rejected: total risk {new_total_risk_pct:.1%} "
                f"exceeds limit {self.max_total_risk:.1%}"
            )
            return False

        # Check position count
        if len(self.active_positions) >= self.max_positions:
            logger.warning(
                f"Order rejected: {len(self.active_positions)} positions "
                f"(max {self.max_positions})"
            )
            return False

        return True

    def create_order_from_setup(
        self,
        setup: SABR20Score,
        account_value: float
    ) -> Optional[TradeOrder]:
        """
        Create order from SABR20 setup.

        Parameters:
        -----------
        setup : SABR20Score
            Scored setup
        account_value : float
            Account value for position sizing

        Returns:
        --------
        TradeOrder or None
            Created order, or None if validation failed
        """
        try:
            # Extract entry/stop/target from setup
            rr_details = setup.details.get('risk_reward', {})
            entry_price = rr_details.get('entry')
            stop_loss = rr_details.get('stop')
            take_profit = rr_details.get('target')

            if not all([entry_price, stop_loss, take_profit]):
                logger.warning(f"Incomplete price data for {setup.symbol}")
                return None

            # Get regime adjustment
            regime_adjustment = regime_detector.get_risk_adjustment_factor()

            # Calculate position size
            sizing = self.calculate_position_size(
                account_value=account_value,
                entry_price=entry_price,
                stop_loss=stop_loss,
                regime_adjustment=regime_adjustment
            )

            if sizing['quantity'] == 0:
                logger.warning(f"Position size = 0 for {setup.symbol}")
                return None

            # Validate risk limits
            if not self.validate_risk_limits(sizing['risk_amount'], account_value):
                return None

            # Create order
            order = TradeOrder(
                symbol=setup.symbol,
                action='BUY',
                quantity=sizing['quantity'],
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_amount=sizing['risk_amount'],
                position_size_pct=sizing['position_pct'],
                sabr20_score=setup.total_points
            )

            logger.info(
                f"Created order: {order.symbol} {order.action} {order.quantity} shares "
                f"@ ${order.entry_price:.2f} (risk: ${order.risk_amount:.2f})"
            )

            return order

        except Exception as e:
            logger.error(f"Error creating order from setup {setup.symbol}: {e}")
            return None

    def submit_order(
        self,
        trade_order: TradeOrder,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Submit order to Interactive Brokers.

        Parameters:
        -----------
        trade_order : TradeOrder
            Order to submit
        dry_run : bool, default=False
            If True, validates but doesn't submit

        Returns:
        --------
        dict
            {'success': bool, 'order_id': int or None, 'message': str, 'trade': Trade or None}
        """
        try:
            # Validate execution allowed
            if not self.validate_execution_allowed() and not dry_run:
                return {
                    'success': False,
                    'order_id': None,
                    'message': 'Execution not allowed',
                    'trade': None
                }

            # Check for duplicate
            if trade_order.symbol in self.active_positions:
                return {
                    'success': False,
                    'order_id': None,
                    'message': f'Position already exists for {trade_order.symbol}',
                    'trade': None
                }

            # Create IB contract
            contract = Stock(trade_order.symbol, 'SMART', 'USD')

            # Create IB order (market order)
            ib_order = Order()
            ib_order.action = trade_order.action
            ib_order.totalQuantity = trade_order.quantity
            ib_order.orderType = 'MKT'  # Market order for immediate fill

            # Dry run - just validate
            if dry_run:
                logger.info(
                    f"DRY RUN: Would submit {trade_order.symbol} "
                    f"{trade_order.action} {trade_order.quantity}"
                )
                return {
                    'success': True,
                    'order_id': None,
                    'message': 'Dry run - order validated',
                    'trade': None
                }

            # Submit order
            trade = ib_manager.ib.placeOrder(contract, ib_order)
            ib_manager.ib.sleep(1)  # Wait for order acknowledgment

            # Update trade order
            trade_order.order_id = ib_order.orderId
            trade_order.status = OrderStatus.SUBMITTED

            # Track position
            self.active_positions[trade_order.symbol] = trade_order
            self.order_history.append(trade_order)

            logger.info(
                f"✅ Order submitted: {trade_order.symbol} {trade_order.action} "
                f"{trade_order.quantity} @ ${trade_order.entry_price:.2f} "
                f"(Order ID: {ib_order.orderId})"
            )

            return {
                'success': True,
                'order_id': ib_order.orderId,
                'message': 'Order submitted successfully',
                'trade': trade
            }

        except Exception as e:
            logger.error(f"Error submitting order for {trade_order.symbol}: {e}")
            trade_order.status = OrderStatus.REJECTED
            return {
                'success': False,
                'order_id': None,
                'message': str(e),
                'trade': None
            }

    def get_active_positions(self) -> List[TradeOrder]:
        """Get list of active positions."""
        return list(self.active_positions.values())

    def get_total_risk(self) -> float:
        """Get total risk across all positions."""
        return sum(pos.risk_amount for pos in self.active_positions.values())

    def get_position_summary(self) -> pd.DataFrame:
        """Get summary of active positions as DataFrame."""
        if not self.active_positions:
            return pd.DataFrame()

        rows = []
        for pos in self.active_positions.values():
            rows.append({
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'entry': pos.entry_price,
                'stop': pos.stop_loss,
                'target': pos.take_profit,
                'risk': pos.risk_amount,
                'sabr20': pos.sabr20_score,
                'status': pos.status.value,
                'timestamp': pos.timestamp
            })

        return pd.DataFrame(rows)


# Global singleton instance
order_manager = OrderManager()
