"""Advanced risk management module for RCT Trader v2.

Implements:
- ATR-based trailing stops
- Time-based exits
- Volatility-adjusted position sizing
- Drawdown protection (circuit breaker)
- Scaled profit-taking
- Volume confirmation
- Portfolio-level risk limits
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger

from src.data_sources.market_data import get_market_data_client
from src.utils.config import settings


@dataclass
class ATRData:
    """Average True Range data for a ticker."""
    ticker: str
    atr_14: float  # 14-day ATR
    atr_7: float   # 7-day ATR (short-term)
    current_price: float
    atr_pct: float  # ATR as % of price
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TrailingStopState:
    """State for a trailing stop on an open position."""
    ticker: str
    entry_price: float
    highest_price: float
    current_stop: float
    atr_multiplier: float  # typically 2.0-3.0
    atr_value: float
    activated: bool = False  # Only activate after position is in profit
    activation_threshold: float = 0.02  # Activate after 2% profit
    
    def update(self, current_price: float, current_atr: Optional[float] = None) -> Tuple[float, bool]:
        """Update trailing stop. Returns (new_stop, triggered)."""
        if current_atr:
            self.atr_value = current_atr
        
        # Check if we should activate the trailing stop
        profit_pct = (current_price - self.entry_price) / self.entry_price
        if profit_pct >= self.activation_threshold:
            self.activated = True
        
        if not self.activated:
            # Use fixed stop until trailing activates
            return self.current_stop, current_price <= self.current_stop
        
        # Update highest price
        if current_price > self.highest_price:
            self.highest_price = current_price
            # ATR-based trailing: stop = highest - (ATR * multiplier)
            new_stop = self.highest_price - (self.atr_value * self.atr_multiplier)
            # Never lower the stop
            self.current_stop = max(self.current_stop, new_stop)
        
        triggered = current_price <= self.current_stop
        return self.current_stop, triggered


@dataclass
class ScaledExitPlan:
    """Scaled profit-taking plan."""
    ticker: str
    entry_price: float
    # List of (target_pct, exit_fraction) - e.g., [(0.05, 0.33), (0.10, 0.33), (0.15, 0.34)]
    targets: List[Tuple[float, float]] = field(default_factory=list)
    targets_hit: List[bool] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.targets:
            # Default: take 1/3 at +5%, 1/3 at +10%, let rest ride with trailing stop
            self.targets = [(0.05, 0.33), (0.10, 0.33), (0.20, 0.34)]
        self.targets_hit = [False] * len(self.targets)
    
    def check_targets(self, current_price: float) -> List[Tuple[float, float]]:
        """Check which targets are hit. Returns list of (target_pct, fraction_to_sell)."""
        exits = []
        profit_pct = (current_price - self.entry_price) / self.entry_price
        
        for i, (target, fraction) in enumerate(self.targets):
            if not self.targets_hit[i] and profit_pct >= target:
                self.targets_hit[i] = True
                exits.append((target, fraction))
        
        return exits


class RiskManager:
    """Portfolio-level risk management."""
    
    def __init__(self):
        self.market_client = get_market_data_client()
        self._trailing_stops: Dict[str, TrailingStopState] = {}
        self._exit_plans: Dict[str, ScaledExitPlan] = {}
        self._position_entry_times: Dict[str, datetime] = {}
        self._circuit_breaker_active = False
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0
        self._peak_portfolio_value: Optional[float] = None
    
    # ── ATR Calculation ──────────────────────────────────────────────
    
    async def calculate_atr(self, ticker: str, period: int = 14) -> Optional[ATRData]:
        """Calculate ATR for a ticker."""
        try:
            end = datetime.now()
            start = end - timedelta(days=period * 3)  # Extra data for warmup
            
            prices = await self.market_client.get_price_history(ticker, start, end)
            if len(prices) < period + 1:
                return None
            
            highs = [float(p.high_price) for p in prices]
            lows = [float(p.low_price) for p in prices]
            closes = [float(p.close_price) for p in prices]
            
            # True Range = max(H-L, |H-prevC|, |L-prevC|)
            true_ranges = []
            for i in range(1, len(prices)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                true_ranges.append(tr)
            
            if len(true_ranges) < period:
                return None
            
            # ATR = EMA of True Range
            tr_series = pd.Series(true_ranges)
            atr_14 = tr_series.ewm(span=14, adjust=False).mean().iloc[-1]
            atr_7 = tr_series.ewm(span=7, adjust=False).mean().iloc[-1]
            current_price = closes[-1]
            
            return ATRData(
                ticker=ticker,
                atr_14=round(atr_14, 4),
                atr_7=round(atr_7, 4),
                current_price=current_price,
                atr_pct=round(atr_14 / current_price, 4) if current_price > 0 else 0,
            )
        except Exception as e:
            logger.error(f"ATR calculation failed for {ticker}: {e}")
            return None
    
    # ── Volatility-Adjusted Position Sizing ──────────────────────────
    
    async def calculate_position_size(
        self,
        ticker: str,
        confidence: float,
        portfolio_value: float,
        max_risk_per_trade: float = 0.02,  # 2% of portfolio at risk
    ) -> Tuple[float, float]:
        """
        Calculate position size using ATR-based volatility adjustment.
        
        Returns: (position_size_pct, stop_distance_pct)
        
        Formula: Position Size = (Portfolio * Risk%) / (ATR * Multiplier)
        This ensures each trade risks the same dollar amount regardless of volatility.
        """
        atr_data = await self.calculate_atr(ticker)
        
        if not atr_data or atr_data.atr_pct == 0:
            # Fallback to confidence-based sizing
            base = 0.02 if confidence >= 0.70 else 0.01
            return min(base, settings.MAX_POSITION_SIZE_PCT), 0.05
        
        # ATR-based stop distance: 2x ATR
        atr_multiplier = 2.0
        stop_distance_pct = atr_data.atr_pct * atr_multiplier
        
        # Ensure minimum stop distance of 3% and max of 12%
        stop_distance_pct = max(0.03, min(0.12, stop_distance_pct))
        
        # Position size = risk_budget / stop_distance
        # E.g., if risk = 2% of portfolio and stop = 5%, position = 40% ... too much
        # So we also cap by MAX_POSITION_SIZE_PCT
        risk_budget = max_risk_per_trade
        raw_position_pct = risk_budget / stop_distance_pct
        
        # Confidence adjustment: scale down for lower confidence
        confidence_mult = min(1.0, (confidence - 0.5) / 0.3)  # 0 at 0.5, 1.0 at 0.8
        adjusted_position = raw_position_pct * max(0.25, confidence_mult)
        
        # Cap
        final_position = min(adjusted_position, settings.MAX_POSITION_SIZE_PCT)
        
        return round(final_position, 4), round(stop_distance_pct, 4)
    
    # ── Trailing Stop Management ─────────────────────────────────────
    
    def create_trailing_stop(
        self,
        ticker: str,
        entry_price: float,
        atr_value: float,
        multiplier: float = 2.5,
        initial_stop_pct: float = 0.05,
    ) -> TrailingStopState:
        """Create a trailing stop for a new position."""
        initial_stop = entry_price * (1 - initial_stop_pct)
        
        state = TrailingStopState(
            ticker=ticker,
            entry_price=entry_price,
            highest_price=entry_price,
            current_stop=initial_stop,
            atr_multiplier=multiplier,
            atr_value=atr_value,
        )
        self._trailing_stops[ticker] = state
        self._position_entry_times[ticker] = datetime.now()
        
        logger.info(f"Trailing stop created for {ticker}: entry={entry_price}, "
                     f"initial_stop={initial_stop:.2f}, ATR={atr_value:.2f}")
        return state
    
    def update_trailing_stop(self, ticker: str, current_price: float, 
                              current_atr: Optional[float] = None) -> Tuple[float, bool]:
        """Update trailing stop for ticker. Returns (stop_price, triggered)."""
        if ticker not in self._trailing_stops:
            return 0.0, False
        return self._trailing_stops[ticker].update(current_price, current_atr)
    
    # ── Time-Based Exits ─────────────────────────────────────────────
    
    def check_time_exit(self, ticker: str, max_hold_days: int = 10) -> bool:
        """Check if position has exceeded maximum holding period."""
        if ticker not in self._position_entry_times:
            return False
        
        entry_time = self._position_entry_times[ticker]
        days_held = (datetime.now() - entry_time).days
        
        if days_held >= max_hold_days:
            logger.info(f"Time exit triggered for {ticker}: held {days_held} days (max={max_hold_days})")
            return True
        return False
    
    def get_time_exit_candidates(self, max_hold_days: int = 10) -> List[str]:
        """Get all positions that should be exited due to time."""
        candidates = []
        for ticker in self._position_entry_times:
            if self.check_time_exit(ticker, max_hold_days):
                candidates.append(ticker)
        return candidates
    
    # ── Scaled Profit Taking ─────────────────────────────────────────
    
    def create_exit_plan(self, ticker: str, entry_price: float, 
                          event_type: str = "results_posted") -> ScaledExitPlan:
        """Create a scaled exit plan based on catalyst type."""
        # Different targets for different catalysts
        if event_type in ("results_posted", "fda_approval"):
            # High-impact: wider targets, hold longer
            targets = [(0.05, 0.25), (0.10, 0.25), (0.15, 0.25), (0.25, 0.25)]
        elif event_type in ("phase_advance",):
            # Medium-impact
            targets = [(0.04, 0.33), (0.08, 0.33), (0.12, 0.34)]
        else:
            # Low-impact: tighter targets
            targets = [(0.03, 0.50), (0.06, 0.50)]
        
        plan = ScaledExitPlan(ticker=ticker, entry_price=entry_price, targets=targets)
        self._exit_plans[ticker] = plan
        return plan
    
    # ── Volume Confirmation ──────────────────────────────────────────
    
    async def confirm_volume(self, ticker: str, min_ratio: float = 1.3) -> Tuple[bool, float]:
        """
        Check if current volume supports the trade.
        Returns (confirmed, volume_ratio).
        
        Requires volume >= min_ratio * 20-day average.
        """
        try:
            end = datetime.now()
            start = end - timedelta(days=40)
            prices = await self.market_client.get_price_history(ticker, start, end)
            
            if len(prices) < 21:
                return True, 1.0  # Insufficient data, don't block
            
            volumes = [p.volume for p in prices if p.volume > 0]
            if len(volumes) < 21:
                return True, 1.0
            
            avg_vol = np.mean(volumes[-21:-1])  # 20-day avg excluding today
            current_vol = volumes[-1]
            
            if avg_vol == 0:
                return True, 1.0
            
            ratio = current_vol / avg_vol
            confirmed = ratio >= min_ratio
            
            if not confirmed:
                logger.info(f"Volume confirmation failed for {ticker}: ratio={ratio:.2f} < {min_ratio}")
            
            return confirmed, round(ratio, 2)
            
        except Exception as e:
            logger.debug(f"Volume check failed for {ticker}: {e}")
            return True, 1.0  # Don't block on error
    
    # ── Circuit Breaker / Drawdown Protection ────────────────────────
    
    def update_portfolio_value(self, current_value: float):
        """Update portfolio tracking for drawdown protection."""
        if self._peak_portfolio_value is None:
            self._peak_portfolio_value = current_value
        else:
            self._peak_portfolio_value = max(self._peak_portfolio_value, current_value)
    
    def check_circuit_breaker(self, current_value: float, 
                                max_drawdown_pct: float = 0.08) -> bool:
        """
        Check if trading should be paused due to drawdown.
        
        Returns True if circuit breaker is triggered (should pause trading).
        """
        if self._peak_portfolio_value is None:
            self.update_portfolio_value(current_value)
            return False
        
        drawdown = (self._peak_portfolio_value - current_value) / self._peak_portfolio_value
        
        if drawdown >= max_drawdown_pct:
            if not self._circuit_breaker_active:
                logger.warning(f"🚨 Circuit breaker triggered! Drawdown: {drawdown:.1%} "
                              f"(peak: ${self._peak_portfolio_value:,.0f}, "
                              f"current: ${current_value:,.0f})")
                self._circuit_breaker_active = True
            return True
        
        # Reset circuit breaker if drawdown recovers to < half the threshold
        if self._circuit_breaker_active and drawdown < max_drawdown_pct / 2:
            logger.info("Circuit breaker reset — drawdown recovered")
            self._circuit_breaker_active = False
        
        return False
    
    def check_daily_loss_limit(self, daily_pnl: float, portfolio_value: float) -> bool:
        """Check if daily loss limit has been hit."""
        daily_loss_pct = abs(daily_pnl) / portfolio_value if daily_pnl < 0 else 0
        return daily_loss_pct >= settings.MAX_DAILY_LOSS_PCT
    
    # ── Entry Timing ─────────────────────────────────────────────────
    
    @staticmethod
    def is_good_entry_window() -> Tuple[bool, str]:
        """
        Check if current time is a good entry window.
        
        Avoid: first 15 min (9:30-9:45) and last 15 min (3:45-4:00) of market.
        Best: 10:00-11:30 AM or 2:00-3:30 PM ET.
        """
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        # Convert to ET (UTC-5, simplified - doesn't handle DST)
        et_hour = (now_utc.hour - 5) % 24
        et_minute = now_utc.minute
        
        # Market hours: 9:30-16:00 ET
        market_minutes = et_hour * 60 + et_minute
        
        if market_minutes < 9 * 60 + 30 or market_minutes >= 16 * 60:
            return False, "Market closed"
        
        if market_minutes < 9 * 60 + 45:
            return False, "Avoid first 15 minutes - high volatility/spreads"
        
        if market_minutes >= 15 * 60 + 45:
            return False, "Avoid last 15 minutes - erratic closes"
        
        # Best windows
        if (10 * 60 <= market_minutes <= 11 * 60 + 30) or \
           (14 * 60 <= market_minutes <= 15 * 60 + 30):
            return True, "Optimal entry window"
        
        return True, "Acceptable entry window"
    
    # ── Correlation / Beta Exposure ──────────────────────────────────
    
    async def calculate_portfolio_beta(self, positions: Dict[str, float]) -> float:
        """
        Calculate portfolio beta-weighted exposure.
        positions: {ticker: position_value}
        """
        if not positions:
            return 0.0
        
        total_value = sum(positions.values())
        if total_value == 0:
            return 0.0
        
        weighted_beta = 0.0
        for ticker, value in positions.items():
            weight = value / total_value
            try:
                # Get beta from price history vs XBI
                end = datetime.now()
                start = end - timedelta(days=120)
                
                stock_prices = await self.market_client.get_price_history(ticker, start, end)
                bench_prices = await self.market_client.get_price_history("XBI", start, end)
                
                if len(stock_prices) < 30 or len(bench_prices) < 30:
                    weighted_beta += weight * 1.0  # Assume beta=1
                    continue
                
                stock_returns = pd.Series([float(p.close_price) for p in stock_prices]).pct_change().dropna()
                bench_returns = pd.Series([float(p.close_price) for p in bench_prices]).pct_change().dropna()
                
                min_len = min(len(stock_returns), len(bench_returns))
                cov = np.cov(stock_returns.iloc[-min_len:], bench_returns.iloc[-min_len:])
                beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 1.0
                
                weighted_beta += weight * beta
                
            except Exception:
                weighted_beta += weight * 1.0
        
        return round(weighted_beta, 2)
    
    # ── Cleanup ──────────────────────────────────────────────────────
    
    def remove_position(self, ticker: str):
        """Clean up tracking state when a position is closed."""
        self._trailing_stops.pop(ticker, None)
        self._exit_plans.pop(ticker, None)
        self._position_entry_times.pop(ticker, None)


# Singleton
_risk_manager: Optional[RiskManager] = None

def get_risk_manager() -> RiskManager:
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
