"""Enhanced market data client with multiple data sources."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

import httpx
import yfinance as yf
import pandas as pd
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from src.utils.config import settings


@dataclass
class PriceData:
    """Structured price data."""
    ticker: str
    date: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    adj_close: Decimal
    volume: int
    market_cap: Optional[Decimal] = None


@dataclass
class IntradayPrice:
    """Intraday price point."""
    ticker: str
    timestamp: datetime
    price: Decimal
    volume: int


@dataclass
class CompanyInfo:
    """Company fundamental information."""
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: Optional[Decimal]
    enterprise_value: Optional[Decimal]
    total_cash: Optional[Decimal]
    total_debt: Optional[Decimal]
    revenue: Optional[Decimal]
    net_income: Optional[Decimal]
    employees: Optional[int]
    website: Optional[str]
    description: Optional[str]


class MarketDataClient:
    """Client for fetching market data from multiple sources."""
    
    def __init__(self):
        self._price_cache = TTLCache(maxsize=500, ttl=300)  # 5 min cache for prices
        self._info_cache = TTLCache(maxsize=200, ttl=3600)  # 1 hour cache for info
        self._semaphore = asyncio.Semaphore(2)  # Low concurrency for 4GB server
    
    async def get_price_history(
        self,
        ticker: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        interval: str = "1d"
    ) -> List[PriceData]:
        """Get historical price data for a ticker."""
        cache_key = f"{ticker}:{start_date}:{end_date}:{interval}"
        
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
        
        try:
            # Use yfinance for historical data
            stock = yf.Ticker(ticker)
            
            # Run in thread pool since yfinance is synchronous
            loop = asyncio.get_event_loop()
            hist = await loop.run_in_executor(
                None,
                lambda: stock.history(
                    start=start_date,
                    end=end_date or datetime.now(),
                    interval=interval
                )
            )
            
            if hist.empty:
                logger.warning(f"No price data found for {ticker}")
                return []
            
            prices = []
            for date, row in hist.iterrows():
                prices.append(PriceData(
                    ticker=ticker,
                    date=date.to_pydatetime(),
                    open_price=Decimal(str(row['Open'])),
                    high_price=Decimal(str(row['High'])),
                    low_price=Decimal(str(row['Low'])),
                    close_price=Decimal(str(row['Close'])),
                    adj_close=Decimal(str(row.get('Adj Close', row['Close']))),
                    volume=int(row['Volume']) if pd.notna(row['Volume']) else 0
                ))
            
            self._price_cache[cache_key] = prices
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching price history for {ticker}: {e}")
            return []
    
    async def get_current_price(self, ticker: str) -> Optional[Decimal]:
        """Get current stock price (memory-efficient)."""
        cache_key = f"current:{ticker}"
        
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
        
        try:
            async with self._semaphore:
                stock = yf.Ticker(ticker)
                loop = asyncio.get_event_loop()
                
                # Use fast_info instead of info (much lighter on memory)
                try:
                    fast = await loop.run_in_executor(None, lambda: stock.fast_info)
                    current_price = getattr(fast, 'last_price', None)
                    if current_price:
                        price = Decimal(str(round(current_price, 2)))
                        self._price_cache[cache_key] = price
                        return price
                except Exception:
                    pass
                
                # Fallback: 2-day history (lighter than full info)
                hist = await loop.run_in_executor(
                    None,
                    lambda: stock.history(period="2d")
                )
                if not hist.empty:
                    price = Decimal(str(round(hist['Close'].iloc[-1], 2)))
                    self._price_cache[cache_key] = price
                    return price
                
                return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {ticker}: {e}")
            return None
    
    async def get_company_info(self, ticker: str) -> Optional[CompanyInfo]:
        """Get company fundamental information."""
        if ticker in self._info_cache:
            return self._info_cache[ticker]
        
        try:
            stock = yf.Ticker(ticker)
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: stock.info)
            
            if not info:
                return None
            
            company_info = CompanyInfo(
                ticker=ticker,
                name=info.get("longName") or info.get("shortName", ticker),
                sector=info.get("sector", "Unknown"),
                industry=info.get("industry", "Unknown"),
                market_cap=Decimal(str(info["marketCap"])) if info.get("marketCap") else None,
                enterprise_value=Decimal(str(info["enterpriseValue"])) if info.get("enterpriseValue") else None,
                total_cash=Decimal(str(info["totalCash"])) if info.get("totalCash") else None,
                total_debt=Decimal(str(info["totalDebt"])) if info.get("totalDebt") else None,
                revenue=Decimal(str(info["totalRevenue"])) if info.get("totalRevenue") else None,
                net_income=Decimal(str(info["netIncomeToCommon"])) if info.get("netIncomeToCommon") else None,
                employees=info.get("fullTimeEmployees"),
                website=info.get("website"),
                description=info.get("longBusinessSummary")
            )
            
            self._info_cache[ticker] = company_info
            return company_info
            
        except Exception as e:
            logger.error(f"Error getting company info for {ticker}: {e}")
            return None
    
    async def get_benchmark_returns(
        self,
        benchmark: str = "XBI",
        days: int = 252
    ) -> pd.Series:
        """Get benchmark returns for market model."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days * 1.5)  # Extra for calculations
            
            prices = await self.get_price_history(benchmark, start_date, end_date)
            if not prices:
                return pd.Series()
            
            df = pd.DataFrame([
                {"date": p.date, "close": float(p.adj_close)}
                for p in prices
            ])
            df.set_index("date", inplace=True)
            
            returns = df["close"].pct_change().dropna()
            return returns
            
        except Exception as e:
            logger.error(f"Error getting benchmark returns for {benchmark}: {e}")
            return pd.Series()
    
    async def get_sector_performance(
        self,
        sector_etfs: List[str] = None,
        period_days: int = 30
    ) -> Dict[str, float]:
        """Get performance of biotech/pharma sector ETFs."""
        if sector_etfs is None:
            sector_etfs = ["XBI", "IBB", "XLV", "PPH"]  # Biotech, Health Care, Pharma
        
        performance = {}
        
        for etf in sector_etfs:
            try:
                end = datetime.now()
                start = end - timedelta(days=period_days)
                
                prices = await self.get_price_history(etf, start, end)
                if len(prices) >= 2:
                    start_price = float(prices[0].adj_close)
                    end_price = float(prices[-1].adj_close)
                    performance[etf] = (end_price - start_price) / start_price
                else:
                    performance[etf] = 0.0
                    
            except Exception as e:
                logger.error(f"Error getting performance for {etf}: {e}")
                performance[etf] = 0.0
        
        return performance
    
    async def get_volatility(
        self,
        ticker: str,
        window_days: int = 30
    ) -> Optional[float]:
        """Calculate annualized volatility for a ticker."""
        try:
            end = datetime.now()
            start = end - timedelta(days=window_days * 2)
            
            prices = await self.get_price_history(ticker, start, end)
            if len(prices) < window_days:
                return None
            
            df = pd.DataFrame([
                {"date": p.date, "close": float(p.adj_close)}
                for p in prices
            ])
            df.set_index("date", inplace=True)
            
            returns = df["close"].pct_change().dropna()
            volatility = returns.std() * (252 ** 0.5)  # Annualized
            
            return volatility
            
        except Exception as e:
            logger.error(f"Error calculating volatility for {ticker}: {e}")
            return None
    
    async def get_average_volume(
        self,
        ticker: str,
        days: int = 30
    ) -> Optional[int]:
        """Get average daily volume."""
        try:
            end = datetime.now()
            start = end - timedelta(days=days * 2)
            
            prices = await self.get_price_history(ticker, start, end)
            if not prices:
                return None
            
            volumes = [p.volume for p in prices[-days:] if p.volume > 0]
            return int(sum(volumes) / len(volumes)) if volumes else None
            
        except Exception as e:
            logger.error(f"Error getting volume for {ticker}: {e}")
            return None
    
    async def is_near_earnings(
        self,
        ticker: str,
        date: datetime,
        window_days: int = 5
    ) -> Tuple[bool, Optional[datetime]]:
        """Check if date is near earnings announcement."""
        try:
            stock = yf.Ticker(ticker)
            loop = asyncio.get_event_loop()
            
            # Get earnings dates
            earnings_dates = await loop.run_in_executor(
                None,
                lambda: stock.earnings_dates
            )
            
            if earnings_dates is None or earnings_dates.empty:
                return False, None
            
            for earnings_date in earnings_dates.index:
                if isinstance(earnings_date, pd.Timestamp):
                    earnings_date = earnings_date.to_pydatetime()
                
                diff = abs((earnings_date - date).days)
                if diff <= window_days:
                    return True, earnings_date
            
            return False, None
            
        except Exception as e:
            logger.debug(f"Could not get earnings date for {ticker}: {e}")
            return False, None
    
    async def get_multiple_prices(
        self,
        tickers: List[str]
    ) -> Dict[str, Optional[Decimal]]:
        """Get current prices for multiple tickers efficiently."""
        tasks = [self.get_current_price(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                prices[ticker] = None
            else:
                prices[ticker] = result
        
        return prices
    
    def calculate_returns(
        self,
        prices: List[PriceData],
        window: int = 1
    ) -> List[float]:
        """Calculate returns from price data."""
        if len(prices) < window + 1:
            return []
        
        closes = [float(p.adj_close) for p in prices]
        returns = []
        
        for i in range(window, len(closes)):
            ret = (closes[i] - closes[i - window]) / closes[i - window]
            returns.append(ret)
        
        return returns
    
    def calculate_cumulative_return(
        self,
        prices: List[PriceData],
        start_idx: int = 0,
        end_idx: Optional[int] = None
    ) -> float:
        """Calculate cumulative return over a period."""
        if not prices:
            return 0.0
        
        end_idx = end_idx or len(prices) - 1
        if start_idx >= len(prices) or end_idx >= len(prices):
            return 0.0
        
        start_price = float(prices[start_idx].adj_close)
        end_price = float(prices[end_idx].adj_close)
        
        if start_price == 0:
            return 0.0
        
        return (end_price - start_price) / start_price


# Singleton instance
_md_client: Optional[MarketDataClient] = None


def get_market_data_client() -> MarketDataClient:
    """Get singleton instance of MarketDataClient."""
    global _md_client
    if _md_client is None:
        _md_client = MarketDataClient()
    return _md_client
