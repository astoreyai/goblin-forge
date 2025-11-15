"""
SABR20 Scoring Engine

Proprietary 6-component scoring system (0-100 points) for identifying
mean-reversion-to-trend-expansion setups.

SABR20 Components:
------------------
1. Setup Strength (0-20 pts):
   - BB position (lower = better)
   - Stoch RSI oversold signals

2. Bottom Phase (0-16 pts):
   - Stoch RSI in oversold zone (< 20)
   - RSI showing recovery signs

3. Accumulation Intensity (0-18 pts):
   - Novel Stoch/RSI signal frequency ratio
   - Detects institutional accumulation
   - Early/Mid/Late/Breakout phases

4. Trend Momentum (0-16 pts):
   - MACD histogram rising (positive momentum)
   - Price above key moving averages

5. Risk/Reward (0-20 pts):
   - Entry price vs BB upper band (target)
   - Stop loss distance (BB lower or recent low)
   - Minimum 2:1 reward:risk ratio

6. Macro Confirmation (0-10 pts):
   - Higher timeframe alignment (4h, 1d)
   - Regime compatibility

Total: 100 points maximum

Scoring Thresholds:
-------------------
- 80-100 pts: Excellent setup (top tier)
- 65-79 pts: Strong setup (high probability)
- 50-64 pts: Good setup (moderate probability)
- < 50 pts: Weak setup (skip)

Usage:
------
from src.screening.sabr20_engine import sabr20_engine

# Score a single symbol
score = sabr20_engine.score_symbol(
    symbol='AAPL',
    data_15m=df_15m,
    data_1h=df_1h,
    data_4h=df_4h
)

print(f"SABR20 Score: {score.total_points} / 100")
print(f"Components: {score.component_scores}")
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import numpy as np
from loguru import logger

from src.config import config
from src.indicators.accumulation_analysis import accumulation_analyzer


@dataclass
class SABR20Score:
    """
    SABR20 score result.

    Attributes:
    -----------
    symbol : str
        Stock symbol
    total_points : float
        Total score (0-100)
    component_scores : dict
        Individual component scores
    setup_grade : str
        Setup quality grade (Excellent/Strong/Good/Weak)
    timestamp : datetime
        Scoring timestamp
    details : dict
        Detailed breakdown for each component
    """
    symbol: str
    total_points: float
    component_scores: Dict[str, float] = field(default_factory=dict)
    setup_grade: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Assign grade based on total points."""
        if self.total_points >= 80:
            self.setup_grade = "Excellent"
        elif self.total_points >= 65:
            self.setup_grade = "Strong"
        elif self.total_points >= 50:
            self.setup_grade = "Good"
        else:
            self.setup_grade = "Weak"


