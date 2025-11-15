# IB Gateway API Setup Notes

**Date**: 2025-11-15
**Status**: API port not enabled in running Gateway

---

## Current Situation

### Gateway Status
- ✅ IB Gateway/TWS is installed at `~/Jts`
- ✅ Process is running (PID 23177)
- ❌ API port 4002 is **NOT listening**
- ❌ API is **NOT enabled** in Gateway settings

### Test Results
```bash
$ python scripts/test_ib_connection.py
❌ FAILED: Connection refused
   Is IB Gateway running on port 4002?
```

---

## How to Enable IB Gateway API

### Option 1: Using IB Gateway GUI (Recommended for Paper Trading)

1. **Stop current Gateway** (if running):
   ```bash
   pkill -f "ibgateway.*total.*jar"
   ```

2. **Launch IB Gateway**:
   ```bash
   cd ~/Jts
   ./ibgateway
   ```

3. **Login** with paper trading credentials

4. **Enable API** in settings:
   - Go to: **File → Global Configuration → API → Settings**
   - ✅ Check: **Enable ActiveX and Socket Clients**
   - ✅ Check: **Allow connections from localhost only** (for security)
   - Set **Socket port**: `4002` (paper) or `4001` (live)
   - ✅ Check: **Read-Only API** (recommended for initial testing)
   - Click **OK**

5. **Verify API is enabled**:
   ```bash
   # Should show port 4002 listening
   netstat -tuln | grep 4002
   # Or
   ss -tuln | grep 4002
   ```

6. **Test connection**:
   ```bash
   cd /home/aaron/github/astoreyai/screener
   source venv/bin/activate
   python scripts/test_ib_connection.py
   ```

### Option 2: Using IBC Automation (Production/Headless)

IBC (Interactive Brokers Controller) automates Gateway startup and API enabling.

1. **Install IBC**:
   ```bash
   cd ~
   wget https://github.com/IbcAlpha/IBC/releases/download/3.17.0/IBCLinux-3.17.0.zip
   unzip IBCLinux-3.17.0.zip -d ~/ibc
   chmod +x ~/ibc/scripts/*.sh
   ```

2. **Create IBC config**:
   ```bash
   mkdir -p ~/.ibgateway/ibc
   cp ~/ibc/config.ini.sample ~/.ibgateway/ibc/config.ini.template
   ```

3. **Edit config** (`~/.ibgateway/ibc/config.ini.template`):
   ```ini
   # Login credentials (DO NOT commit)
   IbLoginId=your_username
   IbPassword=your_password
   TradingMode=paper

   # API settings
   AcceptIncomingConnectionAction=accept
   IbDir=/home/aaron/Jts
   IbcPath=/home/aaron/ibc
   LogToConsole=yes

   # Ports
   ApiPortNumber=4002
   ```

4. **Create credential loader**:
   ```bash
   mkdir -p ~/.ibgateway/secrets
   echo 'your_username' > ~/.ibgateway/secrets/paper_username
   echo 'your_password' > ~/.ibgateway/secrets/paper_password
   chmod 600 ~/.ibgateway/secrets/*
   ```

5. **Use screener's startup script**:
   ```bash
   cd /home/aaron/github/astoreyai/screener
   ./scripts/start_ib_gateway.sh paper
   ```

---

## Testing After API is Enabled

### Quick Test
```bash
cd /home/aaron/github/astoreyai/screener
source venv/bin/activate

# Test connection
python scripts/test_ib_connection.py
```

Expected output:
```
✅ Connected successfully!
   Server version: 176
✅ Account summary retrieved
   Net Liquidation: $1,000,000.00
✅ Contract qualified: AAPL on NASDAQ
   Price: $XXX.XX

Total: 3/3 tests passed
```

### Run Integration Tests
```bash
# Run all integration tests
pytest tests/test_ib_manager_comprehensive.py -v -m integration

# Expected: 16/16 integration tests passing
```

### Run Full Test Suite with Coverage
```bash
# Run all tests (unit + integration)
pytest tests/test_ib_manager_comprehensive.py -v \
    --cov=src.data.ib_manager \
    --cov-report=term-missing

# Expected: 28/28 tests passing, >80% coverage
```

---

## Current Test Status (Without API Enabled)

### Unit Tests: ✅ 12/12 passing
```bash
pytest tests/test_ib_manager_comprehensive.py -v -m "not integration"
```

These tests don't require IB Gateway API:
- ✅ Initialization tests
- ✅ State management tests
- ✅ Error handling tests
- ✅ Rate limiting tests
- ✅ Thread safety tests

### Integration Tests: ⏸️ 16 tests (require API)
These tests require IB Gateway API enabled:
- ⏸️ Connection tests (actual IB connection)
- ⏸️ Heartbeat tests (real heartbeat thread)
- ⏸️ Metrics tests (connection metrics)
- ⏸️ Cleanup tests (resource cleanup)
- ⏸️ Context manager tests
- ⏸️ Performance benchmarks

---

## Alternative: Mock Testing

For CI/CD or testing without IB Gateway, use mocks:

```python
from unittest.mock import Mock, patch

@patch('src.data.ib_manager.IB')
def test_with_mock(mock_ib):
    mock_instance = Mock()
    mock_instance.isConnected.return_value = True
    mock_ib.return_value = mock_instance

    manager = IBDataManager()
    assert manager.connect()
```

---

## Security Notes

### Paper Trading (Port 4002)
- ✅ Safe for development/testing
- ✅ No real money at risk
- ✅ Can enable Read-Only API for extra safety

### Live Trading (Port 4001)
- ⚠️ **USE WITH EXTREME CAUTION**
- 🚨 Real money at risk
- 🚨 Enable **Read-Only API** unless executing trades
- 🚨 Start with **small position sizes**
- 🚨 Monitor first 10 trades closely
- 🚨 Have **circuit breakers** ready

### API Security
- ✅ Always use "Allow connections from localhost only"
- ✅ Never expose IB Gateway API to public internet
- ✅ Use firewall rules if needed:
  ```bash
  sudo ufw allow from 127.0.0.1 to any port 4002 proto tcp
  sudo ufw deny 4002/tcp
  ```

---

## Troubleshooting

### "Connection Refused"
1. Check Gateway is running: `pgrep -f ibgateway`
2. Check API port: `netstat -tuln | grep 4002`
3. Check API enabled in Gateway GUI
4. Check firewall: `sudo ufw status`

### "API connection failed"
1. Verify correct port (4002 paper, 4001 live)
2. Restart Gateway
3. Check Gateway logs: `tail -f ~/Jts/launcher.log`

### "Read-Only API" blocking trades
1. Disable Read-Only in Gateway settings (⚠️ careful!)
2. Or use separate Gateway instance for execution

---

## Next Steps

1. **Enable IB Gateway API** using Option 1 or Option 2 above
2. **Verify connection** with test script
3. **Run integration tests** (should get >80% coverage)
4. **Proceed to Phase 1d** (historical data fetching)

---

**For Aaron**: Choose Option 1 (GUI) for quick setup, or Option 2 (IBC) for production headless setup.
