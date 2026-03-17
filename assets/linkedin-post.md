# LinkedIn Post — RCT Trader Open Source Launch

---

I built a bot that scans clinical trials and trades pharma stocks.

It lost $1,180.

Here's why I'm giving it away for free.

—

Everyone's talking about AI in drug discovery. Billions flowing into clinical pipelines. New trials every day.

But nobody asks the obvious question:

**What happens AFTER the trial?**

How does clinical evidence actually translate to stock price?

As a physician-scientist (MD, PhD, MPH) who studies causal inference and clinical trial methodology — I wanted to find out.

So I built RCT Trader:
→ Scans ClinicalTrials.gov in real-time
→ Maps 181 trial sponsors to stock tickers
→ Scores signals using catalyst quality + technical analysis + ML
→ Tracks ARK Invest trades across all 6 ETFs for convergence signals
→ Executes via Alpaca (paper or live)

I ran it for 3 weeks on $100K paper money.

**Results:**
- Peak: +$2,487 (+2.5%)
- Final: -$1,180 (-1.18%)
- Max drawdown: -3.58%
- 74 orders across 14 tickers

It peaked, then gave everything back.

**What went wrong:**

1. ClinicalTrials.gov data is too slow. By the time events appear, institutions have already moved.
2. 59 buy orders across 14 tickers = spray and pray, not conviction.
3. Detecting "results posted" isn't enough — you need to know if results are positive or negative.
4. Too many small positions diluted any alpha into noise.

**What actually works:**

✅ The ClinicalTrials.gov scanner is fast and reliable
✅ 181 company mappings are comprehensive
✅ The ARK Invest tracker shows what smart money is doing TODAY
✅ Technical analysis engine (RSI, MACD, volume divergence) is solid
✅ The architecture is production-grade (3,900 lines of Python)

**Why I'm open-sourcing this:**

I'm not a quant. I'm a clinical researcher who builds tools.

The data pipeline works. The intelligence layer works. The trading strategy doesn't — yet.

I believe someone in this network — maybe a biotech analyst, a quant developer, or a clinical researcher who also watches markets — can take this further.

**Ideas I think could work:**
- FDA calendar integration (PDUFA dates are scheduled and tradeable)
- NLP to parse trial RESULTS, not just events
- Pre-event positioning (buy before expected completion dates)
- Options straddles before binary FDA decisions

It's MIT licensed. Fork it. Improve it. Build something better.

🔗 GitHub: https://github.com/AnasAlzahrani/rct-trader

The intersection of clinical evidence and market intelligence is wide open. A physician-scientist reading trial results has a structural advantage over a quant reading price charts.

The gap isn't the data. It's the interpretation.

That's a causal inference problem.

And that's my lane.

—

#ClinicalTrials #DrugDiscovery #AIinHealthcare #Biotech #OpenSource #QuantFinance #CausalInference #PharmaceuticalIndustry #ARKInvest #HealthcareAI

---

## Posting Notes

**Format:** Long-form text post (no carousel needed — the story carries it)

**Timing:** Tuesday or Wednesday, 7-8 AM EST (peak LinkedIn engagement for healthcare/finance)

**Attachments:** 
1. Screenshot of ARK tracker output (terminal)
2. Screenshot of signal demo output (terminal)
3. Logo image

**First comment (post immediately after):**
"Here's what the ARK Invest tracker looks like in action — real data from today. CRSP (CRISPR Therapeutics) showing 77% conviction across ARKK + ARKG. That's the kind of convergence signal that gets interesting when combined with a positive Phase 3 result."

**Second comment (30 min later):**
"For anyone asking 'how do I get started' — it's 5 steps:
1. Clone the repo
2. pip install requirements
3. Get free Alpaca paper trading keys
4. Run `python -m src.bot demo`
5. Or just run the ARK tracker: `python -m src.data_sources.ark_tracker`

Full setup guide in the README. Takes about 10 minutes."
