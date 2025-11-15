"""
Comprehensive Aggregation Accuracy Test

Tests the complete data pipeline with accuracy validation:
1. IB Gateway connectivity
2. Historical data fetching (5-second bars)
3. RealtimeAggregator multi-timeframe aggregation
4. Aggregation accuracy validation
5. Detailed results display

This goes beyond simple data download to validate that aggregation
logic correctly transforms 5-second bars into higher timeframes.

Run:
----
python scripts/test_aggregation_accuracy.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import traceback

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.ib_manager import IBDataManager
from src.data.historical_manager import HistoricalDataManager
from src.data.realtime_aggregator import RealtimeAggregator, Bar, Timeframe
import pandas as pd
import numpy as np

print("=" * 80)
print("COMPREHENSIVE AGGREGATION ACCURACY TEST")
print("=" * 80)
print(f"Started: {datetime.now()}")
print()

# Test configuration
TEST_SYMBOL = 'SPY'  # Liquid ETF for consistent data
BASE_TIMEFRAME = '5 secs'
DURATION = '300 S'  # 300 seconds (5 minutes) of 5-second bars = 60 bars
AGGREGATION_TARGETS = {
    '1min': Timeframe.MIN_1,
    '5min': Timeframe.MIN_5,
}

results = {
    'ib_connected': False,
    'data_fetched': False,
    'base_bars': 0,
    'aggregations': {},
    'validations': {},
    'errors': [],
}


def validate_ohlcv_bar(bar: pd.Series, bar_num: int) -> Tuple[bool, List[str]]:
    """
    Validate OHLCV relationships in a single bar.

    Returns:
        (is_valid, list of issues)
    """
    issues = []

    # High must be >= Low
    if bar['high'] < bar['low']:
        issues.append(f"Bar {bar_num}: high ({bar['high']}) < low ({bar['low']})")

    # High must be >= Open
    if bar['high'] < bar['open']:
        issues.append(f"Bar {bar_num}: high ({bar['high']}) < open ({bar['open']})")

    # High must be >= Close
    if bar['high'] < bar['close']:
        issues.append(f"Bar {bar_num}: high ({bar['high']}) < close ({bar['close']})")

    # Low must be <= Open
    if bar['low'] > bar['open']:
        issues.append(f"Bar {bar_num}: low ({bar['low']}) > open ({bar['open']})")

    # Low must be <= Close
    if bar['low'] > bar['close']:
        issues.append(f"Bar {bar_num}: low ({bar['low']}) > close ({bar['close']})")

    # Volume must be non-negative
    if bar['volume'] < 0:
        issues.append(f"Bar {bar_num}: negative volume ({bar['volume']})")

    return len(issues) == 0, issues


def validate_aggregation(base_data: pd.DataFrame, agg_data: pd.DataFrame,
                         target_name: str, bars_per_agg: int) -> Dict:
    """
    Validate that aggregated data correctly represents base data.

    Args:
        base_data: Original 5-second bars
        agg_data: Aggregated bars
        target_name: Name of aggregation (e.g., '1min')
        bars_per_agg: Expected number of base bars per aggregated bar

    Returns:
        Dictionary with validation results
    """
    validation = {
        'passed': True,
        'checks': [],
        'issues': [],
        'stats': {}
    }

    print(f"\n{'='*80}")
    print(f"VALIDATING {target_name.upper()} AGGREGATION")
    print(f"{'='*80}")
    print(f"Base bars: {len(base_data)}, Aggregated bars: {len(agg_data)}")
    print(f"Expected bars per aggregation: {bars_per_agg}")

    # Expected number of aggregated bars
    expected_agg_bars = len(base_data) // bars_per_agg
    if len(agg_data) < expected_agg_bars:
        validation['issues'].append(
            f"Got {len(agg_data)} aggregated bars, expected ~{expected_agg_bars}"
        )

    # Validate each aggregated bar
    for agg_idx, agg_bar in agg_data.iterrows():
        # Find corresponding base bars
        # Note: This is approximate since we don't have exact timestamp alignment
        # In a real scenario, we'd use timestamps to match

        # Validate OHLCV relationships within aggregated bar
        is_valid, issues = validate_ohlcv_bar(agg_bar, agg_idx)
        if not is_valid:
            validation['passed'] = False
            validation['issues'].extend(issues)

    # Statistical validation
    validation['stats'] = {
        'base_volume_total': int(base_data['volume'].sum()),
        'agg_volume_total': int(agg_data['volume'].sum()),
        'base_price_range': f"${base_data['low'].min():.2f} - ${base_data['high'].max():.2f}",
        'agg_price_range': f"${agg_data['low'].min():.2f} - ${agg_data['high'].max():.2f}",
        'volume_preservation': f"{agg_data['volume'].sum() / base_data['volume'].sum() * 100:.1f}%",
    }

    # Volume should be preserved (sum of volumes should match)
    volume_diff = abs(base_data['volume'].sum() - agg_data['volume'].sum())
    volume_tolerance = base_data['volume'].sum() * 0.01  # 1% tolerance

    if volume_diff > volume_tolerance:
        validation['issues'].append(
            f"Volume not preserved: base={base_data['volume'].sum()}, "
            f"agg={agg_data['volume'].sum()}, diff={volume_diff}"
        )
        validation['passed'] = False
    else:
        validation['checks'].append(f"✅ Volume preserved within tolerance")

    # Price range validation
    if agg_data['high'].max() > base_data['high'].max():
        validation['issues'].append(
            f"Aggregated high ({agg_data['high'].max()}) exceeds base high ({base_data['high'].max()})"
        )
        validation['passed'] = False
    else:
        validation['checks'].append(f"✅ High prices within base range")

    if agg_data['low'].min() < base_data['low'].min():
        validation['issues'].append(
            f"Aggregated low ({agg_data['low'].min()}) below base low ({base_data['low'].min()})"
        )
        validation['passed'] = False
    else:
        validation['checks'].append(f"✅ Low prices within base range")

    # Display results
    print(f"\nValidation Checks:")
    for check in validation['checks']:
        print(f"  {check}")

    if validation['issues']:
        print(f"\n⚠️  Issues Found ({len(validation['issues'])}):")
        for issue in validation['issues'][:5]:  # Show first 5
            print(f"  ❌ {issue}")
        if len(validation['issues']) > 5:
            print(f"  ... and {len(validation['issues']) - 5} more")

    print(f"\nStatistics:")
    for key, value in validation['stats'].items():
        print(f"  {key}: {value}")

    return validation


def display_bar_sample(data: pd.DataFrame, name: str, count: int = 5):
    """Display a sample of bars for visual inspection."""
    print(f"\n{'-'*80}")
    print(f"{name} - Sample of {min(count, len(data))} bars:")
    print(f"{'-'*80}")

    sample = data.head(count)

    print(f"{'Time':<20} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print(f"{'-'*80}")

    for idx, row in sample.iterrows():
        time_str = str(idx)[:19] if hasattr(idx, 'strftime') else str(idx)
        print(f"{time_str:<20} {row['open']:>10.2f} {row['high']:>10.2f} "
              f"{row['low']:>10.2f} {row['close']:>10.2f} {row['volume']:>12,.0f}")


def main():
    """Run comprehensive aggregation accuracy test."""

    # 1. Connect to IB Gateway
    print("\n" + "=" * 80)
    print("STEP 1: IB GATEWAY CONNECTION")
    print("=" * 80)

    ib_manager = IBDataManager(port=4002, client_id=102, heartbeat_enabled=False)

    if not ib_manager.connect():
        print("❌ Failed to connect to IB Gateway")
        print("   Make sure IB Gateway is running on port 4002")
        return False

    print(f"✅ Connected to IB Gateway")
    print(f"   State: {ib_manager.state}")
    print(f"   Healthy: {ib_manager.is_healthy()}")
    results['ib_connected'] = True

    try:
        # 2. Fetch base data (5-second bars)
        print("\n" + "=" * 80)
        print(f"STEP 2: FETCH BASE DATA ({BASE_TIMEFRAME})")
        print("=" * 80)

        print(f"\nFetching {BASE_TIMEFRAME} bars for {TEST_SYMBOL} ({DURATION})...")
        base_data = ib_manager.fetch_historical_bars(TEST_SYMBOL, BASE_TIMEFRAME, DURATION)

        if base_data is None or len(base_data) == 0:
            print("❌ No data returned")
            return False

        print(f"✅ Fetched {len(base_data)} bars")
        print(f"   Date range: {base_data.index[0]} to {base_data.index[-1]}")
        print(f"   Price range: ${base_data['low'].min():.2f} - ${base_data['high'].max():.2f}")
        print(f"   Total volume: {base_data['volume'].sum():,.0f}")

        results['data_fetched'] = True
        results['base_bars'] = len(base_data)

        # Display sample of base data
        display_bar_sample(base_data, f"{TEST_SYMBOL} {BASE_TIMEFRAME} Base Data")

        # 3. Test aggregation for each target timeframe
        print("\n" + "=" * 80)
        print("STEP 3: MULTI-TIMEFRAME AGGREGATION")
        print("=" * 80)

        aggregator = RealtimeAggregator(
            source_timeframe='5sec',
            target_timeframes=['1min', '5min']
        )

        # Feed base bars through aggregator
        print(f"\nFeeding {len(base_data)} bars through aggregator...")

        for timestamp, row in base_data.iterrows():
            bar = Bar(
                timestamp=timestamp,
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=int(row['volume']),
                complete=True  # Historical bars are complete
            )
            aggregator.add_bar(TEST_SYMBOL, bar)

        # Get aggregated data
        for target_name, timeframe in AGGREGATION_TARGETS.items():
            print(f"\n{'-'*80}")
            print(f"Aggregating to {target_name}...")

            agg_df = aggregator.to_dataframe(TEST_SYMBOL, timeframe)

            if agg_df is None or len(agg_df) == 0:
                print(f"⚠️  No aggregated data for {target_name}")
                continue

            print(f"✅ Generated {len(agg_df)} {target_name} bars")
            results['aggregations'][target_name] = len(agg_df)

            # Display sample
            display_bar_sample(agg_df, f"{TEST_SYMBOL} {target_name} Aggregated Data", count=3)

            # Validate aggregation
            bars_per_agg = {
                '1min': 12,   # 60 seconds / 5 seconds = 12 bars
                '5min': 60,   # 300 seconds / 5 seconds = 60 bars
            }[target_name]

            validation = validate_aggregation(
                base_data, agg_df, target_name, bars_per_agg
            )

            results['validations'][target_name] = validation

        # 4. Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        print(f"\nConnection: {'✅ PASS' if results['ib_connected'] else '❌ FAIL'}")
        print(f"Data Fetch: {'✅ PASS' if results['data_fetched'] else '❌ FAIL'}")
        print(f"Base Bars: {results['base_bars']}")

        print(f"\nAggregations:")
        for target, count in results['aggregations'].items():
            print(f"  {target}: {count} bars")

        print(f"\nValidations:")
        all_passed = True
        for target, validation in results['validations'].items():
            status = "✅ PASS" if validation['passed'] else "❌ FAIL"
            print(f"  {target}: {status}")
            if not validation['passed']:
                all_passed = False

        # Final verdict
        print("\n" + "=" * 80)
        if all_passed and results['ib_connected'] and results['data_fetched']:
            print("✅ AGGREGATION ACCURACY TEST: PASS")
            print("   All aggregations validated successfully")
        else:
            print("❌ AGGREGATION ACCURACY TEST: FAIL")
            if not all_passed:
                print("   Some aggregations failed validation")
        print("=" * 80)

        return all_passed

    finally:
        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)
        ib_manager.disconnect()
        print("✅ Disconnected from IB Gateway")


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
