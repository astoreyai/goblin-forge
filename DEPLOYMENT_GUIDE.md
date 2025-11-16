# Screener Trading System - Deployment Guide

**Version**: v0.5.0
**Last Updated**: 2025-11-16
**Status**: Production Ready

This guide provides comprehensive instructions for deploying the Screener trading system from installation through production operation.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [IB Gateway Setup](#ib-gateway-setup)
5. [Running the System](#running-the-system)
6. [Dashboard Access](#dashboard-access)
7. [Monitoring and Logs](#monitoring-and-logs)
8. [Database Management](#database-management)
9. [Production Checklist](#production-checklist)
10. [Troubleshooting](#troubleshooting)
11. [Maintenance](#maintenance)
12. [Security](#security)
13. [Performance Tuning](#performance-tuning)

---

## System Requirements

### Hardware Requirements

**Minimum**:
- CPU: 2 cores, 2.0 GHz
- RAM: 4 GB
- Disk: 10 GB free space
- Network: Stable broadband connection (10 Mbps+)

**Recommended**:
- CPU: 4+ cores, 3.0 GHz+
- RAM: 8 GB+
- Disk: 50 GB SSD
- Network: Stable broadband connection (50 Mbps+)

**Production**:
- CPU: 8+ cores, 3.5 GHz+
- RAM: 16 GB+
- Disk: 100 GB NVMe SSD
- Network: Redundant connection with failover
- UPS: Battery backup for graceful shutdown

### Software Requirements

**Operating System**:
- Linux (Ubuntu 20.04+, Debian 11+, or equivalent) - **Recommended**
- macOS 11+ (Big Sur or later)
- Windows 10/11 (with WSL2 recommended)

**Python**:
- Version: 3.11.2 or higher (tested on 3.11.2)
- Note: Python 3.9+ supported, but 3.11+ recommended for performance

**Interactive Brokers**:
- IB Gateway 10.19+ OR TWS 10.19+
- Paper trading account (recommended for initial deployment)
- API access enabled

**Database**:
- SQLite 3.x (development/small-scale)
- PostgreSQL 13+ (production recommended)

**Additional Software**:
- git 2.30+
- TA-Lib C library (for technical indicators)

---

## Installation

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/astoreyai/screener.git
cd screener

# Verify you're on main branch
git branch
# Should show: * main
```

### Step 2: Install TA-Lib C Library

TA-Lib is required for technical indicator calculations.

#### Ubuntu/Debian:
```bash
# Download and install TA-Lib
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
cd ..
rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
```

#### macOS (Homebrew):
```bash
brew install ta-lib
```

#### Windows:
```bash
# Download pre-built wheel from:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
# Then install with pip (see Step 4)
```

### Step 3: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows
```

**Important**: Always activate the virtual environment before running any commands.

### Step 4: Install Python Dependencies

```bash
# Ensure virtual environment is activated
# You should see (venv) in your prompt

# Upgrade pip
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "ib-insync|pandas|dash|plotly|TA-Lib"
```

**Expected Output**:
```
dash                      2.14.0
ib-insync                 0.9.86
pandas                    2.0.0
plotly                    5.17.0
TA-Lib                    0.4.28
```

### Step 5: Verify Installation

```bash
# Quick test of Python imports
python -c "import ib_insync; import pandas; import dash; import talib; print('All imports successful')"

# Should print: All imports successful
```

---

## Configuration

### Step 1: Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env file
nano .env  # or vim, or your preferred editor
```

**.env Configuration**:

```bash
# ===== Interactive Brokers Configuration =====
IB_HOST=127.0.0.1
IB_PORT=4002           # 4002 for paper trading, 7496 for live trading
IB_CLIENT_ID=1         # Unique client ID (1-32)

# ===== Database Configuration =====
# SQLite (Development/Small-Scale)
DATABASE_URL=sqlite:///data/screener.db

# PostgreSQL (Production - Recommended)
# DATABASE_URL=postgresql://user:password@localhost:5432/screener

# ===== Trading Parameters =====
ACCOUNT_BALANCE=100000.00     # Your starting account balance
MAX_RISK_PER_TRADE=0.01       # 1% max risk per trade (DO NOT CHANGE)
MAX_PORTFOLIO_RISK=0.03       # 3% max total portfolio risk (DO NOT CHANGE)
MAX_POSITIONS=10              # Maximum concurrent positions

# ===== Data Storage =====
DATA_DIR=./data               # Directory for Parquet files
LOG_DIR=./logs                # Directory for log files
BACKUP_DIR=./backups          # Directory for database backups

# ===== Dashboard Configuration =====
DASH_HOST=0.0.0.0            # 0.0.0.0 = accessible from network
DASH_PORT=8050               # Dashboard port
DASH_DEBUG=false             # Set to true for development only

# ===== Logging Configuration =====
LOG_LEVEL=INFO               # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_ROTATION=1 day           # Log rotation period
LOG_RETENTION=30 days        # Log retention period

# ===== Performance Tuning =====
CACHE_TTL=300                # Indicator cache TTL (seconds)
MAX_WORKERS=4                # Parallel processing workers
BATCH_SIZE=100               # Batch processing size

# ===== Alerts & Notifications (Optional) =====
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587
# EMAIL_FROM=your-email@example.com
# EMAIL_TO=trading-alerts@example.com
# EMAIL_PASSWORD=your-app-password
```

**Security Notes**:
- ⚠️ NEVER commit `.env` file to git
- ⚠️ Keep `.env` permissions restricted: `chmod 600 .env`
- ⚠️ Use strong passwords for database if using PostgreSQL
- ⚠️ Start with paper trading account (IB_PORT=4002)

### Step 2: Trading Parameters

Edit `config/trading_params.yaml`:

```bash
nano config/trading_params.yaml
```

**config/trading_params.yaml**:

```yaml
# Screener Trading System - Trading Parameters
# Last Updated: 2025-11-16

risk_management:
  # CRITICAL: DO NOT CHANGE THESE VALUES WITHOUT THOROUGH TESTING
  max_risk_per_trade: 0.01      # 1% maximum risk per trade
  max_portfolio_risk: 0.03      # 3% maximum total portfolio risk
  max_positions: 10             # Maximum concurrent positions

  # Position sizing
  min_position_size: 100        # Minimum shares per position
  max_position_size: 10000      # Maximum shares per position
  position_size_increment: 1    # Position size must be multiple of this

  # Stop loss
  min_stop_distance: 0.005      # Minimum stop distance (0.5%)
  max_stop_distance: 0.10       # Maximum stop distance (10%)
  trailing_stop_distance: 0.02  # Trailing stop distance (2%)
  trailing_stop_interval: 60    # Trailing stop check interval (seconds)

execution:
  # Order types
  order_type: MKT               # Market order (MKT) or Limit (LMT)

  # Timeouts
  order_timeout: 60             # Order fill timeout (seconds)
  connection_timeout: 30        # IB connection timeout (seconds)

  # Retry logic
  max_retries: 3                # Maximum retry attempts
  retry_delay: 5                # Delay between retries (seconds)

screening:
  # Universe parameters
  min_price: 5.0                # Minimum stock price
  max_price: 1000.0             # Maximum stock price
  min_volume: 1000000           # Minimum daily volume (shares)
  min_market_cap: 100000000     # Minimum market cap ($100M)

  # Coarse filter thresholds
  bb_position_range: [0.0, 0.3] # Bollinger Band position (lower 30%)
  min_trend_strength: 0.02      # Minimum trend strength (2%)
  min_volume_ratio: 1.2         # Minimum volume vs average (20% above)
  volatility_range: [0.01, 0.10] # ATR/price ratio range (1-10%)

  # SABR20 scoring
  min_sabr20_score: 60          # Minimum SABR20 score for watchlist
  max_watchlist_size: 20        # Maximum symbols in watchlist

data:
  # Historical data
  lookback_days: 90             # Days of historical data to fetch
  bar_size: 15 mins             # Primary bar size for analysis

  # Update frequencies
  universe_update_frequency: daily    # daily, weekly, monthly
  watchlist_update_frequency: hourly  # hourly, 4hour, daily

  # Data quality
  min_bars_required: 50         # Minimum bars required for analysis
  max_missing_bars: 5           # Maximum tolerable missing bars

dashboard:
  # Update intervals (milliseconds)
  positions_update_interval: 5000     # Update positions every 5s
  watchlist_update_interval: 60000    # Update watchlist every 60s
  charts_update_interval: 30000       # Update charts every 30s

  # Display preferences
  chart_bars_display: 200       # Number of bars to display in charts
  default_timeframe: 15min      # Default chart timeframe
  theme: kymera                 # Dashboard theme (kymera, dark, light)

schedule:
  # Market hours (US Eastern Time)
  market_open: "09:30"
  market_close: "16:00"
  premarket_start: "04:00"
  aftermarket_end: "20:00"

  # Automated tasks
  universe_update_time: "00:00"       # Daily universe update
  watchlist_update_time: "09:00"      # Pre-market watchlist update
  database_backup_time: "23:00"       # Daily database backup
```

### Step 3: System Configuration

Edit `config/system_config.yaml`:

```bash
nano config/system_config.yaml
```

**config/system_config.yaml**:

```yaml
# Screener Trading System - System Configuration
# Last Updated: 2025-11-16

logging:
  version: 1
  disable_existing_loggers: false

  formatters:
    standard:
      format: "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    detailed:
      format: "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process}:{thread} | {name}:{function}:{line} - {message}"

  handlers:
    console:
      class: logging.StreamHandler
      level: INFO
      formatter: standard
      stream: ext://sys.stdout

    file:
      class: logging.handlers.RotatingFileHandler
      level: DEBUG
      formatter: detailed
      filename: logs/screener.log
      maxBytes: 10485760  # 10MB
      backupCount: 30

    error_file:
      class: logging.handlers.RotatingFileHandler
      level: ERROR
      formatter: detailed
      filename: logs/errors.log
      maxBytes: 10485760  # 10MB
      backupCount: 90

  root:
    level: DEBUG
    handlers: [console, file, error_file]

cache:
  # Indicator cache configuration
  enabled: true
  backend: memory        # memory, redis (future)
  ttl: 300              # Cache TTL in seconds (5 minutes)
  max_size: 1000        # Maximum cached items

  # Cache keys
  indicator_cache: true
  sabr20_cache: true
  quote_cache: true

performance:
  # Multi-processing
  enable_multiprocessing: false  # Set to true for >1000 symbols
  max_workers: 4                 # CPU cores to use

  # Memory management
  max_memory_mb: 2048            # Maximum memory usage (2GB)
  gc_interval: 300               # Garbage collection interval (seconds)

  # Connection pooling
  db_pool_size: 5                # Database connection pool size
  db_max_overflow: 10            # Maximum overflow connections

monitoring:
  # Health checks
  enable_health_checks: true
  health_check_interval: 60      # Seconds

  # Metrics
  enable_metrics: true
  metrics_port: 9090            # Prometheus metrics port (if enabled)

  # Alerts
  enable_alerts: false          # Set to true for production
  alert_on_errors: true
  alert_on_disconnection: true
  alert_on_risk_breach: true

development:
  # Debug settings (DISABLE IN PRODUCTION)
  debug_mode: false
  profiling_enabled: false
  mock_ib_connection: false
  use_sample_data: false
```

### Step 4: Create Directories

```bash
# Create required directories
mkdir -p data logs backups config

# Set permissions
chmod 755 data logs backups
chmod 700 config  # Restrict config directory
chmod 600 .env    # Restrict .env file

# Verify directory structure
ls -la
```

---

## IB Gateway Setup

### Step 1: Download IB Gateway

**Option A: IB Gateway (Recommended)**
- Download from: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- Lighter weight than TWS
- Better for automated trading
- Runs headless (no GUI after login)

**Option B: Trader Workstation (TWS)**
- Download from: https://www.interactivebrokers.com/en/trading/tws.php
- Full trading platform
- More features and controls
- Includes GUI for manual trading

### Step 2: Install IB Gateway

#### Linux:
```bash
# Make installer executable
chmod +x ibgateway-latest-standalone-linux-x64.sh

# Run installer
./ibgateway-latest-standalone-linux-x64.sh

# Follow installation wizard
# Default installation: /home/username/Jts
```

#### macOS:
```bash
# Open DMG file
open ibgateway-latest-standalone-macosx-x64.dmg

# Drag IB Gateway to Applications
# Run IB Gateway from Applications folder
```

#### Windows:
```bash
# Run installer
ibgateway-latest-standalone-windows-x64.exe

# Follow installation wizard
# Default installation: C:\Jts
```

### Step 3: Configure IB Gateway

1. **Launch IB Gateway**
   ```bash
   # Linux
   ~/Jts/ibgateway/10.19/ibgateway &

   # macOS
   open -a "IB Gateway"

   # Windows
   # Use Start Menu shortcut
   ```

2. **Login**
   - Username: Your IB account username
   - Password: Your IB account password
   - Trading Mode: **Paper Trading** (for initial deployment)

3. **Enable API Access**
   - Click **Configure** → **Settings** → **API** → **Settings**
   - Check **Enable ActiveX and Socket Clients**
   - **Read-Only API**: Unchecked (we need to place orders)
   - **Master API client ID**: Leave at 0
   - **Socket port**:
     - Paper Trading: **4002**
     - Live Trading: **7496**
   - **Trusted IP addresses**: Add `127.0.0.1`
   - Click **OK**

4. **Configure Auto-Restart (Linux)**

   Create systemd service file:
   ```bash
   sudo nano /etc/systemd/system/ibgateway.service
   ```

   Add:
   ```ini
   [Unit]
   Description=IB Gateway
   After=network.target

   [Service]
   Type=simple
   User=your-username
   Environment=DISPLAY=:0
   WorkingDirectory=/home/your-username/Jts/ibgateway/10.19
   ExecStart=/home/your-username/Jts/ibgateway/10.19/ibgateway
   Restart=on-failure
   RestartSec=30

   [Install]
   WantedBy=multi-user.target
   ```

   Enable service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ibgateway
   sudo systemctl start ibgateway
   ```

### Step 4: Verify IB Gateway Connection

```bash
# Activate virtual environment
source venv/bin/activate

# Test connection
python -c "
from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)
print(f'Connected: {ib.isConnected()}')
print(f'Account: {ib.managedAccounts()}')
ib.disconnect()
"
```

**Expected Output**:
```
Connected: True
Account: ['DU1234567']  # Your paper trading account
```

**Troubleshooting**:
- If connection fails, check IB Gateway is running
- Verify API settings enabled
- Verify correct port (4002 for paper, 7496 for live)
- Check firewall allows localhost connections

---

## Running the System

### Development Mode

For development and testing:

```bash
# Activate virtual environment
source venv/bin/activate

# Ensure IB Gateway is running (check previous section)

# Run main system
python src/main.py

# In separate terminal, run dashboard
source venv/bin/activate
python src/dashboard/app.py

# In separate terminal, run trailing stop scheduler
source venv/bin/activate
python scripts/trailing_stop_scheduler.py
```

### Production Mode

For production deployment with process management:

#### Using systemd (Linux)

1. **Create main system service**:
   ```bash
   sudo nano /etc/systemd/system/screener.service
   ```

   ```ini
   [Unit]
   Description=Screener Trading System
   After=network.target ibgateway.service
   Requires=ibgateway.service

   [Service]
   Type=simple
   User=your-username
   WorkingDirectory=/path/to/screener
   Environment="PATH=/path/to/screener/venv/bin"
   ExecStart=/path/to/screener/venv/bin/python src/main.py
   Restart=on-failure
   RestartSec=30
   StandardOutput=append:/path/to/screener/logs/screener.log
   StandardError=append:/path/to/screener/logs/screener-error.log

   [Install]
   WantedBy=multi-user.target
   ```

2. **Create dashboard service**:
   ```bash
   sudo nano /etc/systemd/system/screener-dashboard.service
   ```

   ```ini
   [Unit]
   Description=Screener Dashboard
   After=screener.service
   Requires=screener.service

   [Service]
   Type=simple
   User=your-username
   WorkingDirectory=/path/to/screener
   Environment="PATH=/path/to/screener/venv/bin"
   ExecStart=/path/to/screener/venv/bin/python src/dashboard/app.py
   Restart=on-failure
   RestartSec=30
   StandardOutput=append:/path/to/screener/logs/dashboard.log
   StandardError=append:/path/to/screener/logs/dashboard-error.log

   [Install]
   WantedBy=multi-user.target
   ```

3. **Create trailing stop service**:
   ```bash
   sudo nano /etc/systemd/system/screener-trailing.service
   ```

   ```ini
   [Unit]
   Description=Screener Trailing Stops
   After=screener.service
   Requires=screener.service

   [Service]
   Type=simple
   User=your-username
   WorkingDirectory=/path/to/screener
   Environment="PATH=/path/to/screener/venv/bin"
   ExecStart=/path/to/screener/venv/bin/python scripts/trailing_stop_scheduler.py
   Restart=on-failure
   RestartSec=30
   StandardOutput=append:/path/to/screener/logs/trailing.log
   StandardError=append:/path/to/screener/logs/trailing-error.log

   [Install]
   WantedBy=multi-user.target
   ```

4. **Enable and start services**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable screener screener-dashboard screener-trailing
   sudo systemctl start screener screener-dashboard screener-trailing

   # Check status
   sudo systemctl status screener screener-dashboard screener-trailing
   ```

#### Using Docker (Alternative)

```bash
# Build Docker image
docker build -t screener:latest .

# Run container
docker run -d \
  --name screener \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env \
  -p 8050:8050 \
  screener:latest

# Check logs
docker logs -f screener
```

### Verification

After starting the system:

```bash
# Check all processes running
ps aux | grep screener

# Check log files
tail -f logs/screener.log
tail -f logs/dashboard.log
tail -f logs/trailing.log

# Check IB connection
# Should see in logs:
# INFO | ib_manager:connect:123 - Connected to IB Gateway at 127.0.0.1:4002
```

---

## Dashboard Access

### Local Access

Once the dashboard is running, access it at:

```
http://localhost:8050
```

### Network Access

To access from other devices on your network:

1. **Find your IP address**:
   ```bash
   # Linux/macOS
   ip addr show | grep "inet "
   # or
   ifconfig | grep "inet "

   # Should show something like: 192.168.1.100
   ```

2. **Access dashboard**:
   ```
   http://192.168.1.100:8050
   ```

3. **Configure firewall** (if needed):
   ```bash
   # Ubuntu/Debian
   sudo ufw allow 8050/tcp

   # CentOS/RHEL
   sudo firewall-cmd --add-port=8050/tcp --permanent
   sudo firewall-cmd --reload
   ```

### Dashboard Features

#### Watchlist Tab
- Real-time screened symbols
- SABR20 scores (0-100)
- Current prices and changes
- Entry/exit signals
- Click symbol to view detailed chart

#### Charts Tab
- Multi-timeframe charts (5min, 15min, 1hour, 4hour, 1day)
- Price with Bollinger Bands and moving averages
- Stochastic RSI panel
- MACD panel
- Volume panel with color coding
- Interactive zoom and pan

#### Positions Tab
- Live position tracking
- Unrealized P&L (real-time)
- Realized P&L (closed trades)
- Entry price, current price, quantity
- Stop loss levels
- Position duration
- Color-coded profit/loss

#### Portfolio Summary
- Total account value
- Total unrealized P&L
- Total realized P&L
- Current risk exposure (% of account)
- Number of open positions

### Dashboard Shortcuts

- **Refresh**: Click browser refresh (dashboard auto-updates)
- **Watchlist**: Updates every 60 seconds
- **Positions**: Updates every 5 seconds
- **Charts**: Updates every 30 seconds

---

## Monitoring and Logs

### Log Files

All logs are stored in the `logs/` directory:

```
logs/
├── screener.log         # Main system logs
├── dashboard.log        # Dashboard logs
├── trailing.log         # Trailing stop logs
├── errors.log           # Error logs only
├── ib_connection.log    # IB Gateway connection logs
└── trades.log           # Trade execution logs
```

### Log Levels

Configured in `.env` and `config/system_config.yaml`:

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages
- **CRITICAL**: Critical failures

### Viewing Logs

```bash
# Real-time log monitoring
tail -f logs/screener.log

# View errors only
tail -f logs/errors.log

# Search logs for specific symbol
grep "AAPL" logs/screener.log

# View last 100 lines
tail -100 logs/screener.log

# View logs from today
grep "$(date +%Y-%m-%d)" logs/screener.log
```

### Log Rotation

Logs are automatically rotated based on configuration:

- **Max Size**: 10 MB per log file
- **Retention**:
  - Standard logs: 30 days
  - Error logs: 90 days
- **Compression**: Old logs compressed with gzip

To manually rotate logs:

```bash
# Archive old logs
cd logs
gzip screener.log.1 screener.log.2
mv *.gz archive/

# Clean logs older than 90 days
find logs/ -name "*.log.*" -mtime +90 -delete
```

### Debugging

Enable debug logging temporarily:

```bash
# Edit .env
LOG_LEVEL=DEBUG

# Restart system
sudo systemctl restart screener

# View debug logs
tail -f logs/screener.log
```

**Remember to set back to INFO for production**:
```bash
LOG_LEVEL=INFO
sudo systemctl restart screener
```

### Health Checks

The system includes built-in health checks:

```bash
# Check IB Gateway connection
curl http://localhost:8050/health/ib

# Check database connection
curl http://localhost:8050/health/db

# Check overall system health
curl http://localhost:8050/health

# Expected response:
# {"status": "healthy", "ib_connected": true, "db_connected": true}
```

---

## Database Management

### SQLite (Development/Small-Scale)

Default database location: `data/screener.db`

#### Backup Database

```bash
# Manual backup
cp data/screener.db backups/screener_$(date +%Y%m%d_%H%M%S).db

# Automated backup (add to crontab)
0 23 * * * /path/to/screener/scripts/backup_database.sh
```

#### Restore Database

```bash
# Stop system
sudo systemctl stop screener screener-dashboard screener-trailing

# Restore from backup
cp backups/screener_20251115_230000.db data/screener.db

# Restart system
sudo systemctl start screener screener-dashboard screener-trailing
```

#### View Database

```bash
# Install sqlite3 if needed
sudo apt-get install sqlite3

# Open database
sqlite3 data/screener.db

# View tables
.tables

# View trades
SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10;

# View performance
SELECT
  COUNT(*) as total_trades,
  SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
  SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losers,
  AVG(pnl) as avg_pnl,
  SUM(pnl) as total_pnl
FROM trades
WHERE status = 'closed';

# Exit
.quit
```

### PostgreSQL (Production)

For production with higher volume:

#### Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Create Database

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL prompt:
CREATE DATABASE screener;
CREATE USER screener_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE screener TO screener_user;
\q
```

#### Update Configuration

Edit `.env`:
```bash
DATABASE_URL=postgresql://screener_user:your_secure_password@localhost:5432/screener
```

#### Migrate to PostgreSQL

```bash
# Export from SQLite
sqlite3 data/screener.db .dump > backup.sql

# Import to PostgreSQL (may need manual editing)
psql -U screener_user -d screener -f backup.sql

# Or use migration tool
pip install pgloader
pgloader data/screener.db postgresql://screener_user:password@localhost/screener
```

#### PostgreSQL Backup

```bash
# Manual backup
pg_dump -U screener_user screener > backups/screener_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
pg_dump -U screener_user screener | gzip > backups/screener_$(date +%Y%m%d_%H%M%S).sql.gz

# Automated backup (add to crontab)
0 23 * * * pg_dump -U screener_user screener | gzip > /path/to/backups/screener_$(date +\%Y\%m\%d).sql.gz
```

#### PostgreSQL Restore

```bash
# Stop system
sudo systemctl stop screener

# Drop and recreate database
psql -U postgres
DROP DATABASE screener;
CREATE DATABASE screener;
\q

# Restore from backup
psql -U screener_user screener < backups/screener_20251115.sql
# or
gunzip < backups/screener_20251115.sql.gz | psql -U screener_user screener

# Restart system
sudo systemctl start screener
```

### Database Maintenance

#### Vacuum and Analyze (SQLite)

```bash
# Optimize database
sqlite3 data/screener.db "VACUUM;"
sqlite3 data/screener.db "ANALYZE;"
```

#### Vacuum and Analyze (PostgreSQL)

```bash
# Run as postgres user
sudo -u postgres psql screener -c "VACUUM ANALYZE;"

# Or setup autovacuum (recommended)
# Edit postgresql.conf:
autovacuum = on
```

#### Check Database Size

```bash
# SQLite
ls -lh data/screener.db

# PostgreSQL
psql -U screener_user screener -c "SELECT pg_size_pretty(pg_database_size('screener'));"
```

---

## Production Checklist

Before deploying to production, verify:

### Pre-Deployment

- [ ] **Testing Complete**
  - [ ] All 662 tests passing
  - [ ] Integration tests with IB Gateway passing
  - [ ] Paper trading tested for at least 1 week
  - [ ] Performance benchmarks met

- [ ] **Configuration**
  - [ ] `.env` file configured correctly
  - [ ] `config/trading_params.yaml` reviewed
  - [ ] `config/system_config.yaml` reviewed
  - [ ] Risk limits verified (1% per trade, 3% portfolio)
  - [ ] Position limits set appropriately

- [ ] **IB Gateway**
  - [ ] IB Gateway installed and configured
  - [ ] API access enabled
  - [ ] Correct port configured (4002 paper, 7496 live)
  - [ ] Auto-restart configured
  - [ ] Connection tested and stable

- [ ] **Database**
  - [ ] Database initialized
  - [ ] Backup procedures in place
  - [ ] Automated backups configured
  - [ ] Test restore performed

- [ ] **Security**
  - [ ] `.env` file permissions: 600
  - [ ] Config directory permissions: 700
  - [ ] Database credentials secure
  - [ ] Firewall configured
  - [ ] No credentials in git

- [ ] **Monitoring**
  - [ ] Log rotation configured
  - [ ] Error alerting configured (if enabled)
  - [ ] Health checks working
  - [ ] Metrics collection configured (if enabled)

- [ ] **Infrastructure**
  - [ ] Sufficient disk space (>10 GB free)
  - [ ] Stable network connection
  - [ ] UPS configured (for production)
  - [ ] System backups configured
  - [ ] Systemd services configured (Linux)

### Post-Deployment

- [ ] **Verification (Day 1)**
  - [ ] All services running
  - [ ] IB Gateway connected
  - [ ] Dashboard accessible
  - [ ] Watchlist updating
  - [ ] Positions tracking working
  - [ ] Logs being written
  - [ ] No errors in logs

- [ ] **Monitoring (Week 1)**
  - [ ] Daily log review
  - [ ] Verify first trades execute correctly
  - [ ] Verify risk controls enforced
  - [ ] Verify P&L calculation accurate
  - [ ] Verify stop losses working
  - [ ] Verify trailing stops adjusting

- [ ] **Optimization (Week 2+)**
  - [ ] Review performance metrics
  - [ ] Tune screening parameters if needed
  - [ ] Adjust position sizing if needed
  - [ ] Review and optimize watchlist generation
  - [ ] Consider enabling multiprocessing for large universes

---

## Troubleshooting

### IB Connection Issues

**Problem**: Cannot connect to IB Gateway

**Solutions**:
1. Verify IB Gateway is running:
   ```bash
   ps aux | grep ibgateway
   # or
   sudo systemctl status ibgateway
   ```

2. Check IB Gateway API settings:
   - Configure → Settings → API → Settings
   - Enable ActiveX and Socket Clients: ✓
   - Socket port: 4002 (paper) or 7496 (live)

3. Verify port in `.env` matches IB Gateway:
   ```bash
   grep IB_PORT .env
   # Should show: IB_PORT=4002
   ```

4. Check firewall:
   ```bash
   sudo ufw status | grep 4002
   # Should allow localhost connections
   ```

5. Test direct connection:
   ```bash
   telnet 127.0.0.1 4002
   # Should connect successfully
   ```

**Problem**: IB Gateway disconnects frequently

**Solutions**:
1. Check network stability
2. Verify IB Gateway auto-reconnect enabled
3. Check IB account status (paper trading enabled)
4. Review IB Gateway logs for errors
5. Increase connection timeout in config
6. Consider dedicated network connection

### Data Pipeline Errors

**Problem**: Historical data not fetching

**Solutions**:
1. Verify IB Gateway connected
2. Check symbol is valid (use IB TWS to verify)
3. Verify market is open or use RTH=False for extended hours
4. Check rate limiting (max 60 requests per 10 minutes)
5. Review logs for specific error messages

**Problem**: Parquet files not being created

**Solutions**:
1. Check data directory exists and is writable:
   ```bash
   ls -ld data/
   # Should show: drwxr-xr-x
   ```

2. Check disk space:
   ```bash
   df -h
   # Ensure >1GB free
   ```

3. Verify historical_manager is working:
   ```bash
   python -c "from src.data.historical_manager import historical_manager; print(historical_manager)"
   ```

### Dashboard Not Loading

**Problem**: Cannot access dashboard at localhost:8050

**Solutions**:
1. Verify dashboard process running:
   ```bash
   ps aux | grep dashboard
   ```

2. Check port not in use:
   ```bash
   netstat -tuln | grep 8050
   # or
   lsof -i :8050
   ```

3. Check dashboard logs:
   ```bash
   tail -f logs/dashboard.log
   ```

4. Verify DASH_HOST and DASH_PORT in `.env`:
   ```bash
   grep DASH_ .env
   ```

5. Try accessing from 0.0.0.0:
   ```
   http://0.0.0.0:8050
   ```

**Problem**: Dashboard loads but shows no data

**Solutions**:
1. Verify main system is running
2. Check database has data:
   ```bash
   sqlite3 data/screener.db "SELECT COUNT(*) FROM positions;"
   ```

3. Check dashboard update intervals in config
4. Review dashboard logs for errors
5. Try manual browser refresh (Ctrl+F5)

### Test Failures

**Problem**: Tests failing with "IB Gateway not connected"

**Solution**:
- Tests that require IB Gateway should be skipped without connection
- To run full integration tests, start IB Gateway on port 4002
- Use `pytest -m "not integration"` to skip integration tests

**Problem**: Tests failing with import errors

**Solutions**:
1. Verify virtual environment activated:
   ```bash
   which python
   # Should show: /path/to/screener/venv/bin/python
   ```

2. Reinstall dependencies:
   ```bash
   pip install --upgrade -r requirements.txt
   ```

3. Verify TA-Lib installed:
   ```bash
   python -c "import talib; print(talib.__version__)"
   ```

### Performance Issues

**Problem**: Screening takes too long (>30s for 1000 symbols)

**Solutions**:
1. Enable multiprocessing in config:
   ```yaml
   performance:
     enable_multiprocessing: true
     max_workers: 4
   ```

2. Increase cache TTL:
   ```yaml
   cache:
     ttl: 600  # 10 minutes instead of 5
   ```

3. Reduce universe size or use more aggressive coarse filters

4. Use PostgreSQL instead of SQLite for large datasets

5. Add more RAM to system

**Problem**: High memory usage

**Solutions**:
1. Reduce batch size in config
2. Enable garbage collection:
   ```yaml
   performance:
     gc_interval: 300
   ```

3. Limit concurrent positions
4. Reduce historical data lookback period

### Database Issues

**Problem**: Database locked errors (SQLite)

**Solutions**:
1. Close any open database connections
2. Stop all screener processes
3. Vacuum database:
   ```bash
   sqlite3 data/screener.db "VACUUM;"
   ```

4. Consider migrating to PostgreSQL for production

**Problem**: Database corruption

**Solutions**:
1. Stop all processes
2. Try integrity check:
   ```bash
   sqlite3 data/screener.db "PRAGMA integrity_check;"
   ```

3. Restore from backup:
   ```bash
   cp backups/screener_20251115.db data/screener.db
   ```

4. If no backup, export/import:
   ```bash
   sqlite3 data/screener.db .dump > recovered.sql
   sqlite3 data/screener_new.db < recovered.sql
   mv data/screener_new.db data/screener.db
   ```

---

## Maintenance

### Daily Tasks

1. **Check System Status**
   ```bash
   # Verify services running
   sudo systemctl status screener screener-dashboard screener-trailing

   # Check IB Gateway connection
   curl http://localhost:8050/health/ib

   # Review error logs
   tail -50 logs/errors.log
   ```

2. **Review Trading Activity**
   - Check dashboard positions tab
   - Review realized P&L
   - Verify risk exposure within limits
   - Check for any rejected orders

3. **Database Quick Check**
   ```bash
   # Check database size
   ls -lh data/screener.db

   # Verify recent trades logged
   sqlite3 data/screener.db "SELECT COUNT(*) FROM trades WHERE date(entry_time) = date('now');"
   ```

### Weekly Tasks

1. **Log Review and Cleanup**
   ```bash
   # Archive old logs
   cd logs
   gzip screener.log.{1..7}
   mv *.gz archive/

   # Check log disk usage
   du -sh logs/
   ```

2. **Performance Review**
   - Review screening performance (should be <30s for 1000 symbols)
   - Check dashboard responsiveness
   - Review database query times
   - Check memory usage trends

3. **Backup Verification**
   ```bash
   # Verify backups exist
   ls -lh backups/ | tail -10

   # Test restore (in test environment)
   cp backups/screener_latest.db /tmp/test_restore.db
   sqlite3 /tmp/test_restore.db "SELECT COUNT(*) FROM trades;"
   ```

4. **Update Universe**
   ```bash
   # Run universe update script
   python scripts/update_universe.py

   # Verify new universe size
   wc -l data/universe.csv
   ```

### Monthly Tasks

1. **System Updates**
   ```bash
   # Update system packages (Ubuntu/Debian)
   sudo apt update && sudo apt upgrade

   # Update Python packages
   source venv/bin/activate
   pip list --outdated
   # Update specific packages if needed
   pip install --upgrade package_name
   ```

2. **Database Optimization**
   ```bash
   # SQLite
   sqlite3 data/screener.db "VACUUM; ANALYZE;"

   # PostgreSQL
   psql -U screener_user screener -c "VACUUM ANALYZE;"
   ```

3. **Performance Analysis**
   - Review monthly P&L
   - Analyze win rate and average win/loss
   - Review SABR20 scoring effectiveness
   - Analyze trade duration and holding periods

4. **Configuration Review**
   - Review trading parameters
   - Adjust risk limits if needed (with caution)
   - Review and update watchlist criteria
   - Update universe filters if needed

5. **Full System Backup**
   ```bash
   # Backup entire system
   tar -czf /backup/location/screener_$(date +%Y%m%d).tar.gz \
     --exclude=venv \
     --exclude=__pycache__ \
     /path/to/screener
   ```

### Quarterly Tasks

1. **Comprehensive Testing**
   - Run full test suite
   - Verify all integration tests pass
   - Test disaster recovery procedures
   - Test IB Gateway failover

2. **Security Audit**
   - Review file permissions
   - Update passwords/API keys
   - Review access logs
   - Check for security updates

3. **Performance Tuning**
   - Analyze bottlenecks
   - Optimize database queries
   - Review and tune cache settings
   - Consider infrastructure upgrades

### Annual Tasks

1. **System Upgrade**
   - Review new Python version compatibility
   - Update all dependencies to latest stable
   - Test thoroughly in staging environment
   - Deploy to production

2. **Strategy Review**
   - Analyze full year performance
   - Review SABR20 components effectiveness
   - Consider parameter adjustments
   - Document lessons learned

---

## Security

### Best Practices

1. **Credentials**
   - Never commit `.env` to git
   - Use strong passwords (20+ characters)
   - Rotate passwords quarterly
   - Use different passwords for IB, database, etc.

2. **File Permissions**
   ```bash
   chmod 600 .env                    # Only owner can read/write
   chmod 700 config/                 # Only owner can access
   chmod 755 data/ logs/ backups/    # Owner full, others read
   ```

3. **Network Security**
   ```bash
   # Firewall rules
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow 22/tcp              # SSH
   sudo ufw allow 8050/tcp            # Dashboard (if needed)
   sudo ufw enable
   ```

4. **Database Security**
   - Use strong database password
   - Restrict database network access to localhost
   - Enable SSL for PostgreSQL connections
   - Regular backups with encryption

5. **Monitoring**
   - Review access logs regularly
   - Alert on suspicious activity
   - Monitor for brute force attempts
   - Track configuration changes

### Secrets Management

For production deployment, consider using a secrets manager:

```bash
# Example with HashiCorp Vault
export VAULT_ADDR='http://127.0.0.1:8200'
vault kv put secret/screener \
  ib_password="your-password" \
  db_password="your-db-password"

# Retrieve in application
vault kv get -field=ib_password secret/screener
```

### Audit Logging

Enable audit logging for security compliance:

```yaml
# In config/system_config.yaml
logging:
  handlers:
    audit:
      class: logging.handlers.RotatingFileHandler
      level: INFO
      formatter: detailed
      filename: logs/audit.log
      maxBytes: 10485760
      backupCount: 365  # Keep 1 year
```

---

## Performance Tuning

### System Optimization

1. **Linux Kernel Tuning**
   ```bash
   # Edit /etc/sysctl.conf
   # Increase network buffer sizes
   net.core.rmem_max = 134217728
   net.core.wmem_max = 134217728
   net.ipv4.tcp_rmem = 4096 87380 67108864
   net.ipv4.tcp_wmem = 4096 65536 67108864

   # Apply changes
   sudo sysctl -p
   ```

2. **Python Optimization**
   ```bash
   # Use PyPy for performance-critical code (optional)
   # Note: May have compatibility issues with some packages
   pypy -m pip install -r requirements.txt
   ```

3. **Database Optimization**

   For SQLite:
   ```sql
   -- Add indexes for common queries
   CREATE INDEX idx_trades_symbol ON trades(symbol);
   CREATE INDEX idx_trades_entry_time ON trades(entry_time);
   CREATE INDEX idx_trades_status ON trades(status);

   -- Optimize journal mode
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   ```

   For PostgreSQL:
   ```sql
   -- Add indexes
   CREATE INDEX idx_trades_symbol ON trades(symbol);
   CREATE INDEX idx_trades_entry_time ON trades(entry_time);
   CREATE INDEX idx_trades_status ON trades(status);

   -- Analyze tables
   ANALYZE trades;
   ANALYZE positions;
   ```

4. **Cache Optimization**

   Increase cache size for large universes:
   ```yaml
   # In config/system_config.yaml
   cache:
     ttl: 600           # 10 minutes
     max_size: 5000     # Increased from 1000
   ```

### Application Tuning

1. **Multiprocessing for Large Universes**

   Enable for >1000 symbols:
   ```yaml
   # In config/system_config.yaml
   performance:
     enable_multiprocessing: true
     max_workers: 8  # Set to CPU core count
   ```

2. **Batch Size Optimization**

   Tune based on memory:
   ```yaml
   # In config/system_config.yaml
   performance:
     batch_size: 200  # Increased from 100
   ```

3. **Connection Pooling**

   For PostgreSQL:
   ```yaml
   # In config/system_config.yaml
   performance:
     db_pool_size: 10        # Increased from 5
     db_max_overflow: 20     # Increased from 10
   ```

### Monitoring Performance

1. **Enable Profiling**
   ```yaml
   # In config/system_config.yaml
   development:
     profiling_enabled: true
   ```

2. **Review Performance Logs**
   ```bash
   grep "PERFORMANCE" logs/screener.log
   ```

3. **Benchmark Screening**
   ```bash
   python scripts/benchmark_screening.py
   ```

---

## Support and Resources

### Documentation
- **Implementation Guide**: `IMPLEMENTATION_GUIDE.md`
- **Test Results**: `TEST_RESULTS.md`
- **Architecture**: `ARCHITECTURE.md`
- **Product Requirements**: `PRD/` directory

### External Resources
- IB API Documentation: https://interactivebrokers.github.io/tws-api/
- ib_insync Documentation: https://ib-insync.readthedocs.io/
- TA-Lib Documentation: https://ta-lib.org/
- Dash Documentation: https://dash.plotly.com/

### Getting Help

For issues or questions:
1. Check logs for specific error messages
2. Review troubleshooting section above
3. Search existing GitHub issues
4. Create new GitHub issue with:
   - Error message and stack trace
   - Steps to reproduce
   - System information (OS, Python version)
   - Relevant log excerpts

---

## Appendix

### A. Environment Variable Reference

Complete list of environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `IB_HOST` | 127.0.0.1 | IB Gateway host |
| `IB_PORT` | 4002 | IB Gateway port (4002 paper, 7496 live) |
| `IB_CLIENT_ID` | 1 | IB client ID (1-32) |
| `DATABASE_URL` | sqlite:///data/screener.db | Database connection string |
| `ACCOUNT_BALANCE` | 100000.00 | Starting account balance |
| `MAX_RISK_PER_TRADE` | 0.01 | Max risk per trade (1%) |
| `MAX_PORTFOLIO_RISK` | 0.03 | Max total portfolio risk (3%) |
| `MAX_POSITIONS` | 10 | Maximum concurrent positions |
| `DATA_DIR` | ./data | Data storage directory |
| `LOG_DIR` | ./logs | Log file directory |
| `BACKUP_DIR` | ./backups | Backup directory |
| `DASH_HOST` | 0.0.0.0 | Dashboard host |
| `DASH_PORT` | 8050 | Dashboard port |
| `DASH_DEBUG` | false | Debug mode |
| `LOG_LEVEL` | INFO | Log level |
| `LOG_ROTATION` | 1 day | Log rotation period |
| `LOG_RETENTION` | 30 days | Log retention period |
| `CACHE_TTL` | 300 | Cache TTL (seconds) |
| `MAX_WORKERS` | 4 | Parallel workers |
| `BATCH_SIZE` | 100 | Batch processing size |

### B. Command Reference

Quick reference for common commands:

```bash
# Virtual Environment
source venv/bin/activate              # Activate venv
deactivate                            # Deactivate venv

# Running System
python src/main.py                    # Main system
python src/dashboard/app.py           # Dashboard
python scripts/trailing_stop_scheduler.py  # Trailing stops

# Testing
pytest tests/ -v                      # All tests
pytest tests/ -v --cov=src            # With coverage
pytest tests/test_specific.py -v     # Specific test file
pytest -m "not integration"           # Skip integration tests

# Database
sqlite3 data/screener.db              # Open SQLite database
sqlite3 data/screener.db "VACUUM;"    # Optimize database
pg_dump -U screener_user screener     # Backup PostgreSQL

# Logs
tail -f logs/screener.log             # Real-time logs
grep ERROR logs/screener.log          # Search errors
tail -100 logs/screener.log           # Last 100 lines

# System Management (systemd)
sudo systemctl start screener         # Start service
sudo systemctl stop screener          # Stop service
sudo systemctl restart screener       # Restart service
sudo systemctl status screener        # Check status
sudo systemctl enable screener        # Enable auto-start

# Performance
python scripts/benchmark_screening.py # Benchmark screening
python -m cProfile src/main.py        # Profile application
```

### C. Port Reference

| Port | Service | Protocol |
|------|---------|----------|
| 4002 | IB Gateway (Paper Trading) | TCP |
| 7496 | IB Gateway (Live Trading) | TCP |
| 8050 | Screener Dashboard | HTTP |
| 5432 | PostgreSQL (if used) | TCP |
| 9090 | Prometheus Metrics (optional) | HTTP |

### D. File Structure Reference

```
screener/
├── .env                       # Environment variables (gitignored)
├── .env.example               # Environment template
├── .gitignore                 # Git ignore rules
├── README.md                  # Project overview
├── DEPLOYMENT_GUIDE.md        # This file
├── TEST_RESULTS.md            # Test results documentation
├── ARCHITECTURE.md            # System architecture
├── TODO.md                    # Progress tracker
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Pytest configuration
├── config/
│   ├── trading_params.yaml    # Trading parameters
│   └── system_config.yaml     # System configuration
├── src/
│   ├── data/                  # Data layer
│   ├── indicators/            # Technical indicators
│   ├── screening/             # Screening & scoring
│   ├── regime/                # Market regime analysis
│   ├── execution/             # Trade execution & validation
│   ├── dashboard/             # Dash web application
│   ├── database/              # Database layer
│   └── main.py                # System entry point
├── tests/                     # Test suite
├── scripts/                   # Utility scripts
├── data/                      # Data storage (gitignored)
│   ├── universe.csv           # Stock universe
│   ├── screener.db            # SQLite database
│   └── *.parquet              # Historical data
├── logs/                      # Log files (gitignored)
│   ├── screener.log
│   ├── dashboard.log
│   └── errors.log
└── backups/                   # Database backups (gitignored)
    └── screener_*.db
```

---

**End of Deployment Guide**

For questions or issues, please refer to the troubleshooting section or create a GitHub issue.
