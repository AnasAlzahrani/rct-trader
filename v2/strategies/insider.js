const { fetchRecentInsiderPurchases } = require('../data/insider');

function clusterBySymbol(filings, windowDays = 30) {
  const bySymbol = {};
  const cutoff = Date.now() - windowDays * 24 * 60 * 60 * 1000;
  for (const filing of filings) {
    const ts = Date.parse(filing.pubDate || filing.fetchedAt);
    if (!Number.isFinite(ts) || ts < cutoff) continue;
    if (!bySymbol[filing.ticker]) bySymbol[filing.ticker] = [];
    bySymbol[filing.ticker].push(filing);
  }
  return bySymbol;
}

async function scanInsiderClusters() {
  const filings = await fetchRecentInsiderPurchases({ lookbackDays: 60 });
  const clusters = clusterBySymbol(filings, 30);
  const signals = [];
  for (const [symbol, items] of Object.entries(clusters)) {
    const uniqueInsiders = new Set(items.map((item) => item.insider).filter(Boolean));
    if (uniqueInsiders.size >= 3) {
      signals.push({
        symbol,
        strategy: 'INSIDER_CLUSTER',
        direction: 'long',
        score: Math.min(1, uniqueInsiders.size / 5),
        meta: {
          insiderCount: uniqueInsiders.size,
          filings: items.length,
        },
      });
    }
  }
  return signals;
}

module.exports = { scanInsiderClusters };
