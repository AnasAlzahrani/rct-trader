"""Event study analysis for measuring abnormal returns around trial events."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from loguru import logger

from src.data_sources.market_data import get_market_data_client, MarketDataClient
from src.database.models import TrialEvent, EventStudy


@dataclass
class EventStudyResult:
    """Results of event study analysis."""
    event_id: int
    ticker: str
    event_date: datetime
    
    # Abnormal returns
    car_1day: float
    car_3day: float
    car_5day: float
    car_10day: float
    
    # Daily abnormal returns
    abnormal_returns: Dict[int, float]  # day -> return
    
    # Statistical significance
    t_stat: float
    p_value: float
    is_significant: bool
    
    # Market model parameters
    alpha: float
    beta: float
    r_squared: float
    
    # Raw data
    actual_returns: Dict[int, float]
    expected_returns: Dict[int, float]


class EventStudyAnalyzer:
    """Analyze abnormal returns around clinical trial events."""
    
    def __init__(self):
        self.market_client = get_market_data_client()
        self.estimation_window = 120  # Days for estimating market model
        self.event_window_pre = 5     # Days before event
        self.event_window_post = 10   # Days after event
    
    async def analyze_event(
        self,
        event: TrialEvent,
        ticker: str,
        benchmark: str = "XBI"
    ) -> Optional[EventStudyResult]:
        """Perform event study analysis for a single event."""
        try:
            if not event.event_date:
                logger.warning(f"Event {event.id} has no date")
                return None
            
            # Get price data
            event_date = event.event_date
            start_date = event_date - timedelta(days=self.estimation_window + 30)
            end_date = event_date + timedelta(days=self.event_window_post + 5)
            
            stock_prices = await self.market_client.get_price_history(
                ticker, start_date, end_date
            )
            benchmark_prices = await self.market_client.get_price_history(
                benchmark, start_date, end_date
            )
            
            if len(stock_prices) < self.estimation_window + self.event_window_post:
                logger.warning(f"Insufficient price data for {ticker}")
                return None
            
            if len(benchmark_prices) < self.estimation_window + self.event_window_post:
                logger.warning(f"Insufficient benchmark data for {benchmark}")
                return None
            
            # Calculate returns
            stock_returns = self._calculate_returns(stock_prices)
            benchmark_returns = self._calculate_returns(benchmark_prices)
            
            # Find event index
            event_idx = self._find_event_index(stock_prices, event_date)
            if event_idx is None:
                logger.warning(f"Could not find event date in price data")
                return None
            
            # Split into estimation and event windows
            est_start = max(0, event_idx - self.estimation_window - self.event_window_pre)
            est_end = event_idx - self.event_window_pre
            
            if est_end - est_start < 30:
                logger.warning(f"Insufficient estimation window")
                return None
            
            # Estimate market model
            alpha, beta, r_squared = self._estimate_market_model(
                stock_returns[est_start:est_end],
                benchmark_returns[est_start:est_end]
            )
            
            # Calculate abnormal returns in event window
            event_start = max(0, event_idx - self.event_window_pre)
            event_end = min(len(stock_returns), event_idx + self.event_window_post + 1)
            
            actual_event_returns = stock_returns[event_start:event_end]
            expected_event_returns = [
                alpha + beta * br
                for br in benchmark_returns[event_start:event_end]
            ]
            
            abnormal_returns = [
                actual - expected
                for actual, expected in zip(actual_event_returns, expected_event_returns)
            ]
            
            # Calculate CARs
            event_day_idx = event_idx - event_start
            
            car_1day = sum(abnormal_returns[event_day_idx-1:event_day_idx+1]) if event_day_idx >= 1 else 0
            car_3day = sum(abnormal_returns[max(0, event_day_idx-1):event_day_idx+3])
            car_5day = sum(abnormal_returns[max(0, event_day_idx-1):event_day_idx+5])
            car_10day = sum(abnormal_returns[max(0, event_day_idx-1):event_day_idx+10])
            
            # Statistical significance test
            t_stat, p_value = self._significance_test(abnormal_returns)
            is_significant = p_value < 0.05
            
            # Build day-indexed dictionaries
            ar_dict = {}
            actual_dict = {}
            expected_dict = {}
            
            for i, ar in enumerate(abnormal_returns):
                day = i - event_day_idx
                ar_dict[day] = ar
                actual_dict[day] = actual_event_returns[i]
                expected_dict[day] = expected_event_returns[i]
            
            return EventStudyResult(
                event_id=event.id,
                ticker=ticker,
                event_date=event_date,
                car_1day=car_1day,
                car_3day=car_3day,
                car_5day=car_5day,
                car_10day=car_10day,
                abnormal_returns=ar_dict,
                t_stat=t_stat,
                p_value=p_value,
                is_significant=is_significant,
                alpha=alpha,
                beta=beta,
                r_squared=r_squared,
                actual_returns=actual_dict,
                expected_returns=expected_dict
            )
            
        except Exception as e:
            logger.error(f"Error in event study for {ticker}: {e}")
            return None
    
    async def analyze_multiple_events(
        self,
        events: List[TrialEvent],
        benchmark: str = "XBI"
    ) -> List[EventStudyResult]:
        """Analyze multiple events."""
        results = []
        
        for event in events:
            if event.company and event.company.ticker:
                result = await self.analyze_event(event, event.company.ticker, benchmark)
                if result:
                    results.append(result)
        
        return results
    
    def _calculate_returns(self, prices: List) -> List[float]:
        """Calculate daily returns from price data."""
        returns = []
        for i in range(1, len(prices)):
            if hasattr(prices[i], 'adj_close'):
                curr = float(prices[i].adj_close)
                prev = float(prices[i-1].adj_close)
            else:
                curr = float(prices[i])
                prev = float(prices[i-1])
            
            if prev > 0:
                returns.append((curr - prev) / prev)
            else:
                returns.append(0.0)
        
        return returns
    
    def _find_event_index(
        self,
        prices: List,
        event_date: datetime
    ) -> Optional[int]:
        """Find the index of the event date in price data."""
        for i, price in enumerate(prices):
            price_date = price.date if hasattr(price, 'date') else price
            if hasattr(price_date, 'date'):
                price_date = price_date.date()
            if hasattr(event_date, 'date'):
                event_date_cmp = event_date.date()
            else:
                event_date_cmp = event_date
            
            if price_date == event_date_cmp:
                return i
            elif price_date > event_date_cmp:
                return max(0, i - 1)
        
        return None
    
    def _estimate_market_model(
        self,
        stock_returns: List[float],
        benchmark_returns: List[float]
    ) -> Tuple[float, float, float]:
        """Estimate market model parameters using OLS."""
        if len(stock_returns) != len(benchmark_returns):
            min_len = min(len(stock_returns), len(benchmark_returns))
            stock_returns = stock_returns[:min_len]
            benchmark_returns = benchmark_returns[:min_len]
        
        # Convert to numpy arrays
        y = np.array(stock_returns)
        X = np.array(benchmark_returns)
        
        # Add constant for alpha
        X = add_constant(X)
        
        # Fit OLS
        model = OLS(y, X).fit()
        
        alpha = model.params[0]
        beta = model.params[1]
        r_squared = model.rsquared
        
        return alpha, beta, r_squared
    
    def _significance_test(
        self,
        abnormal_returns: List[float]
    ) -> Tuple[float, float]:
        """Test statistical significance of abnormal returns."""
        if not abnormal_returns:
            return 0.0, 1.0
        
        # One-sample t-test
        t_stat, p_value = stats.ttest_1samp(abnormal_returns, 0)
        
        # Two-tailed test
        if np.isnan(t_stat):
            return 0.0, 1.0
        
        return float(t_stat), float(p_value)
    
    def aggregate_results(
        self,
        results: List[EventStudyResult]
    ) -> Dict[str, any]:
        """Aggregate results across multiple events."""
        if not results:
            return {}
        
        cars_1day = [r.car_1day for r in results]
        cars_3day = [r.car_3day for r in results]
        cars_5day = [r.car_5day for r in results]
        cars_10day = [r.car_10day for r in results]
        
        # Cross-sectional test
        t_stat_3day, p_value_3day = stats.ttest_1samp(cars_3day, 0)
        
        return {
            "num_events": len(results),
            "avg_car_1day": np.mean(cars_1day),
            "avg_car_3day": np.mean(cars_3day),
            "avg_car_5day": np.mean(cars_5day),
            "avg_car_10day": np.mean(cars_10day),
            "median_car_3day": np.median(cars_3day),
            "std_car_3day": np.std(cars_3day),
            "t_stat_3day": t_stat_3day,
            "p_value_3day": p_value_3day,
            "significant_events": sum(1 for r in results if r.is_significant),
            "percent_positive_3day": sum(1 for c in cars_3day if c > 0) / len(cars_3day) * 100,
        }
    
    def get_average_abnormal_return_curve(
        self,
        results: List[EventStudyResult]
    ) -> Dict[int, float]:
        """Get average abnormal return for each day relative to event."""
        if not results:
            return {}
        
        day_returns: Dict[int, List[float]] = {}
        
        for result in results:
            for day, ar in result.abnormal_returns.items():
                if day not in day_returns:
                    day_returns[day] = []
                day_returns[day].append(ar)
        
        avg_curve = {}
        for day, returns in day_returns.items():
            avg_curve[day] = np.mean(returns)
        
        return avg_curve


# Singleton instance
_analyzer: Optional[EventStudyAnalyzer] = None


def get_event_study_analyzer() -> EventStudyAnalyzer:
    """Get singleton instance of EventStudyAnalyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = EventStudyAnalyzer()
    return _analyzer
