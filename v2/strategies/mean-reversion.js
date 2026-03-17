const { fetchBars, calculateRSI, averageVolume } = require('../data/market');
const { readJson } = require('../lib/io');
const config = require('../config');

function loadUniverse() {
  const list = readJson(config.sp500Path, []);
  if (Array.isArray(list) && list.length > 0) return list;
  return [];
}

async function scanMeanReversion() {
  const symbols = loadUniverse();
  const signals = [];
  for (const symbol of symbols) {
    try {
      const bars = await fetchBars(symbol, { timeframe: '1Day', limit: 40 });
      if (bars.length < 20) continue;
      const rsi = calculateRSI(bars, 14);
      const avgVol = averageVolume(bars, 20);
      const latest = bars[bars.length - 1];
      if (rsi !== null && rsi < 25 && avgVol && latest.v > avgVol * 2) {
        signals.push({
          symbol,
          strategy: 'MEAN_REVERSION',
          direction: 'long',
          score: Math.min(1, (25 - rsi) / 25),
          meta: {
            rsi,
            latestVolume: latest.v,
            averageVolume: avgVol,
          },
        });
      }
    } catch (err) {
      // skip symbol on data errors
    }
  }
  return signals;
}

module.exports = { scanMeanReversion };
