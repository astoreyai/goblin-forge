"""
Real-Time Screening Dashboard

Dash-based web application for monitoring screening results and market regime.

Features:
---------
- Real-time watchlist table with SABR20 scores
- Market regime indicator
- Component score breakdown
- Multi-timeframe charts
- Auto-refresh every 5 minutes
- Entry/target/stop visualization

Pages:
------
1. Watchlist: Top setups ranked by SABR20 score
2. Setup Details: Individual symbol analysis
3. Market Regime: Current market conditions

Run:
----
python src/dashboard/app.py

Then navigate to http://localhost:8050
"""

import os
from datetime import datetime
from typing import List, Dict, Any

import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from loguru import logger

from src.config import config
from src.screening.watchlist import watchlist_generator
from src.regime.regime_detector import regime_detector, RegimeType
from src.data.historical_manager import historical_manager


# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

app.title = "Screener Dashboard"

# Global state
watchlist_cache = {
    'data': [],
    'timestamp': None
}


def create_header():
    """Create dashboard header."""
    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col(html.H3("📊 Screener Dashboard", className="text-white mb-0")),
                dbc.Col(
                    html.Div(id='live-clock', className="text-white text-end"),
                    width="auto"
                )
            ], align="center", className="w-100")
        ]),
        color="dark",
        dark=True,
        className="mb-4"
    )


def create_regime_card(regime_data: Dict[str, Any]) -> dbc.Card:
    """Create market regime indicator card."""
    regime_type = regime_data.get('type_str', 'unknown')
    confidence = regime_data.get('confidence', 0)
    recommendation = regime_data.get('recommendation', {})

    # Color based on regime
    regime_colors = {
        'ranging': 'success',
        'trending_bullish': 'info',
        'trending_bearish': 'warning',
        'volatile': 'danger',
        'unknown': 'secondary'
    }
    color = regime_colors.get(regime_type, 'secondary')

    return dbc.Card([
        dbc.CardHeader(html.H5("Market Regime", className="mb-0")),
        dbc.CardBody([
            html.H3(
                regime_type.replace('_', ' ').title(),
                className=f"text-{color}"
            ),
            html.P(f"Confidence: {confidence:.0%}", className="text-muted mb-2"),
            html.Hr(),
            html.P([
                html.Strong("Strategy Fit: "),
                recommendation.get('strategy_suitability', 'unknown').title()
            ], className="mb-1"),
            html.P([
                html.Strong("Position Sizing: "),
                recommendation.get('position_sizing', 'unknown').title()
            ], className="mb-1"),
            html.P(
                recommendation.get('notes', ''),
                className="text-muted small"
            )
        ])
    ], className="mb-4")


def create_watchlist_table(watchlist: List) -> dash_table.DataTable:
    """Create watchlist data table."""
    if not watchlist:
        return html.Div("No setups found", className="text-muted")

    # Convert to DataFrame
    df = watchlist_generator.get_watchlist_summary(watchlist)

    # Format for display
    df['score'] = df['score'].round(1)
    if 'entry' in df.columns:
        df['entry'] = df['entry'].round(2)
    if 'target' in df.columns:
        df['target'] = df['target'].round(2)
    if 'stop' in df.columns:
        df['stop'] = df['stop'].round(2)
    if 'rr_ratio' in df.columns:
        df['rr_ratio'] = df['rr_ratio'].round(2)

    columns = [
        {'name': 'Symbol', 'id': 'symbol'},
        {'name': 'Score', 'id': 'score'},
        {'name': 'Grade', 'id': 'grade'},
        {'name': 'Setup', 'id': 'setup_strength'},
        {'name': 'Bottom', 'id': 'bottom_phase'},
        {'name': 'Accum', 'id': 'accumulation'},
        {'name': 'Momentum', 'id': 'trend_momentum'},
        {'name': 'R:R', 'id': 'risk_reward'},
        {'name': 'Macro', 'id': 'macro'},
        {'name': 'Entry', 'id': 'entry'},
        {'name': 'Target', 'id': 'target'},
        {'name': 'Stop', 'id': 'stop'},
        {'name': 'R:R Ratio', 'id': 'rr_ratio'},
    ]

    return dash_table.DataTable(
        data=df.to_dict('records'),
        columns=columns,
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'fontSize': '14px'
        },
        style_header={
            'backgroundColor': '#343a40',
            'color': 'white',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {
                'if': {'filter_query': '{grade} = "Excellent"'},
                'backgroundColor': '#d4edda',
                'color': '#155724'
            },
            {
                'if': {'filter_query': '{grade} = "Strong"'},
                'backgroundColor': '#d1ecf1',
                'color': '#0c5460'
            },
            {
                'if': {'filter_query': '{grade} = "Good"'},
                'backgroundColor': '#fff3cd',
                'color': '#856404'
            }
        ],
        sort_action='native',
        filter_action='native',
        page_size=20
    )