class SABR20Engine:
    """
    SABR20 scoring engine.

    Calculates proprietary 6-component score for mean-reversion setups.

    Attributes:
    -----------
    weights : dict
        Component weights (loaded from config)
    max_points : dict
        Maximum points per component
    """

    def __init__(self):
        """Initialize SABR20 engine with configuration."""
        # Load configuration
        self.weights = config.sabr20.weights
        self.max_points = config.sabr20.max_points

        # Verify total max points = 100
        total_max = sum(self.max_points.values())
        if total_max != 100:
            logger.warning(f"SABR20 max points sum to {total_max}, expected 100")

        logger.info("SABR20 scoring engine initialized")

    def component_1_setup_strength(
        self,
        df_trigger: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Component 1: Setup Strength (0-20 points).

        Measures how well-positioned the setup is for mean reversion.

        Scoring:
        --------
        - BB Position (0-10 pts):
          * 0-10%: 10 points (deep oversold)
          * 10-20%: 7 points
          * 20-30%: 4 points
          * >30%: 0 points

        - Stoch RSI Oversold (0-10 pts):
          * < 10: 10 points (extreme oversold)
          * 10-15: 7 points
          * 15-20: 4 points
          * > 20: 0 points

        Parameters:
        -----------
        df_trigger : pd.DataFrame
            Trigger timeframe data with indicators

        Returns:
        --------
        dict
            {'points': float, 'bb_position': float, 'stoch_rsi': float}
        """
        if df_trigger is None or df_trigger.empty:
            return {'points': 0, 'bb_position': None, 'stoch_rsi': None}

        latest = df_trigger.iloc[-1]

        # BB Position scoring
        bb_pos = latest.get('bb_position', 1.0)
        if pd.isna(bb_pos):
            bb_points = 0
        elif bb_pos <= 0.10:
            bb_points = 10
        elif bb_pos <= 0.20:
            bb_points = 7
        elif bb_pos <= 0.30:
            bb_points = 4
        else:
            bb_points = 0

        # Stoch RSI scoring
        stoch_rsi = latest.get('stoch_rsi', 100)
        if pd.isna(stoch_rsi):
            stoch_points = 0
        elif stoch_rsi < 10:
            stoch_points = 10
        elif stoch_rsi < 15:
            stoch_points = 7
        elif stoch_rsi < 20:
            stoch_points = 4
        else:
            stoch_points = 0

        total_points = bb_points + stoch_points

        return {
            'points': total_points,
            'bb_position': float(bb_pos) if not pd.isna(bb_pos) else None,
            'bb_points': bb_points,
            'stoch_rsi': float(stoch_rsi) if not pd.isna(stoch_rsi) else None,
            'stoch_points': stoch_points
        }

    def component_2_bottom_phase(
        self,
        df_trigger: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Component 2: Bottom Phase (0-16 points).

        Identifies if price is forming a bottom (oversold + recovery signs).

        Scoring:
        --------
        - Stoch RSI Oversold (0-8 pts):
          * < 20: 8 points
          * 20-30: 4 points
          * > 30: 0 points

        - RSI Recovery (0-8 pts):
          * RSI < 30 but rising: 8 points (strong recovery)
          * RSI 30-40 and rising: 5 points
          * RSI > 40 or falling: 0 points

        Parameters:
        -----------
        df_trigger : pd.DataFrame
            Trigger timeframe data with indicators

        Returns:
        --------
        dict
            {'points': float, 'stoch_oversold': bool, 'rsi_recovery': bool}
        """
        if df_trigger is None or len(df_trigger) < 2:
            return {'points': 0, 'stoch_oversold': False, 'rsi_recovery': False}

        latest = df_trigger.iloc[-1]
        prev = df_trigger.iloc[-2]

        # Stoch RSI oversold
        stoch_rsi = latest.get('stoch_rsi', 100)
        if pd.isna(stoch_rsi):
            stoch_points = 0
        elif stoch_rsi < 20:
            stoch_points = 8
        elif stoch_rsi < 30:
            stoch_points = 4
        else:
            stoch_points = 0

        # RSI recovery
        rsi = latest.get('rsi', 50)
        rsi_prev = prev.get('rsi', 50)

        if pd.isna(rsi) or pd.isna(rsi_prev):
            rsi_points = 0
        else:
            rsi_rising = rsi > rsi_prev

            if rsi < 30 and rsi_rising:
                rsi_points = 8  # Strong recovery from oversold
            elif 30 <= rsi < 40 and rsi_rising:
                rsi_points = 5  # Moderate recovery
            else:
                rsi_points = 0

        total_points = stoch_points + rsi_points

        return {
            'points': total_points,
            'stoch_oversold': stoch_rsi < 20 if not pd.isna(stoch_rsi) else False,
            'stoch_points': stoch_points,
            'rsi': float(rsi) if not pd.isna(rsi) else None,
            'rsi_rising': rsi > rsi_prev if not pd.isna(rsi) and not pd.isna(rsi_prev) else False,
            'rsi_points': rsi_points
        }

    def component_3_accumulation_intensity(
        self,
        df_trigger: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Component 3: Accumulation Intensity (0-18 points).

        Novel component using Stoch/RSI signal frequency ratio.
        Detects institutional accumulation patterns.

        Scoring:
        --------
        - Early Accumulation: 18 points (ratio > 5.0, RSI < 45)
        - Mid Accumulation: 14 points (ratio 3.0-5.0, RSI < 50)
        - Late Accumulation: 10 points (ratio 1.5-3.0, RSI 40-55)
        - Breakout: 6 points (ratio 0.8-1.5, RSI > 50)
        - None: 0 points

        Parameters:
        -----------
        df_trigger : pd.DataFrame
            Trigger timeframe data with indicators

        Returns:
        --------
        dict
            {'points': float, 'phase': str, 'ratio': float, ...}
        """
        if df_trigger is None or df_trigger.empty:
            return {'points': 0, 'phase': 'none', 'ratio': 0}

        # Use accumulation analyzer
        result = accumulation_analyzer.analyze(df_trigger)

        return {
            'points': result['points'],
            'phase': result['phase'],
            'ratio': result['ratio'],
            'description': result['description']
        }

    def component_4_trend_momentum(
        self,
        df_confirmation: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Component 4: Trend Momentum (0-16 points).

        Measures if momentum is building (MACD histogram rising).

        Scoring:
        --------
        - MACD Histogram Rising (0-10 pts):
          * 3+ bars rising: 10 points (strong momentum build)
          * 2 bars rising: 6 points
          * 1 bar rising: 3 points
          * Falling: 0 points

        - MACD Position (0-6 pts):
          * MACD > Signal (bullish crossover): 6 points
          * MACD approaching Signal: 3 points
          * MACD < Signal and diverging: 0 points

        Parameters:
        -----------
        df_confirmation : pd.DataFrame
            Confirmation timeframe data with indicators

        Returns:
        --------
        dict
            {'points': float, 'histogram_rising': bool, 'macd_bullish': bool}
        """
        if df_confirmation is None or len(df_confirmation) < 4:
            return {'points': 0, 'histogram_rising': False, 'macd_bullish': False}

        # Get last 4 bars
        recent = df_confirmation.tail(4)
        macd_hist = recent['macd_hist'].values

        # Check for rising histogram
        if any(pd.isna(macd_hist)):
            hist_points = 0
            rising_count = 0
        else:
            rising_count = 0
            for i in range(1, len(macd_hist)):
                if macd_hist[i] > macd_hist[i-1]:
                    rising_count += 1
                else:
                    break  # Stop on first non-rising bar

            if rising_count >= 3:
                hist_points = 10
            elif rising_count == 2:
                hist_points = 6
            elif rising_count == 1:
                hist_points = 3
            else:
                hist_points = 0

        # MACD position
        latest = df_confirmation.iloc[-1]
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)

        if pd.isna(macd) or pd.isna(macd_signal):
            macd_points = 0
            macd_bullish = False
        else:
            if macd > macd_signal:
                macd_points = 6  # Bullish crossover
                macd_bullish = True
            elif macd > macd_signal * 0.95:  # Within 5%
                macd_points = 3  # Approaching crossover
                macd_bullish = False
            else:
                macd_points = 0
                macd_bullish = False

        total_points = hist_points + macd_points

        return {
            'points': total_points,
            'histogram_rising': rising_count > 0,
            'rising_count': rising_count,
            'hist_points': hist_points,
            'macd_bullish': macd_bullish,
            'macd_points': macd_points
        }

    def component_5_risk_reward(
        self,
        df_trigger: pd.DataFrame,
        entry_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Component 5: Risk/Reward Ratio (0-20 points).

        Calculates reward:risk ratio for trade.

        Scoring:
        --------
        - R:R >= 4.0: 20 points (excellent)
        - R:R 3.0-4.0: 16 points (very good)
        - R:R 2.5-3.0: 12 points (good)
        - R:R 2.0-2.5: 8 points (acceptable)
        - R:R < 2.0: 0 points (reject)

        Calculation:
        ------------
        - Entry: Current price or specified
        - Target: BB upper band (mean reversion target)
        - Stop: BB lower band or recent swing low (whichever is closer)

        Parameters:
        -----------
        df_trigger : pd.DataFrame
            Trigger timeframe data with indicators
        entry_price : float, optional
            Entry price. If None, uses latest close.

        Returns:
        --------
        dict
            {'points': float, 'rr_ratio': float, 'reward': float, 'risk': float}
        """
        if df_trigger is None or df_trigger.empty:
            return {'points': 0, 'rr_ratio': 0, 'reward': 0, 'risk': 0}

        latest = df_trigger.iloc[-1]

        # Entry price
        if entry_price is None:
            entry_price = latest.get('close')

        if pd.isna(entry_price):
            return {'points': 0, 'rr_ratio': 0, 'reward': 0, 'risk': 0}

        # Target: BB upper band
        target = latest.get('bb_upper')
        if pd.isna(target):
            return {'points': 0, 'rr_ratio': 0, 'reward': 0, 'risk': 0}

        # Stop: BB lower band
        stop = latest.get('bb_lower')
        if pd.isna(stop):
            return {'points': 0, 'rr_ratio': 0, 'reward': 0, 'risk': 0}

        # Calculate reward and risk
        reward = target - entry_price
        risk = entry_price - stop

        if risk <= 0:
            return {'points': 0, 'rr_ratio': 0, 'reward': 0, 'risk': 0}

        rr_ratio = reward / risk

        # Score based on R:R
        if rr_ratio >= 4.0:
            points = 20
        elif rr_ratio >= 3.0:
            points = 16
        elif rr_ratio >= 2.5:
            points = 12
        elif rr_ratio >= 2.0:
            points = 8
        else:
            points = 0  # Reject trades with R:R < 2.0

        return {
            'points': points,
            'rr_ratio': float(rr_ratio),
            'reward': float(reward),
            'risk': float(risk),
            'entry': float(entry_price),
            'target': float(target),
            'stop': float(stop)
        }

    def component_6_macro_confirmation(
        self,
        df_regime: pd.DataFrame,
        df_macro: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Component 6: Macro Confirmation (0-10 points).

        Checks if higher timeframes support the setup.

        Scoring:
        --------
        - 4h Timeframe (0-6 pts):
          * Price > BB middle: 3 points (bullish regime)
          * RSI 40-60 (neutral): 3 points (not overbought)

        - Daily Timeframe (0-4 pts):
          * Uptrend (close > SMA20): 4 points
          * Sideways: 2 points
          * Downtrend: 0 points

        Parameters:
        -----------
        df_regime : pd.DataFrame
            Regime timeframe data (4h) with indicators
        df_macro : pd.DataFrame, optional
            Macro timeframe data (daily) with indicators

        Returns:
        --------
        dict
            {'points': float, 'regime_aligned': bool, 'macro_bullish': bool}
        """
        points = 0
        details = {}

        # 4h regime timeframe
        if df_regime is not None and not df_regime.empty:
            latest_4h = df_regime.iloc[-1]

            # Price vs BB middle
            close = latest_4h.get('close')
            bb_middle = latest_4h.get('bb_middle')

            if not pd.isna(close) and not pd.isna(bb_middle):
                if close > bb_middle:
                    points += 3
                    details['regime_bullish'] = True
                else:
                    details['regime_bullish'] = False

            # RSI neutral zone
            rsi = latest_4h.get('rsi', 50)
            if not pd.isna(rsi):
                if 40 <= rsi <= 60:
                    points += 3
                    details['rsi_neutral'] = True
                else:
                    details['rsi_neutral'] = False

        # Daily macro timeframe (if available)
        if df_macro is not None and not df_macro.empty and len(df_macro) >= 20:
            latest_daily = df_macro.iloc[-1]

            # Calculate SMA20
            sma20 = df_macro['close'].tail(20).mean()
            close_daily = latest_daily.get('close')

            if not pd.isna(sma20) and not pd.isna(close_daily):
                if close_daily > sma20:
                    points += 4  # Uptrend
                    details['macro_bullish'] = True
                elif close_daily > sma20 * 0.98:
                    points += 2  # Sideways
                    details['macro_bullish'] = False
                else:
                    details['macro_bullish'] = False

        details['points'] = points
        return details

    def score_symbol(
        self,
        symbol: str,
        data_trigger: pd.DataFrame,
        data_confirmation: pd.DataFrame,
        data_regime: pd.DataFrame,
        data_macro: Optional[pd.DataFrame] = None
    ) -> SABR20Score:
        """
        Calculate complete SABR20 score for a symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        data_trigger : pd.DataFrame
            Trigger timeframe data (15m with indicators)
        data_confirmation : pd.DataFrame
            Confirmation timeframe data (1h with indicators)
        data_regime : pd.DataFrame
            Regime timeframe data (4h with indicators)
        data_macro : pd.DataFrame, optional
            Macro timeframe data (daily with indicators)

        Returns:
        --------
        SABR20Score
            Complete scoring result

        Examples:
        ---------
        >>> score = sabr20_engine.score_symbol(
        ...     symbol='AAPL',
        ...     data_trigger=df_15m,
        ...     data_confirmation=df_1h,
        ...     data_regime=df_4h
        ... )
        >>> print(f"Score: {score.total_points}/100 - {score.setup_grade}")
        """
        try:
            component_scores = {}
            details = {}

            # Component 1: Setup Strength
            c1 = self.component_1_setup_strength(data_trigger)
            component_scores['setup_strength'] = c1['points']
            details['setup_strength'] = c1

            # Component 2: Bottom Phase
            c2 = self.component_2_bottom_phase(data_trigger)
            component_scores['bottom_phase'] = c2['points']
            details['bottom_phase'] = c2

            # Component 3: Accumulation Intensity
            c3 = self.component_3_accumulation_intensity(data_trigger)
            component_scores['accumulation_intensity'] = c3['points']
            details['accumulation_intensity'] = c3

            # Component 4: Trend Momentum
            c4 = self.component_4_trend_momentum(data_confirmation)
            component_scores['trend_momentum'] = c4['points']
            details['trend_momentum'] = c4

            # Component 5: Risk/Reward
            c5 = self.component_5_risk_reward(data_trigger)
            component_scores['risk_reward'] = c5['points']
            details['risk_reward'] = c5

            # Component 6: Macro Confirmation
            c6 = self.component_6_macro_confirmation(data_regime, data_macro)
            component_scores['macro_confirmation'] = c6['points']
            details['macro_confirmation'] = c6

            # Calculate total
            total_points = sum(component_scores.values())

            # Create score object
            score = SABR20Score(
                symbol=symbol,
                total_points=total_points,
                component_scores=component_scores,
                details=details
            )

            logger.debug(
                f"{symbol}: SABR20={total_points:.1f} ({score.setup_grade}) - "
                f"Components: {component_scores}"
            )

            return score

        except Exception as e:
            logger.error(f"Error scoring {symbol}: {e}")
            # Return empty score
            return SABR20Score(
                symbol=symbol,
                total_points=0,
                component_scores={},
                details={'error': str(e)}
            )


# Global singleton instance
sabr20_engine = SABR20Engine()
