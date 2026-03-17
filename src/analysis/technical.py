"""Technical analysis module — MACD, RSI, Volume, Divergence detection."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class TechnicalSignal:
    """Technical analysis result for a ticker."""
    ticker: str
    timestamp: datetime
    
    # RSI
    rsi_14: Optional[float] = None
    rsi_zone: str = "neutral"  # oversold / neutral / overbought
    
    # MACD
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_crossover: str = "none"  # bullish_cross / bearish_cross / none
    macd_trend: str = "neutral"   # bullish / bearish / neutral
    
    # Volume
    current_volume: Optional[int] = None
    avg_volume_20: Optional[int] = None
    volume_ratio: Optional[float] = None  # current / avg
    volume_surge: bool = False  # > 2x average
    
    # Divergence
    rsi_divergence: str = "none"      # bullish / bearish / none
    macd_divergence: str = "none"     # bullish / bearish / none
    
    # ATR
    atr_14: Optional[float] = None
    atr_pct: Optional[float] = None  # ATR as % of price
    
    # Overall TA score (0-1)
    ta_score: float = 0.5
    ta_verdict: str = "neutral"  # strong_buy / buy / neutral / sell / strong_sell
    ta_reasons: List[str] = field(default_factory=list)
    
    @property
    def supports_entry(self) -> bool:
        """Whether TA supports entering a long position."""
        return self.ta_score >= 0.55
    
    @property
    def supports_short(self) -> bool:
        """Whether TA supports entering a short position."""
        return self.ta_score <= 0.40


def compute_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using exponential moving average (Wilder's method)."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD line, signal line, and histogram."""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def detect_divergence(prices: pd.Series, indicator: pd.Series, lookback: int = 14) -> str:
    """
    Detect bullish or bearish divergence between price and indicator (RSI or MACD).
    
    Bullish divergence: price makes lower low, indicator makes higher low
    Bearish divergence: price makes higher high, indicator makes lower high
    """
    if len(prices) < lookback * 2 or len(indicator) < lookback * 2:
        return "none"
    
    # Get recent and prior windows
    recent_prices = prices.iloc[-lookback:]
    prior_prices = prices.iloc[-lookback*2:-lookback]
    recent_ind = indicator.iloc[-lookback:]
    prior_ind = indicator.iloc[-lookback*2:-lookback]
    
    # Find lows and highs
    recent_price_low = recent_prices.min()
    prior_price_low = prior_prices.min()
    recent_ind_low = recent_ind.min()
    prior_ind_low = prior_ind.min()
    
    recent_price_high = recent_prices.max()
    prior_price_high = prior_prices.max()
    recent_ind_high = recent_ind.max()
    prior_ind_high = prior_ind.max()
    
    # Bullish divergence: price lower low + indicator higher low
    if recent_price_low < prior_price_low and recent_ind_low > prior_ind_low:
        return "bullish"
    
    # Bearish divergence: price higher high + indicator lower high
    if recent_price_high > prior_price_high and recent_ind_high < prior_ind_high:
        return "bearish"
    
    return "none"


