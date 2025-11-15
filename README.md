# Screener - Multi-Timeframe Momentum Reversal Trading System

**Status**: Ready for Implementation
**Version**: 1.0.0-specification
**Last Updated**: 2025-11-14

---

## 🎯 Overview

Professional-grade algorithmic trading system that identifies and executes mean-reversion-to-trend-expansion opportunities across multiple timeframes.

**Capabilities:**
- Screens 500-2000 stocks in real-time
- Multi-timeframe analysis (15m, 1h, 4h)
- SABR20 proprietary scoring system (0-100 points)
- Automated trade execution via Interactive Brokers
- Real-time monitoring dashboard
- Comprehensive risk management

---

## 📖 Documentation

### For Implementation (Claude Code on Web)
**➡️ [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Complete implementation instructions with 5 core development rules

### Project Instructions
**➡️ [CLAUDE.md](CLAUDE.md)** - Claude Code project-specific instructions
**➡️ [TODO.md](TODO.md)** - Live implementation progress tracker (update frequently)

### Product Requirements (PRD)
Complete specifications in `/PRD/`:
- [00_system_requirements_and_architecture.md](PRD/00_system_requirements_and_architecture.md) - Tech stack & infrastructure
- [01_algorithm_spec.md](PRD/01_algorithm_spec.md) - Core trading algorithm
- [02_mean_reversion_trend_system.md](PRD/02_mean_reversion_trend_system.md) - Risk management
- [03_decision_tree_and_screening.md](PRD/03_decision_tree_and_screening.md) - Decision logic
- [04_universe_and_prescreening-1.md](PRD/04_universe_and_prescreening-1.md) - Universe construction
- [05_watchlist_generation_and_scoring.md](PRD/05_watchlist_generation_and_scoring.md) - SABR20 scoring
- [06_regime_and_market_checks.md](PRD/06_regime_and_market_checks.md) - Market regime analysis
- [07_realtime_dashboard_specification.md](PRD/07_realtime_dashboard_specification.md) - Dashboard UI
- [08_data_pipeline_and_infrastructure.md](PRD/08_data_pipeline_and_infrastructure.md) - Data management
- [09_execution_and_monitoring.md](PRD/09_execution_and_monitoring.md) - Trade execution

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Interactive Brokers account (paper trading for development)
- TWS or IB Gateway installed

### Installation
```bash
# Clone repository
git clone git@github.com:astoreyai/screener.git
cd screener

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your IB credentials
```

### Configuration
1. Start TWS or IB Gateway
2. Enable API (Configuration → API → Settings)
3. Set Socket Port: 7497 (paper) or 7496 (live)
4. Allow connections from 127.0.0.1

### Initialize
```bash
# Setup database
python scripts/setup_database.py

# Download historical data (optional)
python scripts/download_historical.py

# Run tests
pytest tests/ -v --cov=src
```

### Run
```bash
# Start dashboard (separate terminal)
python src/dashboard/app.py

# Start trading system
python src/main.py

# Access dashboard
# Open browser to http://localhost:8050
```

---

## 🏗️ Architecture

### Technology Stack
- **Data**: IB API (ib-insync), Pandas/Polars, Parquet
- **Indicators**: TA-Lib, pandas-ta
- **Database**: SQLAlchemy + PostgreSQL/SQLite
- **Dashboard**: Dash, Plotly, Bootstrap
- **Execution**: Interactive Brokers API
- **Testing**: pytest, pytest-cov

### Project Structure
```
screener/
├── README.md                    # This file
├── IMPLEMENTATION_GUIDE.md      # Complete implementation instructions
├── CLAUDE.md                    # Claude Code project instructions
├── TODO.md                      # Implementation progress tracker
├── PRD/                         # Product Requirements Documents
├── src/                         # Source code
│   ├── data/                    # Data fetching and management
│   ├── indicators/              # Technical indicator calculations
│   ├── screening/               # Universe screening and scoring
│   ├── regime/                  # Market regime analysis
│   ├── execution/               # Order execution and tracking
│   ├── dashboard/               # Real-time web dashboard
│   ├── pipeline/                # Data pipeline orchestration
│   └── main.py                  # Main system entry point
├── config/                      # Configuration files
├── tests/                       # Test suite
├── scripts/                     # Utility scripts
└── data/                        # Data storage (gitignored)
```

---

## 📊 Key Features

### SABR20 Scoring System
Proprietary 0-100 point scoring across 6 components:
1. **Setup Strength** (30 pts) - Multi-timeframe alignment
2. **Bottom Phase** (22 pts) - Consolidation quality
3. **Accumulation Intensity** (18 pts) - Institutional buying signals
4. **Trend Momentum** (18 pts) - Breakout potential
5. **Risk/Reward** (10 pts) - Setup quality
6. **Volume Profile** (2 pts) - Confirmation

### Risk Management
- Max 1% risk per trade
- Max 3% total portfolio risk
- Automatic position sizing
- Regime-based adjustments
- Trailing stops

### Real-Time Dashboard
- Live watchlist with scores
- Multi-timeframe charts
- Position tracking
- Market regime indicators
- Performance analytics

---

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific module
pytest tests/test_indicators.py -v
```

### Test Requirements
- Unit test coverage >80%
- All indicator calculations verified
- Integration tests for full pipeline
- Performance tests (<30s for 1000 symbols)
- Paper trading validation (1 week minimum)

---

## 📈 Performance Targets

### System Performance
- Screen 1000 symbols in <30 seconds
- Dashboard updates in <500ms
- Database queries <100ms average
- 99.5% uptime during market hours

### Trading Performance (Paper Trading Targets)
- Win rate: 45-60%
- Average R-multiple: >1.5
- Profit factor: >1.5
- Max drawdown: <15%

---

## ⚠️ Risk Disclaimer

**IMPORTANT**: This is a technical specification for educational purposes.

Trading stocks involves substantial risk of loss. Past performance does not guarantee future results. This system is provided as-is with no warranty of profitability.

**Always:**
- Start with paper trading
- Use proper position sizing
- Maintain appropriate stop losses
- Monitor system health continuously
- Have manual override procedures
- Never risk more than you can afford to lose

---

## 🔄 Development Workflow

### Core Development Rules
1. **R1 Truthfulness**: Never guess; ask targeted questions
2. **R2 Completeness**: End-to-end code/docs/tests; zero placeholders
3. **R3 State Safety**: Checkpoint after each phase for continuation
4. **R4 Minimal Files**: Only necessary artifacts; keep docs current
5. **R5 Token Constraints**: Never shorten objectives; use R3 for continuation

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for detailed rules and workflow.

---

## 📝 Implementation Status

- [x] PRD Documentation Complete
- [x] Implementation Guide Created
- [x] CLAUDE.md Project Instructions Created
- [x] TODO.md Progress Tracker Created
- [ ] Phase 1: Project Setup
- [ ] Phase 2: Data Infrastructure
- [ ] Phase 3: Screening & Scoring
- [ ] Phase 4: Regime Analysis
- [ ] Phase 5: Dashboard
- [ ] Phase 6: Execution Engine
- [ ] Phase 7: System Integration
- [ ] Phase 8: Production Ready

See [TODO.md](TODO.md) for detailed progress tracking.

---

## 🤝 Contributing

This is a personal project. Modifications should:
1. Follow the 5 core development rules
2. Maintain >80% test coverage
3. Update documentation
4. Pass all existing tests
5. Include comprehensive docstrings

---

## 📞 Support

**Documentation**: See `/PRD/` for complete specifications
**Implementation**: See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
**Progress**: See [TODO.md](TODO.md)
**Issues**: Document in GitHub Issues

---

## 📜 License

Private project - All rights reserved

---

## 🔗 External Resources

- [Interactive Brokers API](https://interactivebrokers.github.io/tws-api/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [TA-Lib Documentation](https://ta-lib.org/)
- [Dash Documentation](https://dash.plotly.com/)
- [Pandas Documentation](https://pandas.pydata.org/)

---

**Built with rigorous engineering standards for professional algorithmic trading.**
