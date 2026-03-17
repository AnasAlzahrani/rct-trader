# 🧪 RCT Trader — Clinical Trials Intelligence Monitor

**An open-source tool that monitors ClinicalTrials.gov events and maps them to publicly traded pharma/biotech companies.**

> ⚠️ **Honest disclaimer:** I built this, ran it for 3 weeks on a $100K paper trading account, and it **lost $1,180 (-1.18%)**. The intelligence engine works — the trading strategy doesn't. This is shared as-is for collaboration, not as a profitable system. [Read the full story →](#the-honest-results)

---

## What It Does

1. **Scans ClinicalTrials.gov** for recent events (results posted, primary completion, enrollment changes, suspensions, terminations)
2. **Maps trial sponsors → stock tickers** using 181 company mappings (pharma, biotech, medical devices)
3. **Classifies events** by clinical significance (Phase 3 completion > Phase 1 enrollment)
4. **Generates intelligence signals** with confidence scores (catalyst quality + company strength + market conditions)
5. **Runs technical analysis** (RSI, MACD, volume, ATR) as entry/exit filters
6. **Optionally trades** via Alpaca paper/live accounts

## The Honest Results

I ran this from Feb 3–22, 2026 on Alpaca paper trading:

| Metric | Value |
|--------|-------|
| Starting Capital | $100,000 |
| Final Equity | $98,820 |
| **P&L** | **-$1,180 (-1.18%)** |
| Peak | $102,487 (+2.5%) |
| Max Drawdown | -3.58% |
| Orders | 74 (59 buys, 14 sells) |
| Tickers | 14 unique |

### What Went Wrong

1. **Latency problem** — By the time events appear on ClinicalTrials.gov, the market has already priced them in. Institutional investors have faster pipelines (SEC filings, KOL networks, FDA calendars).

2. **Spray and pray** — 59 buy orders across 14 tickers in 19 days. No conviction, no concentration. Should have been 5-6 high-confidence bets.

3. **No edge on event classification** — "Phase 3 results posted" is a signal, but knowing the *outcome* (positive vs negative) requires reading the actual results, not just the event type.

4. **Risk management was too loose** — Positions were small (2% each) but too many. The portfolio became a diluted pharma ETF.

5. **Forced liquidation** — Sold everything on Feb 22 for strategic reasons (pivoting the company), not based on signals. Sold winners and losers alike.

### What Actually Works

- The **ClinicalTrials.gov scanner** is reliable and fast
- The **sponsor → ticker mapping** (181 companies) is comprehensive
- **Event classification** correctly identifies significant milestones
- The **technical analysis engine** (RSI, MACD, volume divergence) is solid standalone
- The **architecture** (modular, clean separation) is production-grade

## Why I'm Open-Sourcing This

I'm a physician-scientist (MD, PhD, MPH) who studies causal inference and clinical trials. I built this to explore whether trial events create tradeable market signals. The answer is: **not with this approach**, but the underlying intelligence layer has value.

**Possible better uses:**
- 📊 Pharma competitive intelligence dashboard
- 🔬 Research tool for studying market reactions to clinical evidence
- 📈 Input feature for a more sophisticated ML trading model
- 🏥 Hospital/health system pipeline monitoring
- 📋 Grant writing — tracking the clinical trial landscape

**I'm looking for collaborators** who can improve the signal quality, build better event classification, or find a genuine edge.

## Architecture

```
rct-trader/
├── src/
│   ├── data_sources/
│   │   ├── clinical_trials.py   # ClinicalTrials.gov API client
│   │   ├── market_data.py       # Yahoo Finance integration
│   │   └── company_mapper.py    # 181 sponsor → ticker mappings
│   ├── analysis/
│   │   ├── signal_generator.py  # Weighted scoring engine
│   │   ├── technical.py         # RSI, MACD, volume, ATR
│   │   ├── event_study.py       # Statistical event analysis
│   │   └── risk_manager.py      # Position sizing, stop losses
│   ├── alerts/
│   │   └── notifier.py          # Telegram, email, console alerts
│   ├── database/
│   │   └── models.py            # SQLAlchemy models
│   └── bot.py                   # Main orchestrator
├── tests/
├── requirements.txt
└── .env.example
```

## Signal Scoring

| Component | Weight | Description |
|-----------|--------|-------------|
| Catalyst Quality | 30% | Event type, trial phase, therapeutic area |
| Technical Analysis | 25% | RSI, MACD, volume ratio, divergence |
| Company Strength | 20% | Market cap, pipeline depth |
| Market Conditions | 10% | Sector momentum, VIX |
| Timing Edge | 10% | Information freshness |
| ML Prediction | 5% | Historical pattern matching |

## Quick Start

```bash
# Clone
git clone https://github.com/AnasAlzahrani/rct-trader.git
cd rct-trader

# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Alpaca keys (free at alpaca.markets)

# Run a scan
python -m src.bot scan --hours 24

# Demo mode (mock signals)
python -m src.bot demo

# Continuous monitoring
python -m src.bot run
```

## Data Sources (All Free)

| Source | Data | Cost |
|--------|------|------|
| ClinicalTrials.gov | Trial events, results, sponsors | Free |
| Yahoo Finance | Stock prices, fundamentals | Free |
| Alpaca | Paper trading execution | Free |

## Ideas for Improvement

If you want to contribute, here's where I think the edge might be:

1. **FDA calendar integration** — PDUFA dates, advisory committee meetings. These are scheduled and tradeable.
2. **Trial outcome parsing** — Actually read the results (efficacy vs futility), don't just detect "results posted"
3. **Pre-event positioning** — Buy *before* expected completion dates, not after
4. **Sentiment overlay** — Twitter/Reddit biotech chatter as a signal amplifier
5. **International trials** — EudraCT, AMED (Japan), CTRI (India)
6. **Options strategies** — Straddles before binary events (FDA decisions)
7. **Better universe filtering** — $20B+ market cap only, or micro-cap biotech only (not both)

## Contributing

This is genuinely collaborative. If you:
- Have a better signal idea → open an issue
- Can improve the ML model → submit a PR
- Found a bug → let me know
- Want to fork and build something different → go for it

## Built By

[Coefficients Health Analytics](https://coef.health) — Research rigor, automated.

Built by [Anas Alzahrani](https://linkedin.com/in/anas-alzahrani-md-phd-mph-7b055218b), MD PhD MPH — Assistant Professor, King Abdulaziz University. Specializing in causal inference, clinical trials methodology, and health data science.

## License

MIT License — do whatever you want with it.

## Disclaimer

This is **not financial advice**. This tool lost money. Trading involves risk of loss. The clinical trials data is delayed. Do your own research. This is shared for educational and collaborative purposes only.
