# Trade Database & Journaling System

Comprehensive SQLite-based trade journaling system with performance analytics for the Screener trading system.

---

## Table of Contents

- [Overview](#overview)
- [Database Schema](#database-schema)
- [Usage Examples](#usage-examples)
- [Performance Analytics](#performance-analytics)
- [Integration with OrderManager](#integration-with-ordermanager)
- [Database Maintenance](#database-maintenance)
- [API Reference](#api-reference)

---

## Overview

The Trade Database provides comprehensive trade journaling capabilities including:

- **Trade Recording**: Entry/exit timestamps, prices, P&L calculations
- **Performance Tracking**: Win rate, profit factor, Sharpe ratio, max drawdown
- **Risk Metrics**: MAE/MFE tracking, risk/reward ratios
- **Integration**: Automatic recording from OrderManager
- **Analytics**: Equity curve generation, per-symbol statistics

### Key Features

1. **Automatic Recording**: Integrates with OrderManager for hands-free journaling
2. **Real-time MAE/MFE**: Tracks maximum adverse/favorable excursion during trade
3. **Performance Analytics**: 15+ performance metrics calculated automatically
4. **Thread-Safe**: Uses thread-local connections for concurrent access
5. **Efficient Storage**: SQLite with proper indexing for fast queries

---

## Database Schema

### Trades Table

```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                    -- 'BUY' or 'SELL'
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,                   -- NULL for open trades
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity INTEGER NOT NULL,
    stop_price REAL,
    target_price REAL,
    actual_stop REAL,                      -- Actual stop hit price
    actual_target REAL,                    -- Actual target hit price
    commission REAL DEFAULT 0.0,
    realized_pnl REAL,                     -- Calculated on exit
    pnl_pct REAL,                          -- Percentage return
    risk_amount REAL NOT NULL,             -- Initial risk ($)
    risk_reward_ratio REAL,                -- Actual R:R achieved
    mae REAL,                              -- Maximum Adverse Excursion
    mfe REAL,                              -- Maximum Favorable Excursion
    hold_time_minutes INTEGER,             -- Trade duration
    exit_reason TEXT,                      -- 'STOP', 'TARGET', 'MANUAL', 'TRAILING_STOP'
    sabr20_score REAL,                     -- Entry SABR20 score
    regime TEXT,                           -- Market regime at entry
    notes TEXT                             -- Trade notes
);
```

### Indexes

```sql
CREATE INDEX idx_symbol ON trades(symbol);
CREATE INDEX idx_entry_time ON trades(entry_time);
CREATE INDEX idx_exit_time ON trades(exit_time);
CREATE INDEX idx_realized_pnl ON trades(realized_pnl);
```

---

## Usage Examples

### Basic Usage

```python
from src.data.trade_database import trade_database

# Record trade entry
trade_id = trade_database.record_trade_entry(
    symbol='AAPL',
    side='BUY',
    entry_time=datetime.now(),
    entry_price=150.00,
    quantity=100,
    stop_price=148.00,
    target_price=154.00,
    risk_amount=200.00,
    sabr20_score=85.5,
    regime='TRENDING_UP'
)

# Update MAE/MFE during trade (called from realtime bars)
trade_database.update_trade_mae_mfe(trade_id, 148.50)  # Adverse
trade_database.update_trade_mae_mfe(trade_id, 153.00)  # Favorable

# Record trade exit
trade_database.record_trade_exit(
    trade_id=trade_id,
    exit_time=datetime.now(),
    exit_price=153.50,
    exit_reason='TARGET',
    commission=2.00
)
```

### Query Trades

```python
# Get single trade
trade = trade_database.get_trade(trade_id)
print(f"P&L: ${trade['realized_pnl']:.2f}")

# Get all open trades
open_trades = trade_database.get_open_trades()
print(f"{len(open_trades)} positions open")

# Get closed trades (with filters)
closed_trades = trade_database.get_closed_trades(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 1, 31),
    symbol='AAPL'
)

# Get trades for specific symbol
aapl_trades = trade_database.get_trades_by_symbol('AAPL')
```

### Performance Analytics

```python
# Get comprehensive statistics
stats = trade_database.get_performance_stats()

print(f"Total trades: {stats['total_trades']}")
print(f"Win rate: {stats['win_rate']:.1f}%")
print(f"Total P&L: ${stats['total_pnl']:,.2f}")
print(f"Avg win: ${stats['avg_win']:.2f}")
print(f"Avg loss: ${stats['avg_loss']:.2f}")
print(f"Profit factor: {stats['profit_factor']:.2f}")
print(f"Sharpe ratio: {stats['sharpe_ratio']:.2f}")
print(f"Max drawdown: {stats['max_drawdown']:.2f}%")
print(f"Avg hold time: {stats['avg_hold_time_minutes']:.0f} minutes")

# Get equity curve
equity_curve = trade_database.get_equity_curve()
equity_curve.plot(x='exit_time', y='equity', title='Account Equity Curve')

# Get symbol-specific stats
aapl_stats = trade_database.get_symbol_statistics('AAPL')
print(f"AAPL win rate: {aapl_stats['win_rate']:.1f}%")
```

### Add Notes to Trades

```python
# Add note during trade
trade_database.add_trade_note(
    trade_id=123,
    note="Tightened stop after breakout confirmation"
)

# Add exit note
trade_database.add_trade_note(
    trade_id=123,
    note="Exited at resistance level, taking profits"
)
```

### DataFrame Export

```python
import pandas as pd

# Get all trades as DataFrame
df = trade_database.get_trades_dataframe(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31)
)

# Analyze by regime
regime_performance = df.groupby('regime')['realized_pnl'].agg(['sum', 'mean', 'count'])
print(regime_performance)

# Analyze by SABR20 score bucket
df['score_bucket'] = pd.cut(df['sabr20_score'], bins=[0, 70, 80, 90, 100])
score_performance = df.groupby('score_bucket')['pnl_pct'].mean()
print(score_performance)

# Export to CSV
df.to_csv('trades_2025.csv', index=False)
```

---

## Performance Analytics

### Metrics Calculated

The `get_performance_stats()` method calculates:

| Metric | Formula | Description |
|--------|---------|-------------|
| `total_trades` | Count of closed trades | Total number of completed trades |
| `winning_trades` | Count where P&L > 0 | Number of profitable trades |
| `losing_trades` | Count where P&L < 0 | Number of losing trades |
| `win_rate` | (wins / total) × 100 | Percentage of winning trades |
| `total_pnl` | Σ realized_pnl | Total profit/loss |
| `avg_win` | mean(winning P&Ls) | Average profit per winning trade |
| `avg_loss` | mean(losing P&Ls) | Average loss per losing trade |
| `largest_win` | max(P&Ls) | Largest single winner |
| `largest_loss` | min(P&Ls) | Largest single loser |
| `avg_risk_reward` | mean(P&L / risk) | Average R:R ratio achieved |
| `profit_factor` | gross_profit / gross_loss | Ratio of total wins to total losses |
| `sharpe_ratio` | (μ / σ) × √252 | Annualized risk-adjusted return |
| `max_drawdown` | max equity decline % | Maximum peak-to-trough decline |
| `avg_hold_time_minutes` | mean(hold times) | Average trade duration |
| `total_commission` | Σ commissions | Total commissions paid |

### Sharpe Ratio Formula

```
Sharpe Ratio = (Mean Return / Std Dev of Returns) × √252

Where:
- Mean Return = average P&L per trade
- Std Dev = standard deviation of P&L
- √252 = annualization factor (252 trading days/year)
```

### Max Drawdown Formula

```
Drawdown(t) = (Equity(t) - Peak Equity) / Peak Equity × 100
Max Drawdown = min(all drawdowns)

Where:
- Peak Equity = running maximum of equity curve
- Calculated from equity curve, not individual positions
```

### Profit Factor

```
Profit Factor = Gross Profit / Gross Loss

Where:
- Gross Profit = Σ(all winning trades)
- Gross Loss = |Σ(all losing trades)|
- Values > 2.0 are excellent
- Values < 1.0 indicate losing system
```

---

## Integration with OrderManager

The Trade Database integrates automatically with OrderManager for hands-free journaling.

### Automatic Recording on Position Open

```python
from src.execution.order_manager import order_manager

# When position is opened, trade is automatically recorded
order_manager.open_position(
    symbol='AAPL',
    side='BUY',
    quantity=100,
    entry_price=150.00,
    stop_price=148.00,
    target_price=154.00,
    risk_amount=200.00
)

# Trade entry is automatically recorded in database
# SABR20 score and regime are captured if available
```

### Automatic MAE/MFE Tracking

```python
# Real-time bar updates automatically update MAE/MFE
# Called from RealtimeAggregator on each new bar

order_manager.update_position_price('AAPL', 148.50)
# Database is automatically updated with new MAE/MFE
```

### Automatic Recording on Position Close

```python
# When position is closed, trade exit is automatically recorded
order_manager.close_position(
    symbol='AAPL',
    exit_price=153.50,
    exit_reason='TARGET',
    commission=2.00,
    notes='Hit target after 4h consolidation'
)

# Exit is recorded with:
# - Calculated P&L and percentage
# - Final MAE/MFE values
# - Hold time in minutes
# - Exit reason and notes
```

### Position to Trade ID Mapping

The OrderManager maintains a mapping between positions and database trade IDs:

```python
# Internal mapping (managed automatically)
order_manager.position_to_trade_id = {
    'AAPL': 123,
    'MSFT': 124,
    'GOOGL': 125
}

# Used for MAE/MFE updates and exit recording
```

---

## Database Maintenance

### Backup Strategy

```python
import shutil
from pathlib import Path
from datetime import datetime

def backup_trade_database():
    """Create timestamped backup of trade database."""
    db_path = Path('data/trades.db')
    backup_dir = Path('data/backups')
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'trades_{timestamp}.db'

    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")

# Run daily backup (add to cron or system scheduler)
backup_trade_database()
```

### Cleanup Old Trades

```python
def archive_old_trades(days_old=365):
    """Archive trades older than specified days."""
    from datetime import datetime, timedelta
    import sqlite3

    cutoff_date = datetime.now() - timedelta(days=days_old)

    # Export to archive database
    archive_path = f'data/archive/trades_{cutoff_date.year}.db'

    with sqlite3.connect('data/trades.db') as source_conn:
        with sqlite3.connect(archive_path) as archive_conn:
            # Copy old trades
            source_conn.backup(archive_conn)

            # Delete from main database
            cursor = source_conn.cursor()
            cursor.execute("""
                DELETE FROM trades
                WHERE exit_time < ?
            """, (cutoff_date,))
            source_conn.commit()

            deleted_count = cursor.rowcount
            print(f"Archived {deleted_count} trades to {archive_path}")

# Run annually
archive_old_trades(days_old=365)
```

### Database Optimization

```python
def optimize_database():
    """Vacuum and analyze database for optimal performance."""
    import sqlite3

    with sqlite3.connect('data/trades.db') as conn:
        # Reclaim unused space
        conn.execute('VACUUM')

        # Update query planner statistics
        conn.execute('ANALYZE')

        print("Database optimized")

# Run monthly
optimize_database()
```

### Export to CSV

```python
def export_monthly_report(year, month):
    """Export monthly trading report to CSV."""
    from datetime import datetime

    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    df = trade_database.get_trades_dataframe(
        start_date=start_date,
        end_date=end_date
    )

    filename = f'reports/trades_{year}_{month:02d}.csv'
    df.to_csv(filename, index=False)
    print(f"Report exported: {filename}")

# Export each month
export_monthly_report(2025, 1)
```

---

## API Reference

### TradeDatabase Class

#### Methods

##### record_trade_entry()

```python
def record_trade_entry(
    symbol: str,
    side: str,
    entry_time: datetime,
    entry_price: float,
    quantity: int,
    stop_price: float,
    target_price: float,
    risk_amount: float,
    sabr20_score: Optional[float] = None,
    regime: Optional[str] = None
) -> int
```

Record new trade entry. Returns trade ID.

**Parameters:**
- `symbol`: Stock symbol (e.g., 'AAPL')
- `side`: 'BUY' or 'SELL'
- `entry_time`: Entry timestamp
- `entry_price`: Entry price per share
- `quantity`: Number of shares
- `stop_price`: Stop loss price
- `target_price`: Take profit price
- `risk_amount`: Initial risk in dollars
- `sabr20_score`: Optional SABR20 score (0-100)
- `regime`: Optional market regime ('TRENDING_UP', 'RANGING', etc.)

**Returns:** Database ID of inserted trade

---

##### record_trade_exit()

```python
def record_trade_exit(
    trade_id: int,
    exit_time: datetime,
    exit_price: float,
    exit_reason: str,
    commission: float = 0.0,
    actual_stop: Optional[float] = None,
    actual_target: Optional[float] = None,
    mae: Optional[float] = None,
    mfe: Optional[float] = None,
    notes: Optional[str] = None
) -> None
```

Update trade with exit information. Automatically calculates P&L, percentage return, R:R ratio, and hold time.

**Parameters:**
- `trade_id`: Database ID of trade
- `exit_time`: Exit timestamp
- `exit_price`: Exit price per share
- `exit_reason`: 'STOP', 'TARGET', 'MANUAL', 'TRAILING_STOP'
- `commission`: Total commission paid (default 0.0)
- `actual_stop`: Actual stop hit price (if applicable)
- `actual_target`: Actual target hit price (if applicable)
- `mae`: Maximum Adverse Excursion
- `mfe`: Maximum Favorable Excursion
- `notes`: Optional exit notes

---

##### get_performance_stats()

```python
def get_performance_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]
```

Calculate comprehensive performance statistics.

**Parameters:**
- `start_date`: Filter by exit_time >= start_date
- `end_date`: Filter by exit_time <= end_date

**Returns:** Dictionary with 15 performance metrics (see Performance Analytics section)

---

##### get_equity_curve()

```python
def get_equity_curve(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    starting_equity: float = 100000.0
) -> pd.DataFrame
```

Generate equity curve DataFrame.

**Parameters:**
- `start_date`: Filter by exit_time >= start_date
- `end_date`: Filter by exit_time <= end_date
- `starting_equity`: Starting account balance (default $100,000)

**Returns:** DataFrame with columns: `[exit_time, realized_pnl, cumulative_pnl, equity]`

---

##### update_trade_mae_mfe()

```python
def update_trade_mae_mfe(
    trade_id: int,
    current_price: float
) -> None
```

Update MAE/MFE for open trade based on current price. Called automatically from OrderManager.

**Parameters:**
- `trade_id`: Database ID of trade
- `current_price`: Current market price

**Notes:**
- Only updates if new extreme is reached
- Safe to call multiple times
- Only updates open trades (exit_time IS NULL)

---

##### add_trade_note()

```python
def add_trade_note(
    trade_id: int,
    note: str
) -> None
```

Append timestamped note to trade.

**Parameters:**
- `trade_id`: Database ID of trade
- `note`: Note text

**Example:**
```python
trade_database.add_trade_note(123, "Tightened stop after gap up")
# Stored as: "[2025-01-15 14:30:00] Tightened stop after gap up"
```

---

##### get_symbol_statistics()

```python
def get_symbol_statistics(
    symbol: str
) -> Dict[str, Any]
```

Get performance statistics for specific symbol.

**Parameters:**
- `symbol`: Stock symbol

**Returns:** Dictionary with symbol-specific performance metrics

---

### Exit Reasons

Valid exit reasons (stored in `exit_reason` field):

- `'STOP'`: Stop loss hit
- `'TARGET'`: Take profit target hit
- `'MANUAL'`: Manual exit by trader
- `'TRAILING_STOP'`: Trailing stop activated

---

## Performance Benchmarks

### Query Performance

Typical query times on database with 1000 trades:

| Operation | Time |
|-----------|------|
| Single trade lookup | <1ms |
| Get open trades | <5ms |
| Get closed trades (no filter) | <10ms |
| Get closed trades (date filter) | <5ms |
| Performance stats | <50ms |
| Equity curve generation | <100ms |
| DataFrame export | <150ms |

### Storage

- Average trade record: ~500 bytes
- 1000 trades: ~500 KB
- 10,000 trades: ~5 MB
- 100,000 trades: ~50 MB

### Optimization Tips

1. **Use date filters**: Always filter by date range for large datasets
2. **Batch operations**: Record multiple trades in same connection
3. **Index usage**: Ensure indexes exist on frequently queried columns
4. **Regular vacuum**: Run `VACUUM` monthly to reclaim space
5. **Archive old data**: Move trades older than 1 year to archive database

---

## Troubleshooting

### Database Locked Error

If you get "database is locked" errors:

```python
# Increase timeout
import sqlite3
conn = sqlite3.connect('data/trades.db', timeout=30.0)
```

Or ensure all connections are properly closed:

```python
trade_database.close()
```

### Missing MAE/MFE Data

If MAE/MFE values are 0 or NULL:

1. Verify `update_position_price()` is being called from realtime bars
2. Check that position_to_trade_id mapping exists
3. Confirm trade is still open (exit_time IS NULL)

### Performance Issues

If queries are slow:

```python
# Rebuild indexes
import sqlite3
with sqlite3.connect('data/trades.db') as conn:
    conn.execute('REINDEX')
    conn.execute('ANALYZE')
```

### Corrupt Database

If database becomes corrupted:

```python
# Restore from backup
import shutil
shutil.copy2('data/backups/trades_20250115_120000.db', 'data/trades.db')
```

---

## Best Practices

1. **Daily Backups**: Automate daily database backups
2. **Monthly Reports**: Export monthly CSV reports for analysis
3. **Add Notes**: Document important trades with notes
4. **Review Stats Weekly**: Review performance stats every week
5. **Archive Annually**: Archive trades older than 1 year
6. **Validate Data**: Periodically verify P&L calculations match broker statements

---

## Future Enhancements

Potential future additions:

- Multi-asset support (futures, options, forex)
- Position sizing analysis (optimal quantity backtesting)
- Slippage tracking
- Market condition correlation analysis
- Monte Carlo simulation
- Web dashboard for trade analytics
- Export to Excel with charts
- Integration with tax reporting tools

---

## References

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Trading Performance Metrics](https://www.investopedia.com/articles/trading/09/performance-measurement.asp)
- [Sharpe Ratio](https://www.investopedia.com/terms/s/sharperatio.asp)
- [Maximum Drawdown](https://www.investopedia.com/terms/m/maximum-drawdown-mdd.asp)
