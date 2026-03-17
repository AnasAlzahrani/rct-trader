# Stock Trading Bot v2 — Multi-Strategy Paper Trading

## Why RCT Failed
- Single signal source (clinical trials → stock) with no proven edge
- No exit logic — buy and hold forever
- 42% win rate, -0.39% in 19 days
- The "edge" was noise

## What Actually Has Edge (Literature-Backed)

### Strategy 1: PEAD (Post-Earnings Announcement Drift)
- **The anomaly:** After earnings surprises, stocks continue drifting in the surprise direction for 30-60 days
- **Academic backing:** One of the most robust anomalies in finance, documented since 1968 (Ball & Brown), still persistent
- **Why it works:** Investors underreact to earnings news
- **Signal:** Buy after positive earnings surprise (EPS beat > 10%), sell after negative surprise
- **Entry:** Day after earnings announcement (avoid overnight gap risk by entering at market open)
- **Exit:** 30-day hold or trailing stop at -5%
- **Edge:** ~2-4% per trade historically, stronger in small/mid-cap with low analyst coverage
- **Data source:** Financial Modeling Prep API (free tier: 250 req/day) or Yahoo Finance

### Strategy 2: Insider Buying Clusters
- **The signal:** When 3+ insiders buy within 30 days (cluster buying), it predicts 8-12% outperformance over 6 months
- **Why it works:** Insiders buy for one reason (they think it's undervalued). Multiple insiders = strong conviction
- **Caveat:** Jan 2026 SSRN paper shows most alpha occurs BEFORE Form 4 filing. But cluster buying still has residual signal
- **Entry:** Day after detecting 3+ insider buys in 30-day window
- **Exit:** 60-day hold or trailing stop at -7%
- **Data source:** SEC EDGAR Form 4 RSS feed (free, real-time)

### Strategy 3: Mean Reversion (RSI Extreme + Volume Spike)
- **The signal:** RSI(14) < 25 AND volume > 2x 20-day average AND stock is in S&P 500
- **Why it works:** Large-cap stocks rarely stay oversold — institutional buying kicks in
- **Entry:** When RSI < 25 with volume confirmation
- **Exit:** RSI crosses back above 50, or 10-day max hold, or -3% stop loss
- **Edge:** ~1.5-3% per trade, high win rate (65-75%)
- **Data source:** Alpaca market data (free with account)

## Architecture

```
rct-trader/
├── strategies/
│   ├── pead.js          # Earnings surprise scanner
│   ├── insider.js       # SEC Form 4 cluster detector
│   └── mean-reversion.js # RSI + volume oversold bounce
├── signals/
│   ├── scanner.js       # Runs all strategies, generates signals
│   └── scorer.js        # Scores and ranks signals across strategies
├── execution/
│   ├── paper-trader.js  # Paper trading engine (existing Alpaca connection)
│   ├── risk.js          # Position sizing, max positions, sector limits
│   └── exits.js         # Stop losses, trailing stops, time-based exits
├── data/
│   ├── earnings.js      # Earnings calendar + surprise data
│   ├── insider.js       # SEC EDGAR Form 4 feed
│   └── market.js        # Price/volume/RSI from Alpaca
└── index.js             # Orchestrator: scan → score → trade → manage exits
```

## Risk Management (What RCT v1 Lacked)
- Max 10 open positions
- Max 2% of portfolio per position ($2K on $100K)
- Hard stop loss: -5% (no exceptions)
- Trailing stop: activates at +3%, trails at 2%
- Max sector exposure: 30% in any single sector
- Daily loss limit: -2% of portfolio → halt trading for the day
- Time-based exit: 30 days max hold (PEAD), 60 days (insider), 10 days (mean reversion)

## Success Criteria (30-day paper test)
- Win rate > 55%
- Profit factor > 1.5 (gross profits / gross losses)
- Max drawdown < 5%
- Sharpe ratio > 1.0
- At least 50 round-trip trades

## Data Sources (All Free)
1. **Alpaca Market Data** — real-time prices, bars, RSI calculation (already connected)
2. **SEC EDGAR** — Form 4 filings RSS feed (https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=only&count=100&search_text=&action=getcurrent)
3. **Financial Modeling Prep** — earnings calendar, EPS estimates (free tier)
4. **Yahoo Finance** — backup for earnings data (via yahoo-finance skill)
