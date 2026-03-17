const { fetchEarningsCalendar } = require('../data/earnings');

async function scanPEAD({ surpriseThreshold = 0.1 } = {}) {
  const earnings = await fetchEarningsCalendar();
  return earnings
    .filter((item) => item.surprise !== null && item.surprise >= surpriseThreshold)
    .map((item) => ({
      symbol: item.symbol,
      strategy: 'PEAD',
      direction: 'long',
      score: Math.min(1, item.surprise),
      meta: {
        earningsDate: item.date,
        surprise: item.surprise,
        epsActual: item.epsActual,
        epsEstimated: item.epsEstimated,
        source: item.source,
      },
    }));
}

module.exports = { scanPEAD };
