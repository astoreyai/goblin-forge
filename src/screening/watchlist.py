"""
Watchlist Generation

Orchestrates the complete screening pipeline to generate ranked watchlist.

Pipeline Flow:
--------------
1. Universe Construction → 500-1000 symbols
2. Coarse Screening (1h) → ~50-100 candidates
3. Fine Screening (multi-timeframe SABR20) → ~10-30 scored setups
4. Ranking & Watchlist → Top 10-20 best setups

Output:
-------
Ranked watchlist with:
- Symbol
- SABR20 score (0-100)
- Setup grade (Excellent/Strong/Good)
- Component breakdown
- Entry/target/stop prices
- Risk/reward ratio

Usage:
------
from src.screening.watchlist import watchlist_generator

# Generate watchlist
watchlist = watchlist_generator.generate(
    max_symbols=20,
    min_score=50.0
)

# Display
for setup in watchlist:
    print(f"{setup.symbol}: {setup.total_points}/100 ({setup.setup_grade})")
    print(f"  Entry: ${setup.details['risk_reward']['entry']:.2f}")
    print(f"  Target: ${setup.details['risk_reward']['target']:.2f}")
    print(f"  R:R: {setup.details['risk_reward']['rr_ratio']:.1f}:1")
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from loguru import logger

from src.config import config
from src.screening.universe import universe_manager
from src.screening.coarse_filter import coarse_filter
from src.screening.sabr20_engine import sabr20_engine, SABR20Score
from src.data.historical_manager import historical_manager
from src.data.ib_manager import ib_manager
from src.indicators.indicator_engine import indicator_engine


class WatchlistGenerator:
    """
    Watchlist generation orchestrator.

    Runs complete screening pipeline from universe to ranked watchlist.

    Attributes:
    -----------
    timeframes : dict
        Active timeframe profile from configuration
    max_watchlist_size : int
        Maximum watchlist symbols
    min_score_threshold : float
        Minimum SABR20 score for inclusion
    """

    def __init__(self):
        """Initialize watchlist generator with configuration."""
        # Load active timeframe profile
        timeframe_config = config.timeframes
        active_profile = timeframe_config.active_profile
        profile = timeframe_config.profiles[active_profile]

        self.timeframes = {
            'trigger': profile['trigger'],
            'confirmation': profile['confirmation'],
            'regime': profile['regime'],
            'macro': profile['macro']
        }

        # Watchlist parameters
        self.max_watchlist_size = config.screening.max_watchlist_size
        self.min_score_threshold = config.screening.min_score_threshold

        logger.info(
            f"Watchlist generator initialized: {active_profile} profile, "
            f"timeframes={self.timeframes}"
        )

    def load_multi_timeframe_data(
        self,
        symbol: str,
        use_cached: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Load and calculate indicators for all timeframes.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        use_cached : bool, default=True
            If True, uses historical data from disk. If False, fetches live.

        Returns:
        --------
        dict
            {timeframe_name: df_with_indicators}
            Keys: 'trigger', 'confirmation', 'regime', 'macro'

        Examples:
        ---------
        >>> data = watchlist_generator.load_multi_timeframe_data('AAPL')
        >>> df_15m = data['trigger']
        >>> df_1h = data['confirmation']
        """
        data = {}

        for tf_name, tf_value in self.timeframes.items():
            try:
                # Load data
                if use_cached:
                    df = historical_manager.load(symbol, tf_value)
                else:
                    # Determine duration based on timeframe
                    if '1 day' in tf_value or '1 week' in tf_value:
                        duration = '1 Y'
                    elif '4 hours' in tf_value:
                        duration = '1 M'
                    elif '1 hour' in tf_value:
                        duration = '2 W'
                    else:
                        duration = '5 D'

                    df = ib_manager.fetch_historical_bars(
                        symbol=symbol,
                        bar_size=tf_value,
                        duration=duration
                    )

                if df is None or df.empty:
                    logger.debug(f"No data for {symbol} {tf_value}")
                    continue

                # Calculate indicators
                df = indicator_engine.calculate_all(df, symbol=symbol)

                if df is not None:
                    data[tf_name] = df

            except Exception as e:
                logger.debug(f"Error loading {symbol} {tf_value}: {e}")
                continue

        return data

    def score_candidate(
        self,
        symbol: str,
        use_cached_data: bool = True
    ) -> Optional[SABR20Score]:
        """
        Score a single candidate symbol.

        Parameters:
        -----------
        symbol : str
            Stock symbol
        use_cached_data : bool, default=True
            Use cached historical data

        Returns:
        --------
        SABR20Score or None
            Score result, or None if insufficient data
        """
        try:
            # Load multi-timeframe data
            data = self.load_multi_timeframe_data(symbol, use_cached=use_cached_data)

            # Check if we have minimum required data
            required_timeframes = ['trigger', 'confirmation', 'regime']
            if not all(tf in data for tf in required_timeframes):
                logger.debug(
                    f"Insufficient data for {symbol}, missing: "
                    f"{set(required_timeframes) - set(data.keys())}"
                )
                return None

            # Score symbol
            score = sabr20_engine.score_symbol(
                symbol=symbol,
                data_trigger=data['trigger'],
                data_confirmation=data['confirmation'],
                data_regime=data['regime'],
                data_macro=data.get('macro')  # Optional
            )

            return score

        except Exception as e:
            logger.error(f"Error scoring candidate {symbol}: {e}")
            return None

    def score_candidates_parallel(
        self,
        candidates: List[str],
        max_workers: int = 4
    ) -> List[SABR20Score]:
        """
        Score multiple candidates in parallel.

        Parameters:
        -----------
        candidates : list of str
            Candidate symbols to score
        max_workers : int, default=4
            Maximum parallel workers

        Returns:
        --------
        list of SABR20Score
            Scored results (excluding None values)
        """
        scores = []

        logger.info(f"Scoring {len(candidates)} candidates...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scoring tasks
            future_to_symbol = {
                executor.submit(self.score_candidate, symbol): symbol
                for symbol in candidates
            }

            # Collect results as they complete
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    score = future.result()
                    if score is not None:
                        scores.append(score)
                        logger.debug(
                            f"Scored {symbol}: {score.total_points:.1f} ({score.setup_grade})"
                        )
                except Exception as e:
                    logger.error(f"Error getting score for {symbol}: {e}")

        logger.info(f"Scored {len(scores)} / {len(candidates)} candidates")

        return scores

    def generate(
        self,
        universe: Optional[List[str]] = None,
        max_symbols: Optional[int] = None,
        min_score: Optional[float] = None,
        skip_coarse_filter: bool = False
    ) -> List[SABR20Score]:
        """
        Generate complete watchlist.

        This is the main method that runs the full screening pipeline.

        Parameters:
        -----------
        universe : list of str, optional
            Custom universe. If None, builds from config sources.
        max_symbols : int, optional
            Maximum watchlist size. If None, uses config default.
        min_score : float, optional
            Minimum SABR20 score. If None, uses config default.
        skip_coarse_filter : bool, default=False
            If True, skips coarse filter and scores entire universe.
            Warning: Much slower on large universes!

        Returns:
        --------
        list of SABR20Score
            Ranked watchlist (best to worst)

        Examples:
        ---------
        >>> # Standard watchlist generation
        >>> watchlist = watchlist_generator.generate()
        >>> for setup in watchlist[:10]:
        ...     print(f"{setup.symbol}: {setup.total_points}/100")

        >>> # Custom parameters
        >>> watchlist = watchlist_generator.generate(
        ...     universe=['AAPL', 'MSFT', 'TSLA'],
        ...     max_symbols=5,
        ...     min_score=65.0
        ... )
        """
        start_time = datetime.now()

        # Use defaults if not specified
        if max_symbols is None:
            max_symbols = self.max_watchlist_size
        if min_score is None:
            min_score = self.min_score_threshold

        logger.info("=" * 60)
        logger.info("WATCHLIST GENERATION STARTED")
        logger.info(f"Max size: {max_symbols}, Min score: {min_score}")
        logger.info("=" * 60)

        # Step 1: Build universe
        if universe is None:
            logger.info("Step 1: Building universe...")
            universe = universe_manager.build_universe()
            logger.info(f"Universe: {len(universe)} symbols")
        else:
            logger.info(f"Step 1: Using custom universe: {len(universe)} symbols")

        # Step 2: Coarse filtering (optional)
        if skip_coarse_filter:
            logger.info("Step 2: Skipping coarse filter (scoring entire universe)")
            candidates = universe
        else:
            logger.info("Step 2: Coarse screening (1h filters)...")
            candidates = coarse_filter.screen(universe)
            logger.info(f"Candidates: {len(candidates)} symbols passed coarse filter")

        if not candidates:
            logger.warning("No candidates passed coarse filter!")
            return []

        # Step 3: SABR20 scoring
        logger.info("Step 3: SABR20 scoring (multi-timeframe analysis)...")
        scores = self.score_candidates_parallel(candidates)

        if not scores:
            logger.warning("No candidates scored successfully!")
            return []

        logger.info(f"Scored: {len(scores)} symbols")

        # Step 4: Filter by minimum score
        logger.info(f"Step 4: Filtering by minimum score ({min_score})...")
        qualified_scores = [s for s in scores if s.total_points >= min_score]
        logger.info(f"Qualified: {len(qualified_scores)} symbols above threshold")

        # Step 5: Rank and limit
        logger.info("Step 5: Ranking and creating watchlist...")
        watchlist = sorted(
            qualified_scores,
            key=lambda s: s.total_points,
            reverse=True
        )[:max_symbols]

        # Log results
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(f"WATCHLIST GENERATION COMPLETE ({duration:.1f}s)")
        logger.info(f"Final watchlist: {len(watchlist)} symbols")
        logger.info("=" * 60)

        if watchlist:
            logger.info("Top 5 setups:")
            for i, score in enumerate(watchlist[:5], 1):
                logger.info(
                    f"  {i}. {score.symbol}: {score.total_points:.1f}/100 "
                    f"({score.setup_grade})"
                )

        return watchlist

    def get_watchlist_summary(
        self,
        watchlist: List[SABR20Score]
    ) -> pd.DataFrame:
        """
        Get watchlist summary as DataFrame for display.

        Parameters:
        -----------
        watchlist : list of SABR20Score
            Watchlist to summarize

        Returns:
        --------
        pd.DataFrame
            Summary with columns: symbol, score, grade, entry, target, stop, rr_ratio

        Examples:
        ---------
        >>> watchlist = watchlist_generator.generate()
        >>> df = watchlist_generator.get_watchlist_summary(watchlist)
        >>> print(df.to_string())
        """
        rows = []

        for score in watchlist:
            rr_details = score.details.get('risk_reward', {})

            row = {
                'symbol': score.symbol,
                'score': score.total_points,
                'grade': score.setup_grade,
                'setup_strength': score.component_scores.get('setup_strength', 0),
                'bottom_phase': score.component_scores.get('bottom_phase', 0),
                'accumulation': score.component_scores.get('accumulation_intensity', 0),
                'trend_momentum': score.component_scores.get('trend_momentum', 0),
                'risk_reward': score.component_scores.get('risk_reward', 0),
                'macro': score.component_scores.get('macro_confirmation', 0),
                'entry': rr_details.get('entry'),
                'target': rr_details.get('target'),
                'stop': rr_details.get('stop'),
                'rr_ratio': rr_details.get('rr_ratio'),
                'timestamp': score.timestamp
            }

            rows.append(row)

        return pd.DataFrame(rows)

    def export_watchlist(
        self,
        watchlist: List[SABR20Score],
        filepath: str = 'data/watchlist.csv'
    ) -> bool:
        """
        Export watchlist to CSV file.

        Parameters:
        -----------
        watchlist : list of SABR20Score
            Watchlist to export
        filepath : str, default='data/watchlist.csv'
            Output file path

        Returns:
        --------
        bool
            True if export successful
        """
        try:
            df = self.get_watchlist_summary(watchlist)
            df.to_csv(filepath, index=False)
            logger.info(f"Exported watchlist to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error exporting watchlist: {e}")
            return False


# Global singleton instance
watchlist_generator = WatchlistGenerator()
