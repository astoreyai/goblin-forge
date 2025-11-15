#!/usr/bin/env python3
"""
Test IB Gateway connection for Screener Trading System.

Usage:
    python scripts/test_ib_connection.py

This script:
1. Attempts to connect to IB Gateway on port 4002
2. Validates connection and account access
3. Tests basic market data retrieval
4. Reports connection status

Requires:
- IB Gateway running (start with: ./scripts/start_ib_gateway.sh paper)
- ib_insync installed (pip install ib_insync)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from ib_insync import IB, Stock
except ImportError as exc:
    raise SystemExit(
        "Missing dependency 'ib_insync'. Install with: pip install ib_insync"
    ) from exc


def test_connection(host: str = "127.0.0.1", port: int = 4002, client_id: int = 999) -> bool:
    """Test basic IB Gateway connection."""
    print(f"\n{'='*70}")
    print(f"SCREENER - IB GATEWAY CONNECTION TEST")
    print(f"{'='*70}\n")
    print(f"Connection Parameters:")
    print(f"  Host:      {host}")
    print(f"  Port:      {port} (IB Gateway Paper Trading)")
    print(f"  Client ID: {client_id}")
    print(f"\n{'='*70}\n")

    ib = None
    try:
        print("⏳ Connecting to IB Gateway...")
        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=20)

        if not ib.isConnected():
            print("❌ FAILED: Connection not established")
            return False

        print(f"✅ Connected successfully!")
        print(f"   Server version: {ib.client.serverVersion()}")

        # Try to get connection time
        try:
            conn_time = ib.client.connTime()
            print(f"   Connection time: {conn_time}")
        except (AttributeError, Exception):
            print(f"   Connection time: (not available)")

        return True

    except ConnectionRefusedError:
        print("❌ FAILED: Connection refused")
        print("   Is IB Gateway running on port 4002?")
        print("   Start with: ./scripts/start_ib_gateway.sh paper")
        return False

    except TimeoutError:
        print("❌ FAILED: Connection timeout")
        print("   IB Gateway may be starting up - try again in 30 seconds")
        return False

    except Exception as exc:
        print(f"❌ FAILED: {type(exc).__name__}: {exc}")
        return False

    finally:
        if ib and ib.isConnected():
            ib.disconnect()
            print("\n🔌 Disconnected from gateway")
            time.sleep(1)


def test_account_info(host: str = "127.0.0.1", port: int = 4002, client_id: int = 998) -> bool:
    """Test account information retrieval."""
    print(f"\n{'='*70}")
    print(f"ACCOUNT INFORMATION TEST")
    print(f"{'='*70}\n")

    ib = None
    try:
        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=20)

        if not ib.isConnected():
            print("❌ FAILED: Not connected")
            return False

        print("⏳ Requesting account summary...")
        time.sleep(1)  # Brief delay for connection to stabilize

        # Request account summary
        summary = ib.accountSummary()

        if not summary:
            print("⚠️  WARNING: No account summary returned")
            print("   This may be normal if gateway just started")
            return False

        print(f"✅ Account summary retrieved ({len(summary)} items)")

        # Find NetLiquidation value
        net_liq = None
        for item in summary:
            if item.tag == "NetLiquidation":
                net_liq = item.value
                break

        if net_liq:
            print(f"\n   Net Liquidation: ${float(net_liq):,.2f}")
        else:
            print(f"\n   ⚠️  NetLiquidation not found")
            print(f"   Available tags: {', '.join(set(item.tag for item in summary[:5]))}")

        return True

    except Exception as exc:
        print(f"❌ FAILED: {type(exc).__name__}: {exc}")
        return False

    finally:
        if ib and ib.isConnected():
            ib.disconnect()
            print("\n🔌 Disconnected from gateway")
            time.sleep(1)


def test_market_data(host: str = "127.0.0.1", port: int = 4002, client_id: int = 997) -> bool:
    """Test market data retrieval for a sample stock."""
    print(f"\n{'='*70}")
    print(f"MARKET DATA TEST")
    print(f"{'='*70}\n")

    ib = None
    try:
        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=20)

        if not ib.isConnected():
            print("❌ FAILED: Not connected")
            return False

        # Test with AAPL (liquid stock, always available)
        test_symbol = "AAPL"
        contract = Stock(test_symbol, "SMART", "USD")

        print(f"⏳ Requesting market data for {test_symbol}...")

        # Qualify contract
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            print(f"❌ FAILED: Could not qualify {test_symbol} contract")
            return False

        contract = qualified[0]
        print(f"✅ Contract qualified: {contract.symbol} on {contract.primaryExchange}")

        # Request market data
        ticker = ib.reqMktData(contract)
        ib.sleep(2)  # Wait for data to arrive

        if ticker.last or ticker.close:
            price = ticker.last if ticker.last else ticker.close
            print(f"\n   Symbol: {test_symbol}")
            print(f"   Price:  ${price:.2f}")
            if ticker.bid:
                print(f"   Bid:    ${ticker.bid:.2f}")
            if ticker.ask:
                print(f"   Ask:    ${ticker.ask:.2f}")
            result = True
        else:
            print(f"⚠️  WARNING: No market data received for {test_symbol}")
            print("   This may occur outside market hours")
            result = False

        # Cancel market data subscription
        ib.cancelMktData(contract)

        return result

    except Exception as exc:
        print(f"❌ FAILED: {type(exc).__name__}: {exc}")
        return False

    finally:
        if ib and ib.isConnected():
            ib.disconnect()
            print("\n🔌 Disconnected from gateway")
            time.sleep(1)


def main():
    """Run all gateway tests."""
    print("\n" + "="*70)
    print("SCREENER TRADING SYSTEM - IB GATEWAY TEST SUITE")
    print("="*70)

    # Configuration
    HOST = "127.0.0.1"
    PORT = 4002  # IB Gateway Paper Trading via IBC

    # Run tests with unique client IDs to avoid conflicts
    results = {
        "Connection": test_connection(HOST, PORT, client_id=999),
        "Account Info": test_account_info(HOST, PORT, client_id=998),
        "Market Data": test_market_data(HOST, PORT, client_id=997),
    }

    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}\n")

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name:20s} {status}")

    total = len(results)
    passed = sum(results.values())

    print(f"\n  Total: {passed}/{total} tests passed")
    print(f"{'='*70}\n")

    if passed == total:
        print("✓ IB Gateway is ready for Screener Trading System!")
        print("  Next: Create src/data/ib_manager.py")
        print("")
        return 0
    else:
        print("✗ Some tests failed - check IB Gateway status")
        print("  Troubleshooting:")
        print("    1. Verify gateway is running: pgrep -f ibgateway")
        print("    2. Check port 4002: netstat -tuln | grep 4002")
        print("    3. View logs: tail ~/.ibgateway/logs/screener_ibgateway_paper_*.log")
        print("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
