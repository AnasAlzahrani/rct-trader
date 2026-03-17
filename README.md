# 🧪 RCT Trader — Clinical Trials Intelligence Monitor

**Open-source tool that monitors ClinicalTrials.gov in real-time, maps trial events to pharma/biotech stocks, and generates market intelligence signals.**

Built at the intersection of clinical research, AI drug discovery, and quantitative finance.

> ⚠️ **Full transparency:** I ran this for 3 weeks on $100K paper money. It **lost $1,180 (-1.18%)**. The data pipeline works — the trading strategy needs work. That's why it's open source. [See results →](#performance-results)

---

## 🎯 Why This Exists

AI is transforming drug discovery. Billions are flowing into clinical trials. But there's a gap:

**Clinical evidence → market pricing is still inefficient.**

Most quants can't read trial results. Most clinicians don't watch markets. This tool bridges that gap — whether for trading, competitive intelligence, or research.

---

## ✨ Features

### Core Intelligence
- 🔍 **ClinicalTrials.gov Scanner** — Real-time monitoring of trial events (results, completions, suspensions, terminations)
- 🏢 **Company Mapper** — 181 sponsor → ticker mappings (Pfizer, Lilly, Novartis, Gilead, Amgen, etc.)
- 📊 **Event Classifier** — Categorizes events by significance (Phase 3 results > Phase 1 enrollment)
- 🧠 **ML Signal Scoring** — Weighted model: catalyst quality (30%) + technical analysis (25%) + company strength (20%) + market conditions (10%) + timing (10%) + ML prediction (5%)
- 🦈 **ARK Invest Tracker** — Real-time monitoring of all ARK ETF trades and holdings (ARKK, ARKG, ARKF, ARKW, ARKQ, ARKX) with conviction scoring and cross-referencing against trial signals

### Technical Analysis
- 📈 **RSI(14)** with zone detection (oversold/overbought)
- 📉 **MACD(12/26/9)** with crossover detection
- 📊 **Volume analysis** with ratio and divergence detection
- 🎯 **ATR-based** trailing stops and position sizing

### Trading & Alerts
- 💰 **Alpaca Integration** — Paper or live trading (stocks + crypto)
- 📱 **Telegram alerts** — Real-time signal notifications
- 📧 **Email alerts** — SMTP-based notifications
- 🖥️ **Rich CLI** — Beautiful terminal output with tables and charts

### Risk Management
- Max position: 5% of portfolio
- Max sector exposure: 25%
- Max daily loss: 3% (circuit breaker)
- ATR-based stop losses
- Confidence-based position sizing

### ARK Invest Radar
- 🏦 **Daily trade tracking** across all 6 ARK ETFs
- 📈 **Multi-fund conviction scoring** — CRSP bought by both ARKK + ARKG = high conviction
- 🎯 **Cross-reference engine** — ARK buying + positive trial signal = convergence (boosted confidence)
- 📊 **Holdings weight tracking** — monitor accumulation vs reduction over time
- 🧬 **ARKG focus** — Genomic Revolution ETF weighted highest for biotech relevance

```bash
# Quick ARK summary
python -m src.data_sources.ark_tracker
```

Example output:
```
📊 ARK Invest Activity Summary
========================================

🟢 BUYING (5 tickers):
  CRSP   |   44,923 shares | Conviction: 77% | Funds: ARKG, ARKK | Holdings: 15.3%
  WGS    |    6,017 shares | Conviction: 68% | Funds: ARKG, ARKK | Holdings: 3.5%

🔴 SELLING (6 tickers):
  IONS   |    7,220 shares | Conviction: 67% | Funds: ARKG
  TXG    |   32,982 shares | Conviction: 66% | Funds: ARKG, ARKK
```

---

## 📦 Installation

### Prerequisites
- Python 3.10+
- Git

### Step 1: Clone & Setup

```bash
git clone https://github.com/AnasAlzahrani/rct-trader.git
cd rct-trader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-core.txt
```

### Step 2: Configure

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# REQUIRED: Alpaca API (free at https://alpaca.markets)
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use paper first!

# OPTIONAL: Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_IDS=your_chat_id

# OPTIONAL: Email alerts
EMAIL_USERNAME=your_email
EMAIL_PASSWORD=your_app_password
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

### Step 3: Get Alpaca Keys (Free)

1. Go to [alpaca.markets](https://alpaca.markets) and create a free account
2. Navigate to **Paper Trading** → **API Keys**
3. Generate a new key pair
4. Paste `API Key ID` and `Secret Key` into your `.env`
5. Keep `ALPACA_BASE_URL=https://paper-api.alpaca.markets` for paper trading

> 💡 **Paper trading is free** with $100K virtual money. No real money risk. Start here.

### Step 4: Run

```bash
# Quick demo with sample signals
python -m src.bot demo

# Scan last 24 hours of clinical trials
python -m src.bot scan --hours 24

# Continuous monitoring (scans every hour)
python -m src.bot run

# Scan specific trial phase
python -m src.bot scan --hours 48 --phase PHASE3
```

---

## 🔌 Connecting Your Brokerage

### Paper Trading (Recommended Start)

Alpaca paper trading gives you $100K virtual money:

```env
ALPACA_BASE_URL=https://paper-api.alpaca.markets
TRADING_MODE=paper
INITIAL_CAPITAL=100000
```

### Live Trading (⚠️ Real Money)

Switch to live when you're confident in your strategy:

```env
ALPACA_BASE_URL=https://api.alpaca.markets
TRADING_MODE=live
```

> ⚠️ **Warning:** This bot lost money in paper trading. Do NOT use live trading without significant improvements to the signal model. You will likely lose money.

### Alert-Only Mode (No Trading)

Just receive signals without executing trades:

```env
TRADING_MODE=alert
```

Signals go to Telegram, email, or console. You decide what to trade manually.

---

## 📊 Performance Results

**Paper trading: Feb 3–22, 2026 ($100K account)**

| Metric | Value |
|--------|-------|
| Starting Capital | $100,000 |
| Final Equity | $98,820 |
| **Total P&L** | **-$1,180 (-1.18%)** |
| Peak Equity | $102,487 (+2.5%) |
| Max Drawdown | -3.58% from peak |
| Total Orders | 74 (59 buys, 14 sells) |
| Unique Tickers | 14 |
| Win Rate | ~40% |

### Tickers Traded
`AMGN` `AZN` `LLY` `PFE` `MRK` `NVO` `BSX` `GSK` `RHHBY` `BAYRY` `ARWR` `MYGN` `SNY` `SOLUSD`

### What Went Wrong

1. **📡 Latency** — ClinicalTrials.gov updates are delayed. By the time events appear, institutional investors have already moved.
2. **🎯 No conviction** — 59 buys across 14 tickers = spray and pray. Should be 5 high-confidence bets.
3. **📄 Event ≠ Outcome** — Detecting "results posted" isn't enough. You need to know if the results are *positive or negative*.
4. **💊 Pharma ETF effect** — Too many small positions diluted any alpha into noise.
5. **🔪 Forced exit** — Liquidated all positions on Feb 22 for strategic reasons, not signals.

### What Actually Works

✅ ClinicalTrials.gov scanner — fast, reliable, good event detection
✅ Company mapper — 181 verified sponsor → ticker mappings
✅ Technical analysis engine — RSI, MACD, volume divergence
✅ Architecture — modular, clean, production-grade code
✅ Alert system — real-time Telegram notifications

---

## 🧬 Architecture

```
rct-trader/
├── src/
│   ├── bot.py                      # Main orchestrator & CLI
│   ├── data_sources/
│   │   ├── clinical_trials.py      # ClinicalTrials.gov API (441 lines)
│   │   ├── market_data.py          # Yahoo Finance integration (403 lines)
│   │   └── company_mapper.py       # 181 sponsor→ticker maps (335 lines)
│   ├── analysis/
│   │   ├── signal_generator.py     # ML scoring engine (657 lines)
│   │   ├── technical.py            # RSI/MACD/Volume/ATR (298 lines)
│   │   ├── event_study.py          # Statistical event analysis (338 lines)
│   │   └── risk_manager.py         # Position sizing & stops (462 lines)
│   ├── alerts/
│   │   └── notifier.py             # Telegram/email/console (346 lines)
│   ├── database/
│   │   └── models.py               # SQLAlchemy models (418 lines)
│   └── utils/
│       └── config.py               # Pydantic settings (125 lines)
├── v2/                             # Node.js experimental version
├── tests/                          # Test suite
├── requirements-core.txt           # Lean dependencies
├── requirements.txt                # Full dependencies (ML, NLP, etc.)
└── .env.example                    # Configuration template
```

**~3,900 lines of Python** across 11 modules. Clean separation of concerns.

---

## 🔬 Signal Scoring Model

Each potential signal is scored on 6 weighted components:

```
Final Score = (0.30 × Catalyst) + (0.25 × Technical) + (0.20 × Company)
            + (0.10 × Market) + (0.10 × Timing) + (0.05 × ML)
```

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| **Catalyst Quality** | 30% | Trial phase, event type, therapeutic area, primary endpoint |
| **Technical Analysis** | 25% | RSI zone, MACD crossover, volume surge, divergence |
| **Company Strength** | 20% | Market cap, pipeline depth, sector position |
| **Market Conditions** | 10% | Sector momentum, VIX, risk-on/risk-off |
| **Timing Edge** | 10% | Hours since event, pre-market vs market, information freshness |
| **ML Prediction** | 5% | GradientBoosting on historical event → price patterns |

**Signal thresholds:**
- **Strong Buy:** ≥ 75% confidence
- **Buy:** ≥ 60% confidence
- **Sell:** ≥ 60% confidence (negative catalyst)
- **Minimum:** ≥ 55% to generate any signal

---

## 🤝 Contributing — Where the Edge Might Be

This is a genuine collaboration request. Here's what I think could make this profitable:

### 🟢 High-Impact Ideas
1. **FDA Calendar Integration** — PDUFA dates and AdCom meetings are *scheduled*. Position before binary events.
2. **Trial Outcome Parsing** — Use NLP to read actual results (efficacy vs futility vs safety signal), not just "results posted"
3. **Pre-event Positioning** — Buy 2-4 weeks before expected Phase 3 completion dates
4. **Options Strategies** — Straddles before FDA decisions capture volatility regardless of direction

### 🟡 Medium-Impact Ideas
5. **Sentiment Overlay** — Biotech Twitter/Reddit chatter as a signal amplifier
6. **SEC Filing Cross-Reference** — 8-K filings often appear before ClinicalTrials.gov updates
7. **International Trials** — EudraCT (Europe), AMED (Japan), CTRI (India)
8. **Better Universe** — Focus on micro-cap biotech (binary outcomes) OR mega-cap pharma (not both)

### 🔵 Research Ideas
9. **Event Study Framework** — Rigorous CAR/BHAR analysis of trial event → stock reaction
10. **Causal Inference** — Does trial *outcome quality* predict abnormal returns? (IV: trial design rigor → stock reaction)
11. **AI Drug Discovery Signals** — Track AI-discovered vs traditional compounds separately

---

## 📱 Setting Up Telegram Alerts

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token to `.env` as `TELEGRAM_BOT_TOKEN`
4. Start a chat with your new bot
5. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)
6. Add chat ID to `.env` as `TELEGRAM_CHAT_IDS`

You'll get real-time alerts like:
```
🟢 STRONG BUY: GILD (76.5%)
Phase 3 Hep B results posted
RSI: 42.3 (neutral) | MACD: bullish cross
Entry: $84.20 | Stop: $81.50 | Target: $91.00
```

---

## 🗺️ Roadmap

- [ ] FDA calendar integration (PDUFA dates)
- [ ] NLP trial outcome parsing
- [ ] Web dashboard (React)
- [ ] Options market support
- [ ] SEC 8-K filing monitor
- [ ] International trials (EudraCT)
- [ ] Backtesting framework
- [ ] Portfolio optimization (Markowitz / risk parity)
- [ ] Social sentiment integration
- [ ] Mobile app alerts

---

## 🏥 Built By

**[Coefficients Health Analytics](https://coef.health)** — Research rigor, automated.

Created by **[Anas Alzahrani](https://linkedin.com/in/anas-alzahrani-md-phd-mph-7b055218b)**, MD PhD MPH
- Assistant Professor, King Abdulaziz University
- PhD in Clinical Research (Mount Sinai)
- MPH in Epidemiologic Methods (Johns Hopkins)
- 20+ years in data analysis and clinical trials

> *"I study how clinical evidence translates to real-world outcomes. This is the same question — except the outcome is stock price."*

---

## 📄 License

MIT License — fork it, improve it, build on it.

---

## ⚠️ Disclaimer

**This is not financial advice.** This tool lost money in paper trading. Trading stocks involves substantial risk of loss. Clinical trials data from ClinicalTrials.gov may be delayed or incomplete. Past performance does not guarantee future results. Always do your own research. This software is provided "as-is" for educational and research purposes.
