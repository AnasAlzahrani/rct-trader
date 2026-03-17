const { readJson } = require('../lib/io');
const config = require('../config');

function loadSectorMap() {
  const map = readJson(config.sectorMapPath, {});
  return map && typeof map === 'object' ? map : {};
}

function sectorExposure(positions, sectorMap) {
  const exposure = {};
  for (const pos of positions) {
    const sector = sectorMap[pos.symbol] || 'UNKNOWN';
    const value = Math.abs(Number(pos.market_value || 0));
    if (!exposure[sector]) exposure[sector] = 0;
    exposure[sector] += value;
  }
  return exposure;
}

function canAddPosition({ positions, equity, symbol }) {
  if (positions.length >= config.maxPositions) return { ok: false, reason: 'max_positions' };
  const sectorMap = loadSectorMap();
  const exposure = sectorExposure(positions, sectorMap);
  const sector = sectorMap[symbol] || 'UNKNOWN';
  if (sector !== 'UNKNOWN') {
    const sectorValue = exposure[sector] || 0;
    if (sectorValue / equity > config.sectorLimitPct) {
      return { ok: false, reason: 'sector_limit' };
    }
  }
  return { ok: true };
}

function positionSize({ equity, price }) {
  const maxDollars = equity * config.maxPositionPct;
  if (price <= 0) return 0;
  return Math.floor(maxDollars / price);
}

function shouldHaltTrading({ equity, dayStartEquity }) {
  if (!dayStartEquity) return false;
  const pnl = (equity - dayStartEquity) / dayStartEquity;
  return pnl <= config.dailyLossLimitPct;
}

module.exports = {
  canAddPosition,
  positionSize,
  shouldHaltTrading,
};
