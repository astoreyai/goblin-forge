"""
Screener System - Main Entry Point

Orchestrates the complete screening pipeline from data collection to watchlist generation.

System Flow:
------------
1. Connect to IB API
2. Detect market regime
3. Build and filter universe
4. Run screening pipeline
5. Generate watchlist
6. (Optional) Submit orders
7. Display results

Run Modes:
----------
- Screening Only (default): Generate watchlist, no execution
- With Execution: Submit validated orders to IB
- Dashboard: Launch web dashboard

Usage:
------
# Screening only
python src/main.py

# With dashboard
python src/main.py --dashboard

# Schedule periodic screening
python src/main.py --schedule 5m
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config
from src.data.ib_manager import ib_manager
from src.regime.regime_detector import regime_detector
from src.screening.watchlist import watchlist_generator
from src.execution.order_manager import order_manager


class ScreenerSystem:
    """
    Main screener system orchestrator.

    Coordinates all components to run complete screening pipeline.
    """

    def __init__(self):
        """Initialize screener system."""
        self.session_start = datetime.now()
        logger.info("=" * 70)
        logger.info("SCREENER SYSTEM INITIALIZED")
        logger.info(f"Session started: {self.session_start}")
        logger.info("=" * 70)

    def connect_ib(self) -> bool:
        """
        Connect to Interactive Brokers.

        Returns:
        --------
        bool
            True if connected successfully
        """
        try:
            logger.info("Connecting to Interactive Brokers...")

            # Get IB configuration
            ib_config = config.ib
            active_profile = ib_config.active_profile

            logger.info(f"Using profile: {active_profile}")

            # Connect
            success = ib_manager.connect(profile=active_profile)

            if success:
                logger.info("✅ Connected to Interactive Brokers")
                return True
            else:
                logger.error("❌ Failed to connect to Interactive Brokers")
                return False

        except Exception as e:
            logger.error(f"Error connecting to IB: {e}")
            return False

    def run_screening_pipeline(
        self,
        max_symbols: int = 20,
        min_score: float = 50.0
    ):
        """
        Run complete screening pipeline.

        Parameters:
        -----------
        max_symbols : int, default=20
            Maximum watchlist size
        min_score : float, default=50.0
            Minimum SABR20 score

        Returns:
        --------
        list of SABR20Score
            Generated watchlist
        """
        logger.info("=" * 70)
        logger.info("SCREENING PIPELINE STARTED")
        logger.info("=" * 70)

        try:
            # Step 1: Detect market regime
            logger.info("Step 1: Detecting market regime...")
            regime = regime_detector.detect_regime()

            logger.info(
                f"Regime: {regime['type_str']} "
                f"(confidence: {regime['confidence']:.0%})"
            )
            logger.info(f"Strategy fit: {regime['recommendation']['strategy_suitability']}")
            logger.info(f"Risk adjustment: {regime['recommendation']['risk_adjustment']}")

            # Step 2-5: Generate watchlist (universe → coarse → fine → ranked)
            logger.info("\nStep 2-5: Running screening pipeline...")
            watchlist = watchlist_generator.generate(
                max_symbols=max_symbols,
                min_score=min_score
            )

            # Display results
            logger.info("\n" + "=" * 70)
            logger.info("SCREENING COMPLETE")
            logger.info("=" * 70)

            if watchlist:
                logger.info(f"\n📊 WATCHLIST ({len(watchlist)} setups):\n")

                for i, setup in enumerate(watchlist, 1):
                    rr = setup.details.get('risk_reward', {})

                    logger.info(
                        f"{i:2d}. {setup.symbol:6s} | "
                        f"Score: {setup.total_points:5.1f}/100 ({setup.setup_grade:10s}) | "
                        f"Entry: ${rr.get('entry', 0):7.2f} | "
                        f"Target: ${rr.get('target', 0):7.2f} | "
                        f"R:R: {rr.get('rr_ratio', 0):4.1f}:1"
                    )

                    # Show component breakdown for top 3
                    if i <= 3:
                        logger.info(f"       Components: {setup.component_scores}")

            else:
                logger.warning("⚠️  No setups found matching criteria")

            return watchlist

        except Exception as e:
            logger.error(f"Error in screening pipeline: {e}")
            return []

    def execute_orders(
        self,
        watchlist,
        account_value: float = 100000,
        dry_run: bool = True
    ):
        """
        Execute orders from watchlist (if enabled).

        Parameters:
        -----------
        watchlist : list of SABR20Score
            Watchlist to execute from
        account_value : float, default=100000
            Account value for position sizing
        dry_run : bool, default=True
            If True, validates without submitting
        """
        if not order_manager.allow_execution and not dry_run:
            logger.info("\n⏸️  Execution disabled (SCREENER-ONLY mode)")
            logger.info("To enable execution, set allow_execution: true in config/trading_params.yaml")
            return

        logger.info("\n" + "=" * 70)
        logger.info("ORDER EXECUTION" + (" (DRY RUN)" if dry_run else " (LIVE)"))
        logger.info("=" * 70)

        if not watchlist:
            logger.info("No setups to execute")
            return

        # Execute top setups
        for setup in watchlist[:5]:  # Top 5 only
            # Create order
            order = order_manager.create_order_from_setup(
                setup=setup,
                account_value=account_value
            )

            if order:
                # Submit order
                result = order_manager.submit_order(order, dry_run=dry_run)

                if result['success']:
                    logger.info(
                        f"✅ {setup.symbol}: {order.quantity} shares @ ${order.entry_price:.2f} "
                        f"(risk: ${order.risk_amount:.2f})"
                    )
                else:
                    logger.warning(f"❌ {setup.symbol}: {result['message']}")
            else:
                logger.warning(f"⏭️  {setup.symbol}: Order creation failed")

        # Display position summary
        positions = order_manager.get_position_summary()
        if not positions.empty:
            logger.info(f"\n📋 ACTIVE POSITIONS ({len(positions)}):")
            logger.info(positions.to_string())

    def run(
        self,
        connect_ib_api: bool = True,
        run_execution: bool = False,
        dry_run: bool = True
    ):
        """
        Run complete system.

        Parameters:
        -----------
        connect_ib_api : bool, default=True
            Connect to IB API
        run_execution : bool, default=False
            Execute orders from watchlist
        dry_run : bool, default=True
            Dry run mode (validation only)
        """
        try:
            # Connect to IB if requested
            if connect_ib_api:
                if not self.connect_ib():
                    logger.error("Failed to connect to IB - continuing with cached data only")

            # Run screening pipeline
            watchlist = self.run_screening_pipeline()

            # Execute orders if requested
            if run_execution:
                self.execute_orders(
                    watchlist=watchlist,
                    dry_run=dry_run
                )

            # Session summary
            duration = (datetime.now() - self.session_start).total_seconds()
            logger.info("\n" + "=" * 70)
            logger.info(f"SESSION COMPLETE (Duration: {duration:.1f}s)")
            logger.info("=" * 70)

            return watchlist

        except KeyboardInterrupt:
            logger.info("\n⏸️  System interrupted by user")
            self.shutdown()

        except Exception as e:
            logger.error(f"System error: {e}")
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown."""
        logger.info("\nShutting down...")

        # Disconnect from IB
        if ib_manager.is_connected():
            logger.info("Disconnecting from IB...")
            ib_manager.disconnect()

        logger.info("✅ System shutdown complete")


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Screener - Mean Reversion Trading System"
    )

    parser.add_argument(
        '--no-ib',
        action='store_true',
        help='Run without connecting to IB (uses cached data)'
    )

    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute orders from watchlist (if enabled in config)'
    )

    parser.add_argument(
        '--live',
        action='store_true',
        help='Live execution mode (default is dry run)'
    )

    parser.add_argument(
        '--dashboard',
        action='store_true',
        help='Launch web dashboard'
    )

    parser.add_argument(
        '--schedule',
        type=str,
        metavar='INTERVAL',
        help='Run on schedule (e.g., "5m", "1h", "1d")'
    )

    parser.add_argument(
        '--max-symbols',
        type=int,
        default=20,
        help='Maximum watchlist size (default: 20)'
    )

    parser.add_argument(
        '--min-score',
        type=float,
        default=50.0,
        help='Minimum SABR20 score (default: 50.0)'
    )

    args = parser.parse_args()

    # Launch dashboard if requested
    if args.dashboard:
        logger.info("Launching dashboard...")
        from src.dashboard.app import app
        app.run(debug=True, host='0.0.0.0', port=8050)
        return

    # Initialize system
    system = ScreenerSystem()

    # Run system
    system.run(
        connect_ib_api=not args.no_ib,
        run_execution=args.execute,
        dry_run=not args.live
    )


if __name__ == '__main__':
    main()
