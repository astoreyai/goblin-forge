#!/usr/bin/env bash
# Launch IB Gateway for Screener Trading System
# Adapted from /home/aaron/projects/stoch/scripts/start_ib_gateway.sh
# Uses IBC automation for paper trading

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

TRADING_MODE="${1:-paper}"  # paper or live
IBC_PATH="${IBC_PATH:-${HOME}/ibc}"
IBG_PATH="${IBG_PATH:-${HOME}/Jts}"
IBC_CONFIG_DIR="${HOME}/.ibgateway/ibc"
LOG_DIR="${HOME}/.ibgateway/logs"

# Ports for connection testing
PAPER_PORT=4002
LIVE_PORT=4001

# ============================================================================
# VALIDATION
# ============================================================================

if [[ "$TRADING_MODE" != "paper" && "$TRADING_MODE" != "live" ]]; then
    echo "ERROR: Trading mode must be 'paper' or 'live'" >&2
    echo "Usage: $0 [paper|live]" >&2
    exit 1
fi

if [[ ! -d "$IBC_PATH" ]]; then
    echo "ERROR: IBC not found at $IBC_PATH" >&2
    echo "Install from: https://github.com/IbcAlpha/IBC/releases" >&2
    exit 1
fi

if [[ ! -d "$IBG_PATH" ]]; then
    echo "ERROR: IB Gateway installation not found at $IBG_PATH" >&2
    exit 1
fi

if [[ ! -f "$IBC_CONFIG_DIR/config.ini.template" ]]; then
    echo "ERROR: IBC config template not found" >&2
    echo "Create: $IBC_CONFIG_DIR/config.ini.template" >&2
    exit 1
fi

# ============================================================================
# SETUP
# ============================================================================

mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/screener_ibgateway_${TRADING_MODE}_${TIMESTAMP}.log"

echo "==============================================="
echo "IB Gateway Startup - Screener Trading System"
echo "==============================================="
echo "Trading Mode:  $TRADING_MODE"
echo "IBC Path:      $IBC_PATH"
echo "Gateway Path:  $IBG_PATH"
echo "Log File:      $LOG_FILE"
echo "==============================================="

# ============================================================================
# CREDENTIAL LOADING
# ============================================================================

echo "[1/5] Loading credentials..."
if [[ -x "${HOME}/.ibgateway/load_credentials.sh" ]]; then
    if ! "${HOME}/.ibgateway/load_credentials.sh"; then
        echo "ERROR: Failed to load credentials" >&2
        echo "Please set up credentials:" >&2
        echo "  echo 'your_username' > ~/.ibgateway/secrets/${TRADING_MODE}_username" >&2
        echo "  echo 'your_password' > ~/.ibgateway/secrets/${TRADING_MODE}_password" >&2
        echo "  chmod 600 ~/.ibgateway/secrets/${TRADING_MODE}_*" >&2
        exit 1
    fi
else
    echo "WARNING: Credential loader not found at ${HOME}/.ibgateway/load_credentials.sh"
    echo "Using template as-is - you may be prompted for credentials"
fi

# ============================================================================
# CHECK FOR EXISTING PROCESS
# ============================================================================

echo "[2/5] Checking for existing gateway process..."
if pgrep -f "ibgateway.*total.*jar" > /dev/null; then
    echo "WARNING: IB Gateway appears to be already running"
    echo "Port $PAPER_PORT may already be in use"
    echo ""
    echo "Options:"
    echo "  1. Use existing gateway (recommended)"
    echo "  2. Kill and restart gateway"
    echo ""
    read -p "Choose option (1 or 2): " -n 1 -r
    echo
    if [[ $REPLY == "2" ]]; then
        pkill -f "ibgateway.*total.*jar" || true
        sleep 3
        echo "Existing gateway killed"
    else
        echo "Using existing gateway - skipping launch"
        TARGET_PORT=$PAPER_PORT
        if [[ "$TRADING_MODE" == "live" ]]; then
            TARGET_PORT=$LIVE_PORT
        fi
        # Jump to validation
        goto validation
    fi
fi

# ============================================================================
# LAUNCH IB GATEWAY VIA IBC
# ============================================================================

echo "[3/5] Launching IB Gateway with IBC..."

