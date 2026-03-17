const { scanPEAD } = require('../strategies/pead');
const { scanInsiderClusters } = require('../strategies/insider');
const { scanMeanReversion } = require('../strategies/mean-reversion');
const { logEvent } = require('../lib/logger');

async function runScanner() {
  const [pead, insider, mean] = await Promise.all([
    scanPEAD(),
    scanInsiderClusters(),
    scanMeanReversion(),
  ]);
  const signals = [...pead, ...insider, ...mean];
  logEvent('signals_scanned', {
    counts: { pead: pead.length, insider: insider.length, mean: mean.length, total: signals.length },
  });
  return signals;
}

module.exports = { runScanner };
