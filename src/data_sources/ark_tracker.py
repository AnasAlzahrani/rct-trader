"""ARK Invest trade and holdings tracker.

Monitors daily trades across all ARK ETFs (ARKK, ARKG, ARKF, ARKW, ARKQ, ARKX)
and cross-references with clinical trial signals for conviction scoring.

Data source: arkfunds.io API (free, no key required)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import requests
from loguru import logger
from cachetools import TTLCache


class TradeDirection(str, Enum):
    BUY = "Buy"
    SELL = "Sell"


@dataclass
class ArkTrade:
    """A single ARK trade."""
    fund: str
    date: str
    ticker: str
    company: str
    direction: TradeDirection
    shares: int
    etf_percent: float  # % of ETF that this trade represents
    cusip: str = ""


@dataclass
class ArkHolding:
    """A single ARK holding."""
    fund: str
    date: str
    ticker: str
    company: str
    shares: int
    market_value: float
    share_price: float
    weight: float  # % weight in fund
    weight_rank: int = 0


@dataclass
class ArkSignal:
    """Cross-referenced ARK signal with clinical trial data."""
    ticker: str
    company: str
    ark_action: TradeDirection
    funds_involved: List[str]
    total_shares: int
    total_etf_impact: float  # Combined etf_percent across funds
    conviction_score: float  # 0-1 based on trade size + multi-fund + direction
    holdings_weight: float  # Current total weight across all ARK funds
    has_trial_signal: bool = False
    trial_signal_direction: Optional[str] = None
    convergence: bool = False  # True if ARK trade aligns with trial signal


# ARK ETFs to monitor
ARK_FUNDS = ["ARKK", "ARKG", "ARKF", "ARKW", "ARKQ", "ARKX"]

# Biotech-heavy funds get higher weight in conviction scoring
FUND_RELEVANCE = {
    "ARKG": 1.0,   # Genomic Revolution — most relevant to clinical trials
    "ARKK": 0.8,   # Innovation — broad but includes biotech
    "ARKQ": 0.3,   # Autonomous Tech — less relevant
    "ARKW": 0.3,   # Next Gen Internet — less relevant
    "ARKF": 0.2,   # Fintech — rarely relevant
    "ARKX": 0.2,   # Space — rarely relevant
}

API_BASE = "https://arkfunds.io/api/v2"


class ArkTracker:
    """Track ARK Invest trades and holdings."""

    def __init__(self):
        self._trade_cache = TTLCache(maxsize=100, ttl=3600)  # 1hr cache
        self._holdings_cache = TTLCache(maxsize=100, ttl=3600)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "RCT-Trader/1.0"})

    def get_trades(self, fund: str = "ARKG") -> List[ArkTrade]:
        """Get recent trades for an ARK fund."""
        cache_key = f"trades_{fund}"
        if cache_key in self._trade_cache:
            return self._trade_cache[cache_key]

        try:
            r = self._session.get(
                f"{API_BASE}/etf/trades?symbol={fund}", timeout=15
            )
            r.raise_for_status()
            data = r.json()
            trades = [
                ArkTrade(
                    fund=t["fund"],
                    date=t["date"],
                    ticker=t.get("ticker", ""),
                    company=t.get("company", ""),
                    direction=TradeDirection(t["direction"]),
                    shares=t.get("shares", 0),
                    etf_percent=t.get("etf_percent", 0),
                    cusip=t.get("cusip", ""),
                )
                for t in data.get("trades", [])
                if t.get("ticker")
            ]
            self._trade_cache[cache_key] = trades
            logger.info(f"Fetched {len(trades)} trades for {fund}")
            return trades
        except Exception as e:
            logger.error(f"Failed to fetch {fund} trades: {e}")
            return []

    def get_all_trades(self) -> List[ArkTrade]:
        """Get recent trades across ALL ARK funds."""
        all_trades = []
        for fund in ARK_FUNDS:
            trades = self.get_trades(fund)
            all_trades.extend(trades)
        return all_trades

    def get_holdings(self, fund: str = "ARKG") -> List[ArkHolding]:
        """Get current holdings for an ARK fund."""
        cache_key = f"holdings_{fund}"
        if cache_key in self._holdings_cache:
            return self._holdings_cache[cache_key]

        try:
            r = self._session.get(
                f"{API_BASE}/etf/holdings?symbol={fund}", timeout=15
            )
            r.raise_for_status()
            data = r.json()
            holdings = [
                ArkHolding(
                    fund=h["fund"],
                    date=h.get("date", ""),
                    ticker=h.get("ticker", ""),
                    company=h.get("company", ""),
                    shares=h.get("shares", 0),
                    market_value=h.get("market_value", 0),
                    share_price=h.get("share_price", 0),
                    weight=h.get("weight", 0),
                    weight_rank=h.get("weight_rank", 0),
                )
                for h in data.get("holdings", [])
                if h.get("ticker")
            ]
            self._holdings_cache[cache_key] = holdings
            logger.info(f"Fetched {len(holdings)} holdings for {fund}")
            return holdings
        except Exception as e:
            logger.error(f"Failed to fetch {fund} holdings: {e}")
            return []

    def get_ticker_holdings(self, ticker: str) -> List[ArkHolding]:
        """Get holdings of a specific ticker across all ARK funds."""
        all_holdings = []
        for fund in ARK_FUNDS:
            holdings = self.get_holdings(fund)
            for h in holdings:
                if h.ticker == ticker:
                    all_holdings.append(h)
        return all_holdings

    def get_ticker_total_weight(self, ticker: str) -> float:
        """Get combined weight of a ticker across all ARK funds."""
        holdings = self.get_ticker_holdings(ticker)
        return sum(h.weight for h in holdings)

    def aggregate_trades_by_ticker(
        self, trades: Optional[List[ArkTrade]] = None
    ) -> Dict[str, ArkSignal]:
        """Aggregate trades by ticker across funds and compute conviction."""
        if trades is None:
            trades = self.get_all_trades()

        # Group by ticker + direction
        ticker_map: Dict[str, Dict] = {}
        for t in trades:
            key = t.ticker
            if key not in ticker_map:
                ticker_map[key] = {
                    "ticker": t.ticker,
                    "company": t.company,
                    "buys": [],
                    "sells": [],
                }
            if t.direction == TradeDirection.BUY:
                ticker_map[key]["buys"].append(t)
            else:
                ticker_map[key]["sells"].append(t)

        # Build signals
        signals: Dict[str, ArkSignal] = {}
        for ticker, data in ticker_map.items():
            buys = data["buys"]
            sells = data["sells"]

            # Determine net direction
            buy_shares = sum(t.shares for t in buys)
            sell_shares = sum(t.shares for t in sells)

            if buy_shares > sell_shares:
                direction = TradeDirection.BUY
                primary_trades = buys
            elif sell_shares > buy_shares:
                direction = TradeDirection.SELL
                primary_trades = sells
            else:
                continue  # Net zero — skip

            funds_involved = list(set(t.fund for t in primary_trades))
            total_shares = abs(buy_shares - sell_shares)
            total_etf_impact = sum(t.etf_percent for t in primary_trades)

            # Conviction scoring
            conviction = self._compute_conviction(
                direction, primary_trades, funds_involved, total_etf_impact
            )

            # Current holdings weight
            holdings_weight = self.get_ticker_total_weight(ticker)

            signals[ticker] = ArkSignal(
                ticker=ticker,
                company=data["company"],
                ark_action=direction,
                funds_involved=funds_involved,
                total_shares=total_shares,
                total_etf_impact=total_etf_impact,
                conviction_score=conviction,
                holdings_weight=holdings_weight,
            )

        return signals

    def _compute_conviction(
        self,
        direction: TradeDirection,
        trades: List[ArkTrade],
        funds: List[str],
        etf_impact: float,
    ) -> float:
        """Compute conviction score (0-1) for an ARK signal.

        Factors:
        - Number of funds buying/selling (multi-fund = high conviction)
        - Relevance of funds (ARKG > ARKF for biotech)
        - Size of trade (etf_percent)
        - Consistency (all buys or all sells, no mixed signals)
        """
        score = 0.0

        # Multi-fund bonus (0-0.3)
        fund_count = len(funds)
        score += min(fund_count * 0.10, 0.30)

        # Fund relevance (0-0.3)
        relevance = sum(FUND_RELEVANCE.get(f, 0.1) for f in funds) / len(funds)
        score += relevance * 0.30

        # Trade size — etf_percent (0-0.25)
        # >0.05% is significant, >0.1% is large
        size_score = min(etf_impact / 0.10, 1.0)
        score += size_score * 0.25

        # Consistency bonus (0-0.15)
        directions = set(t.direction for t in trades)
        if len(directions) == 1:
            score += 0.15  # All same direction

        return min(score, 1.0)

    def cross_reference_trial_signal(
        self, ticker: str, trial_direction: str, ark_signals: Optional[Dict[str, ArkSignal]] = None
    ) -> Optional[ArkSignal]:
        """Check if an ARK signal converges with a clinical trial signal.

        Args:
            ticker: Stock ticker
            trial_direction: 'buy' or 'sell' from trial signal
            ark_signals: Pre-computed ARK signals (optional)

        Returns:
            ArkSignal with convergence flag if match found
        """
        if ark_signals is None:
            ark_signals = self.aggregate_trades_by_ticker()

        signal = ark_signals.get(ticker)
        if not signal:
            return None

        signal.has_trial_signal = True
        signal.trial_signal_direction = trial_direction

        # Check convergence
        ark_buy = signal.ark_action == TradeDirection.BUY
        trial_buy = trial_direction.lower() in ("buy", "strong_buy")

        if ark_buy == trial_buy:
            signal.convergence = True
            # Boost conviction when both point same direction
            signal.conviction_score = min(signal.conviction_score * 1.5, 1.0)

        return signal

    def get_summary(self) -> str:
        """Generate a human-readable summary of ARK activity."""
        signals = self.aggregate_trades_by_ticker()
        if not signals:
            return "No recent ARK trades detected."

        lines = ["📊 ARK Invest Activity Summary", "=" * 40]

        buys = {k: v for k, v in signals.items() if v.ark_action == TradeDirection.BUY}
        sells = {k: v for k, v in signals.items() if v.ark_action == TradeDirection.SELL}

        if buys:
            lines.append(f"\n🟢 BUYING ({len(buys)} tickers):")
            for ticker, sig in sorted(buys.items(), key=lambda x: -x[1].conviction_score):
                funds_str = ", ".join(sig.funds_involved)
                lines.append(
                    f"  {ticker:6s} | {sig.total_shares:>8,} shares | "
                    f"Conviction: {sig.conviction_score:.0%} | "
                    f"Funds: {funds_str} | "
                    f"Holdings: {sig.holdings_weight:.1f}%"
                )

        if sells:
            lines.append(f"\n🔴 SELLING ({len(sells)} tickers):")
            for ticker, sig in sorted(sells.items(), key=lambda x: -x[1].conviction_score):
                funds_str = ", ".join(sig.funds_involved)
                lines.append(
                    f"  {ticker:6s} | {sig.total_shares:>8,} shares | "
                    f"Conviction: {sig.conviction_score:.0%} | "
                    f"Funds: {funds_str}"
                )

        return "\n".join(lines)


# Singleton
_tracker: Optional[ArkTracker] = None


def get_ark_tracker() -> ArkTracker:
    """Get or create the ARK tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = ArkTracker()
    return _tracker


if __name__ == "__main__":
    # Quick test
    tracker = ArkTracker()
    print(tracker.get_summary())
    print("\n--- ARKG Holdings (Top 10) ---")
    for h in tracker.get_holdings("ARKG")[:10]:
        print(f"  {h.ticker:6s} {h.weight:5.2f}% ${h.market_value/1e6:.1f}M — {h.company}")
