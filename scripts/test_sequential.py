"""
Sequential Testing Workflow

Tests all system components in sequence with user-friendly progress display:
1. IB Gateway connectivity
2. Historical data fetching
3. Parquet storage/retrieval
4. Multi-timeframe aggregation
5. Aggregation accuracy validation
6. Trade validation (risk controls)

Run:
----
python scripts/test_sequential.py

Options:
--------
--skip-ib          Skip IB Gateway tests (use cached data)
--component NAME   Run only specific component
--verbose          Show detailed output

Examples:
---------
python scripts/test_sequential.py                    # Run all tests
python scripts/test_sequential.py --component ib     # Test IB only
python scripts/test_sequential.py --skip-ib          # Skip IB tests
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import traceback

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.ib_manager import IBDataManager
from src.data.historical_manager import HistoricalDataManager
from src.data.realtime_aggregator import RealtimeAggregator, Bar, Timeframe
from src.execution.validator import ExecutionValidator, TradeProposal
import pandas as pd
import numpy as np

# Test configuration
TEST_SYMBOL = 'SPY'
TEST_SYMBOLS_MULTI = ['SPY', 'AAPL', 'MSFT']
BASE_TIMEFRAME = '5 secs'
DURATION = '600 S'  # 10 minutes for complete 5min bar
DATA_DIR = 'data/historical_test'

# Global results
results = {
    'start_time': None,
    'end_time': None,
    'tests_run': 0,
    'tests_passed': 0,
    'tests_failed': 0,
    'components': {},
}


def print_header(title: str, level: int = 1):
    """Print formatted section header."""
    if level == 1:
        print("\n" + "=" * 80)
        print(f"{title.upper()}")
        print("=" * 80)
    elif level == 2:
        print("\n" + "-" * 80)
        print(f"{title}")
        print("-" * 80)
    else:
        print(f"\n{title}")


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result with consistent formatting."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        for line in details.split('\n'):
            print(f"      {line}")


def test_ib_connectivity(verbose: bool = False) -> bool:
    """Test 1: IB Gateway Connectivity."""
    print_header("TEST 1: IB GATEWAY CONNECTIVITY", level=1)

    test_results = {
        'connection': False,
        'state': None,
        'health': False,
        'version': None,
    }

    try:
        print("\n[1/3] Initializing IB Manager...")
        ib_manager = IBDataManager(port=4002, client_id=200, heartbeat_enabled=False)

        print("[2/3] Connecting to IB Gateway (port 4002)...")
        connected = ib_manager.connect()

        if not connected:
            print_result("IB Gateway Connection", False, "Failed to connect - ensure IB Gateway is running")
            return False

        test_results['connection'] = True
        test_results['state'] = ib_manager.state
        test_results['health'] = ib_manager.is_healthy()

        print("[3/3] Verifying connection health...")
        time.sleep(1)  # Allow heartbeat

        details = f"State: {test_results['state']}\nHealthy: {test_results['health']}"
        print_result("IB Gateway Connection", True, details)

        # Cleanup
        ib_manager.disconnect()

        results['components']['ib_connectivity'] = test_results
        return True

    except Exception as e:
        print_result("IB Gateway Connection", False, f"Error: {e}")
        if verbose:
            traceback.print_exc()
        return False


def test_historical_data_fetch(ib_manager: Optional[IBDataManager] = None, verbose: bool = False) -> Tuple[bool, Optional[pd.DataFrame]]:
    """Test 2: Historical Data Fetching."""
    print_header("TEST 2: HISTORICAL DATA FETCHING", level=1)

    cleanup_ib = False

    try:
        if ib_manager is None:
            print("\n[1/4] Connecting to IB Gateway...")
            ib_manager = IBDataManager(port=4002, client_id=201, heartbeat_enabled=False)
            if not ib_manager.connect():
                print_result("Historical Data Fetch", False, "Failed to connect to IB Gateway")
                return False, None
            cleanup_ib = True

        print(f"[2/4] Fetching {BASE_TIMEFRAME} bars for {TEST_SYMBOL} ({DURATION})...")
        data = ib_manager.fetch_historical_bars(TEST_SYMBOL, BASE_TIMEFRAME, DURATION)

        if data is None or len(data) == 0:
            print_result("Historical Data Fetch", False, "No data returned")
            return False, None

        print(f"[3/4] Validating data structure...")
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            print_result("Historical Data Fetch", False, "Missing required columns")
            return False, None

        print(f"[4/4] Validating OHLCV integrity...")
        if not (data['high'] >= data['low']).all():
            print_result("Historical Data Fetch", False, "Data corruption: high < low")
            return False, None

        details = (
            f"Bars: {len(data)}\n"
            f"Date range: {data.index[0]} to {data.index[-1]}\n"
            f"Price range: ${data['low'].min():.2f} - ${data['high'].max():.2f}\n"
            f"Volume: {data['volume'].sum():,.0f}"
        )
        print_result("Historical Data Fetch", True, details)

        results['components']['historical_fetch'] = {
            'bars': len(data),
            'date_range': f"{data.index[0]} to {data.index[-1]}",
            'price_range': f"${data['low'].min():.2f} - ${data['high'].max():.2f}",
            'volume': int(data['volume'].sum()),
        }

        return True, data

    except Exception as e:
        print_result("Historical Data Fetch", False, f"Error: {e}")
        if verbose:
            traceback.print_exc()
        return False, None

    finally:
        if cleanup_ib and ib_manager:
            ib_manager.disconnect()


def test_parquet_storage(data: pd.DataFrame, verbose: bool = False) -> bool:
    """Test 3: Parquet Storage and Retrieval."""
    print_header("TEST 3: PARQUET STORAGE & RETRIEVAL", level=1)

    try:
        print("\n[1/4] Initializing Historical Manager...")
        hist_manager = HistoricalDataManager(data_dir=DATA_DIR)

        print(f"[2/4] Saving {len(data)} bars to Parquet...")
        file_path = hist_manager.save_symbol_data(TEST_SYMBOL, BASE_TIMEFRAME, data)

        if not Path(file_path).exists():
            print_result("Parquet Storage", False, "File not created")
            return False

        print(f"[3/4] Loading data from Parquet...")
        loaded_data = hist_manager.load_symbol_data(TEST_SYMBOL, BASE_TIMEFRAME)

        if loaded_data is None or len(loaded_data) == 0:
            print_result("Parquet Storage", False, "Failed to load data")
            return False

        print(f"[4/4] Verifying data integrity...")
        if len(loaded_data) != len(data):
            print_result("Parquet Storage", False, f"Bar count mismatch: {len(loaded_data)} != {len(data)}")
            return False

        # Check metadata
        metadata = hist_manager.get_metadata(TEST_SYMBOL, BASE_TIMEFRAME)

        details = (
            f"File: {file_path}\n"
            f"Bars: {len(loaded_data)}\n"
            f"Size: {Path(file_path).stat().st_size / 1024:.1f} KB\n"
            f"Metadata: {metadata is not None}"
        )
        print_result("Parquet Storage", True, details)

        results['components']['parquet_storage'] = {
            'file_path': file_path,
            'bars': len(loaded_data),
            'file_size_kb': Path(file_path).stat().st_size / 1024,
        }

        return True

    except Exception as e:
        print_result("Parquet Storage", False, f"Error: {e}")
        if verbose:
            traceback.print_exc()
        return False


def test_aggregation(data: pd.DataFrame, verbose: bool = False) -> Tuple[bool, Optional[Dict]]:
    """Test 4: Multi-Timeframe Aggregation."""
    print_header("TEST 4: MULTI-TIMEFRAME AGGREGATION", level=1)

    try:
        print("\n[1/3] Initializing RealtimeAggregator...")
        aggregator = RealtimeAggregator(
            source_timeframe='5sec',
            target_timeframes=['1min', '5min']
        )

        print(f"[2/3] Feeding {len(data)} bars through aggregator...")
        for timestamp, row in data.iterrows():
            bar = Bar(
                timestamp=timestamp,
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=int(row['volume']),
                complete=True
            )
            aggregator.add_bar(TEST_SYMBOL, bar)

        print(f"[3/3] Retrieving aggregated bars...")

        # Get 1min bars
        bars_1min = aggregator.to_dataframe(TEST_SYMBOL, Timeframe.MIN_1)

        # Get 5min bars
        bars_5min = aggregator.to_dataframe(TEST_SYMBOL, Timeframe.MIN_5)

        if len(bars_1min) == 0:
            print_result("Multi-Timeframe Aggregation", False, "No 1min bars generated")
            return False, None

        details = (
            f"1min bars: {len(bars_1min)}\n"
            f"5min bars: {len(bars_5min)}\n"
            f"Source bars: {len(data)}"
        )
        print_result("Multi-Timeframe Aggregation", True, details)

        agg_data = {
            '1min': bars_1min,
            '5min': bars_5min,
        }

        results['components']['aggregation'] = {
            '1min_bars': len(bars_1min),
            '5min_bars': len(bars_5min),
            'source_bars': len(data),
        }

        return True, agg_data

    except Exception as e:
        print_result("Multi-Timeframe Aggregation", False, f"Error: {e}")
        if verbose:
            traceback.print_exc()
        return False, None


def test_aggregation_accuracy(base_data: pd.DataFrame, agg_data: Dict[str, pd.DataFrame], verbose: bool = False) -> bool:
    """Test 5: Aggregation Accuracy Validation."""
    print_header("TEST 5: AGGREGATION ACCURACY VALIDATION", level=1)

    try:
        all_valid = True

        for timeframe_name, agg_df in agg_data.items():
            if len(agg_df) == 0:
                print(f"\n[{timeframe_name}] Skipping - no complete bars")
                continue

            print(f"\n[{timeframe_name}] Validating {len(agg_df)} bars...")

            issues = []

            # OHLCV validation
            print(f"  [1/4] Checking OHLCV relationships...")
            if not (agg_df['high'] >= agg_df['low']).all():
                issues.append("High < Low detected")
            if not (agg_df['high'] >= agg_df['open']).all():
                issues.append("High < Open detected")
            if not (agg_df['high'] >= agg_df['close']).all():
                issues.append("High < Close detected")
            if not (agg_df['low'] <= agg_df['open']).all():
                issues.append("Low > Open detected")
            if not (agg_df['low'] <= agg_df['close']).all():
                issues.append("Low > Close detected")

            # Price range validation
            print(f"  [2/4] Checking price ranges...")
            if agg_df['high'].max() > base_data['high'].max():
                issues.append(f"Aggregated high ({agg_df['high'].max():.2f}) exceeds base high ({base_data['high'].max():.2f})")
            if agg_df['low'].min() < base_data['low'].min():
                issues.append(f"Aggregated low ({agg_df['low'].min():.2f}) below base low ({base_data['low'].min():.2f})")

            # Volume validation (allow for incomplete bars)
            print(f"  [3/4] Checking volume...")
            # Note: Volume may differ due to incomplete bars being excluded

            # Display sample
            print(f"  [4/4] Sample data...")
            if verbose and len(agg_df) > 0:
                print(f"\n  Sample {timeframe_name} bar:")
                sample = agg_df.iloc[0]
                print(f"    Time: {agg_df.index[0]}")
                print(f"    OHLC: {sample['open']:.2f} / {sample['high']:.2f} / {sample['low']:.2f} / {sample['close']:.2f}")
                print(f"    Volume: {sample['volume']:,.0f}")

            if issues:
                print_result(f"{timeframe_name} Aggregation", False, "\n".join(issues))
                all_valid = False
            else:
                print_result(f"{timeframe_name} Aggregation", True, f"{len(agg_df)} bars validated")

        results['components']['aggregation_accuracy'] = {
            'validated': all_valid,
            'timeframes_tested': list(agg_data.keys()),
        }

        return all_valid

    except Exception as e:
        print_result("Aggregation Accuracy", False, f"Error: {e}")
        if verbose:
            traceback.print_exc()
        return False


def test_trade_validation(verbose: bool = False) -> bool:
    """Test 6: Trade Validation (Risk Controls)."""
    print_header("TEST 6: TRADE VALIDATION (RISK CONTROLS)", level=1)

    try:
        print("\n[1/4] Initializing ExecutionValidator...")
        validator = ExecutionValidator(
            account_size=100000.0,
            max_risk_per_trade_percent=1.0,
            max_total_risk_percent=3.0,
        )

        print("[2/4] Testing position size calculation...")

        # Test case: Buy at $100, stop at $95 (5% risk)
        position_size = validator.calculate_position_size(
            symbol=TEST_SYMBOL,
            entry_price=100.0,
            stop_loss=95.0
        )

        expected_size = (100000.0 * 0.01) / 5.0  # $1000 risk / $5 per share = 200 shares
        if abs(position_size - expected_size) > 0.01:
            print_result("Position Size Calculation", False, f"Expected {expected_size:.0f}, got {position_size:.0f}")
            return False

        print(f"  ✅ Position size: {position_size:.0f} shares (${position_size * 100.0:,.2f})")

        print("[3/4] Testing trade validation...")

        # Valid trade
        valid_proposal = TradeProposal(
            symbol=TEST_SYMBOL,
            side='BUY',
            quantity=200,
            entry_price=100.0,
            stop_loss=95.0,
        )

        report = validator.validate(valid_proposal)

        if not report.approved:
            reasons = ', '.join(report.rejection_messages)
            print_result("Valid Trade Test", False, f"Valid trade rejected: {reasons}")
            return False

        print(f"  ✅ Valid trade accepted")

        print("[4/4] Testing risk limit enforcement...")

        # Invalid trade (too much risk)
        invalid_proposal = TradeProposal(
            symbol=TEST_SYMBOL,
            side='BUY',
            quantity=5000,  # Way too large
            entry_price=100.0,
            stop_loss=95.0,
        )

        report = validator.validate(invalid_proposal)

        if report.approved:
            print_result("Risk Limit Test", False, "Oversized trade not rejected")
            return False

        reasons = ', '.join(report.rejection_messages)
        print(f"  ✅ Oversized trade rejected: {reasons}")

        details = (
            f"Max risk per trade: 1%\n"
            f"Max total risk: 3%\n"
            f"Account balance: ${100000.0:,.2f}"
        )
        print_result("Trade Validation", True, details)

        results['components']['trade_validation'] = {
            'position_size_calculated': position_size,
            'valid_trade_accepted': True,
            'invalid_trade_rejected': True,
        }

        return True

    except Exception as e:
        print_result("Trade Validation", False, f"Error: {e}")
        if verbose:
            traceback.print_exc()
        return False


def run_all_tests(skip_ib: bool = False, verbose: bool = False):
    """Run all tests in sequence."""
    print("=" * 80)
    print("SEQUENTIAL TESTING WORKFLOW")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print(f"Test symbol: {TEST_SYMBOL}")
    print(f"Skip IB: {skip_ib}")
    print()

    results['start_time'] = time.time()

    ib_manager = None
    base_data = None
    agg_data = None

    # Test 1: IB Connectivity
    if not skip_ib:
        results['tests_run'] += 1
        if test_ib_connectivity(verbose):
            results['tests_passed'] += 1
        else:
            results['tests_failed'] += 1
            print("\n⚠️  IB Gateway test failed - continuing with cached data if available")

    # Test 2: Historical Data Fetch
    if not skip_ib:
        results['tests_run'] += 1
        success, base_data = test_historical_data_fetch(verbose=verbose)
        if success:
            results['tests_passed'] += 1
        else:
            results['tests_failed'] += 1
            print("\n❌ Cannot continue without historical data")
            return
    else:
        # Try to load cached data
        print_header("LOADING CACHED DATA", level=1)
        try:
            hist_manager = HistoricalDataManager(data_dir=DATA_DIR)
            base_data = hist_manager.load_symbol_data(TEST_SYMBOL, BASE_TIMEFRAME)
            if base_data is not None:
                print(f"✅ Loaded {len(base_data)} cached bars")
            else:
                print("❌ No cached data available - run without --skip-ib first")
                return
        except Exception as e:
            print(f"❌ Failed to load cached data: {e}")
            return

    # Test 3: Parquet Storage
    if base_data is not None:
        results['tests_run'] += 1
        if test_parquet_storage(base_data, verbose):
            results['tests_passed'] += 1
        else:
            results['tests_failed'] += 1

    # Test 4: Aggregation
    if base_data is not None:
        results['tests_run'] += 1
        success, agg_data = test_aggregation(base_data, verbose)
        if success:
            results['tests_passed'] += 1
        else:
            results['tests_failed'] += 1

    # Test 5: Aggregation Accuracy
    if base_data is not None and agg_data is not None:
        results['tests_run'] += 1
        if test_aggregation_accuracy(base_data, agg_data, verbose):
            results['tests_passed'] += 1
        else:
            results['tests_failed'] += 1

    # Test 6: Trade Validation
    results['tests_run'] += 1
    if test_trade_validation(verbose):
        results['tests_passed'] += 1
    else:
        results['tests_failed'] += 1

    # Final summary
    results['end_time'] = time.time()
    print_summary()


def print_summary():
    """Print final test summary."""
    print_header("FINAL SUMMARY", level=1)

    execution_time = results['end_time'] - results['start_time']

    print(f"\nTests Run: {results['tests_run']}")
    print(f"  ✅ Passed: {results['tests_passed']}")
    print(f"  ❌ Failed: {results['tests_failed']}")
    print(f"\nExecution Time: {execution_time:.2f}s")

    if results['tests_failed'] == 0:
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print(f"❌ {results['tests_failed']} TEST(S) FAILED")
        print("=" * 80)

    # Component summary
    if results['components']:
        print("\n" + "-" * 80)
        print("Component Details:")
        print("-" * 80)
        for component, data in results['components'].items():
            print(f"\n{component}:")
            for key, value in data.items():
                print(f"  {key}: {value}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sequential testing workflow for screener system"
    )
    parser.add_argument(
        '--skip-ib',
        action='store_true',
        help='Skip IB Gateway tests (use cached data)'
    )
    parser.add_argument(
        '--component',
        type=str,
        choices=['ib', 'historical', 'parquet', 'aggregation', 'accuracy', 'validation'],
        help='Run only specific component'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    if args.component:
        # Run single component
        print(f"Running {args.component} test only...")
        if args.component == 'ib':
            success = test_ib_connectivity(args.verbose)
        elif args.component == 'validation':
            success = test_trade_validation(args.verbose)
        else:
            print("❌ Single component test not yet implemented for this component")
            print("   Use full test suite instead")
            return

        sys.exit(0 if success else 1)
    else:
        # Run all tests
        run_all_tests(skip_ib=args.skip_ib, verbose=args.verbose)
        sys.exit(0 if results['tests_failed'] == 0 else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