# Launch in background using IBC's gateway start script
"${IBC_PATH}/scripts/ibcstart.sh" \
    "1037" \
    --gateway \
    --tws-path="$IBG_PATH" \
    --ibc-path="$IBC_PATH" \
    --ibc-ini="$IBC_CONFIG_DIR/config.ini" \
    --mode="$TRADING_MODE" \
    >> "$LOG_FILE" 2>&1 &

GATEWAY_PID=$!
echo "Gateway launching with script PID: $GATEWAY_PID"
echo "Check log for details: $LOG_FILE"

# ============================================================================
# WAIT FOR API PORT
# ============================================================================

validation:
echo "[4/5] Waiting for API socket to become available..."

if [[ "$TRADING_MODE" == "paper" ]]; then
    TARGET_PORT=$PAPER_PORT
else
    TARGET_PORT=$LIVE_PORT
fi

MAX_WAIT=120  # 2 minutes
ELAPSED=0

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    if netstat -tuln 2>/dev/null | grep -q ":${TARGET_PORT} " || \
       ss -tuln 2>/dev/null | grep -q ":${TARGET_PORT} "; then
        echo ""
        echo "✓ API socket listening on port $TARGET_PORT"
        break
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))

    # Show progress indicator
    if [[ $((ELAPSED % 10)) -eq 0 ]]; then
        echo "  ... still waiting (${ELAPSED}s elapsed)"
    fi
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo ""
    echo "ERROR: API socket did not become available within ${MAX_WAIT}s" >&2
    echo "Check log: $LOG_FILE" >&2
    echo ""
    echo "Common issues:" >&2
    echo "  - Wrong credentials" >&2
    echo "  - 2FA timeout" >&2
    echo "  - IB Gateway failed to start" >&2
    echo ""
    if [[ -f "$LOG_FILE" ]]; then
        echo "Tail of log file:" >&2
        tail -20 "$LOG_FILE" >&2
    fi
    exit 1
fi

# ============================================================================
# CONNECTION VALIDATION
# ============================================================================

echo "[5/5] Validating connection readiness..."

# Give gateway a moment to fully initialize
sleep 5

# Try to find the actual gateway PID (not the script PID)
ACTUAL_PID=$(pgrep -f "ibgateway.*total.*jar" || echo "unknown")
echo "Gateway Java process PID: $ACTUAL_PID"

# Run screener's test script if available
SCREENER_DIR="/home/aaron/github/astoreyai/screener"
if [[ -f "$SCREENER_DIR/scripts/test_ib_connection.py" && "$TRADING_MODE" == "paper" ]]; then
    echo ""
    echo "Running screener connection test..."

    cd "$SCREENER_DIR"
    # Activate venv if it exists
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    fi

    # Run test in background to avoid blocking if it hangs
    if timeout 30 python scripts/test_ib_connection.py; then
        TEST_RESULT=0
    else
        TEST_RESULT=$?
    fi

    if [[ $TEST_RESULT -eq 0 ]]; then
        echo ""
        echo "==============================================="
        echo "✓ IB Gateway READY for Screener"
        echo "==============================================="
        echo "Mode:     $TRADING_MODE"
        echo "Port:     $TARGET_PORT"
        echo "PID:      $ACTUAL_PID"
        echo "Log:      $LOG_FILE"
        echo "==============================================="
        echo ""
        echo "Gateway is ready for trading!"
        echo ""
    else
        echo ""
        echo "WARNING: Connection test failed (exit code: $TEST_RESULT)"
        echo "Gateway is running but may not be fully ready"
        echo "Check log: $LOG_FILE"
        echo ""
    fi
else
    echo "✓ Gateway appears ready (test script not yet created)"
    echo ""
    echo "==============================================="
    echo "Gateway Running - Screener Trading System"
    echo "==============================================="
    echo "Mode:     $TRADING_MODE"
    echo "Port:     $TARGET_PORT"
    echo "PID:      $ACTUAL_PID"
    echo "Log:      $LOG_FILE"
    echo "==============================================="
    echo ""
fi

echo "To stop gateway:  pkill -f 'ibgateway.*total.*jar'"
echo "To view logs:     tail -f $LOG_FILE"
echo ""
echo "Next: Create src/data/ib_manager.py to connect to port $TARGET_PORT"
echo ""