# Layout
app.layout = html.Div([
    create_header(),

    dbc.Container([
        # Control row
        dbc.Row([
            dbc.Col([
                dbc.Button(
                    "🔄 Refresh Watchlist",
                    id="refresh-button",
                    color="primary",
                    className="me-2"
                ),
                dbc.Button(
                    "⚙️ Settings",
                    id="settings-button",
                    color="secondary",
                    className="me-2"
                ),
                html.Span(id="last-update", className="text-muted ms-3")
            ], width=12, className="mb-3")
        ]),

        # Main content row
        dbc.Row([
            # Left column: Regime + Stats
            dbc.Col([
                html.Div(id='regime-card'),
                dbc.Card([
                    dbc.CardHeader(html.H5("Statistics", className="mb-0")),
                    dbc.CardBody(id='stats-content')
                ])
            ], width=3),

            # Right column: Watchlist
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Watchlist", className="mb-0")),
                    dbc.CardBody(id='watchlist-content')
                ])
            ], width=9)
        ]),

        # Hidden interval for auto-refresh
        dcc.Interval(
            id='interval-component',
            interval=5*60*1000,  # 5 minutes in milliseconds
            n_intervals=0
        ),

        # Hidden interval for clock
        dcc.Interval(
            id='clock-interval',
            interval=1000,  # 1 second
            n_intervals=0
        )
    ], fluid=True)
])


@app.callback(
    Output('live-clock', 'children'),
    Input('clock-interval', 'n_intervals')
)
def update_clock(n):
    """Update live clock."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.callback(
    [Output('regime-card', 'children'),
     Output('watchlist-content', 'children'),
     Output('stats-content', 'children'),
     Output('last-update', 'children')],
    [Input('refresh-button', 'n_clicks'),
     Input('interval-component', 'n_intervals')]
)
def update_dashboard(n_clicks, n_intervals):
    """Update dashboard with fresh data."""
    try:
        logger.info("Updating dashboard...")

        # Detect regime
        regime_data = regime_detector.detect_regime()
        regime_card = create_regime_card(regime_data)

        # Generate watchlist
        watchlist = watchlist_generator.generate(
            max_symbols=20,
            min_score=50.0
        )

        # Update cache
        watchlist_cache['data'] = watchlist
        watchlist_cache['timestamp'] = datetime.now()

        # Create watchlist table
        watchlist_table = create_watchlist_table(watchlist)

        # Statistics
        stats = html.Div([
            html.P([
                html.Strong("Setups Found: "),
                str(len(watchlist))
            ], className="mb-2"),
            html.P([
                html.Strong("Avg Score: "),
                f"{sum(s.total_points for s in watchlist) / len(watchlist):.1f}" if watchlist else "N/A"
            ], className="mb-2"),
            html.P([
                html.Strong("Top Grade: "),
                watchlist[0].setup_grade if watchlist else "N/A"
            ], className="mb-2")
        ])

        last_update = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"

        return regime_card, watchlist_table, stats, last_update

    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
        error_msg = html.Div(f"Error: {str(e)}", className="text-danger")
        return error_msg, error_msg, error_msg, "Error"


if __name__ == '__main__':
    logger.info("Starting Screener Dashboard...")
    logger.info("Navigate to: http://localhost:8050")

    # Run server
    app.run_server(
        debug=config.get('dashboard.debug', True),
        host='0.0.0.0',
        port=8050
    )