def analyze_ticker(ticker: str, hist: pd.DataFrame) -> Optional[TechnicalSignal]:
    """
    Run full technical analysis on a ticker's price history.
    
    Args:
        ticker: Stock symbol
        hist: DataFrame with columns: Open, High, Low, Close, Volume (index = datetime)
    
    Returns:
        TechnicalSignal with all indicators computed
    """
    if hist is None or len(hist) < 35:  # Need at least 35 bars for MACD(26) + signal(9)
        logger.debug(f"Insufficient data for TA on {ticker}: {len(hist) if hist is not None else 0} bars")
        return None
    
    closes = hist['Close'].astype(float)
    volumes = hist['Volume'].astype(float)
    highs = hist['High'].astype(float) if 'High' in hist.columns else closes
    lows = hist['Low'].astype(float) if 'Low' in hist.columns else closes
    
    sig = TechnicalSignal(ticker=ticker, timestamp=datetime.now())
    reasons = []
    score = 0.5  # Start neutral
    
    # === ATR ===
    if len(closes) >= 15:
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                float(highs.iloc[i] - lows.iloc[i]),
                abs(float(highs.iloc[i] - closes.iloc[i-1])),
                abs(float(lows.iloc[i] - closes.iloc[i-1]))
            )
            true_ranges.append(tr)
        if true_ranges:
            tr_series = pd.Series(true_ranges)
            atr_14_val = tr_series.ewm(span=14, adjust=False).mean().iloc[-1]
            sig.atr_14 = round(atr_14_val, 4)
            current_px = float(closes.iloc[-1])
            sig.atr_pct = round(atr_14_val / current_px, 4) if current_px > 0 else None
    
    # === RSI ===
    rsi = compute_rsi(closes)
    current_rsi = rsi.iloc[-1]
    if pd.notna(current_rsi):
        sig.rsi_14 = round(current_rsi, 1)
        if current_rsi <= 30:
            sig.rsi_zone = "oversold"
            score += 0.12
            reasons.append(f"RSI oversold ({sig.rsi_14})")
        elif current_rsi <= 40:
            sig.rsi_zone = "approaching_oversold"
            score += 0.06
            reasons.append(f"RSI approaching oversold ({sig.rsi_14})")
        elif current_rsi >= 70:
            sig.rsi_zone = "overbought"
            score -= 0.10
            reasons.append(f"RSI overbought ({sig.rsi_14}) — risky entry")
        elif current_rsi >= 60:
            sig.rsi_zone = "approaching_overbought"
            score -= 0.04
            reasons.append(f"RSI elevated ({sig.rsi_14})")
        else:
            sig.rsi_zone = "neutral"
    
    # === MACD ===
    macd_line, signal_line, histogram = compute_macd(closes)
    if len(macd_line) >= 2 and pd.notna(macd_line.iloc[-1]):
        sig.macd_line = round(macd_line.iloc[-1], 4)
        sig.macd_signal = round(signal_line.iloc[-1], 4)
        sig.macd_histogram = round(histogram.iloc[-1], 4)
        
        # Crossover detection (last 2 bars)
        prev_hist = histogram.iloc[-2]
        curr_hist = histogram.iloc[-1]
        
        if prev_hist < 0 and curr_hist >= 0:
            sig.macd_crossover = "bullish_cross"
            score += 0.10
            reasons.append("MACD bullish crossover ✅")
        elif prev_hist > 0 and curr_hist <= 0:
            sig.macd_crossover = "bearish_cross"
            score -= 0.10
            reasons.append("MACD bearish crossover ⚠️")
        
        # MACD trend (histogram direction over 3 bars)
        if len(histogram) >= 3:
            h3 = histogram.iloc[-3:]
            if h3.iloc[-1] > h3.iloc[-2] > h3.iloc[-3]:
                sig.macd_trend = "bullish"
                score += 0.05
                reasons.append("MACD histogram rising")
            elif h3.iloc[-1] < h3.iloc[-2] < h3.iloc[-3]:
                sig.macd_trend = "bearish"
                score -= 0.05
                reasons.append("MACD histogram falling")
    
    # === Volume ===
    if len(volumes) >= 20:
        sig.current_volume = int(volumes.iloc[-1])
        sig.avg_volume_20 = int(volumes.iloc[-20:].mean())
        
        if sig.avg_volume_20 > 0:
            sig.volume_ratio = round(sig.current_volume / sig.avg_volume_20, 2)
            sig.volume_surge = sig.volume_ratio >= 2.0
            
            if sig.volume_surge:
                score += 0.08
                reasons.append(f"Volume surge ({sig.volume_ratio}x avg) — strong conviction")
            elif sig.volume_ratio >= 1.3:
                score += 0.04
                reasons.append(f"Above-average volume ({sig.volume_ratio}x)")
            elif sig.volume_ratio < 0.5:
                score -= 0.04
                reasons.append(f"Thin volume ({sig.volume_ratio}x) — weak conviction")
    
    # === Divergence ===
    if len(rsi) >= 28:
        sig.rsi_divergence = detect_divergence(closes, rsi, lookback=14)
        if sig.rsi_divergence == "bullish":
            score += 0.10
            reasons.append("Bullish RSI divergence — reversal signal 🔥")
        elif sig.rsi_divergence == "bearish":
            score -= 0.08
            reasons.append("Bearish RSI divergence — momentum fading")
    
    if len(histogram) >= 28:
        sig.macd_divergence = detect_divergence(closes, histogram, lookback=14)
        if sig.macd_divergence == "bullish":
            score += 0.08
            reasons.append("Bullish MACD divergence")
        elif sig.macd_divergence == "bearish":
            score -= 0.06
            reasons.append("Bearish MACD divergence")
    
    # === Final score ===
    sig.ta_score = max(0.0, min(1.0, score))
    
    if sig.ta_score >= 0.72:
        sig.ta_verdict = "strong_buy"
    elif sig.ta_score >= 0.58:
        sig.ta_verdict = "buy"
    elif sig.ta_score >= 0.42:
        sig.ta_verdict = "neutral"
    elif sig.ta_score >= 0.30:
        sig.ta_verdict = "sell"
    else:
        sig.ta_verdict = "strong_sell"
    
    sig.ta_reasons = reasons
    return sig


async def get_technical_analysis(ticker: str, days: int = 90) -> Optional[TechnicalSignal]:
    """
    Fetch price history and run technical analysis for a ticker.
    Uses yfinance async-compatible pattern.
    """
    import asyncio
    import yfinance as yf
    
    try:
        loop = asyncio.get_event_loop()
        stock = yf.Ticker(ticker)
        hist = await loop.run_in_executor(
            None,
            lambda: stock.history(period=f"{days}d")
        )
        
        if hist is None or hist.empty:
            logger.warning(f"No price data for TA: {ticker}")
            return None
        
        return analyze_ticker(ticker, hist)
        
    except Exception as e:
        logger.error(f"TA error for {ticker}: {e}")
        return None
