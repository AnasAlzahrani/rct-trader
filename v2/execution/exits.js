const config = require('../config');
const { readJson, writeJson } = require('../lib/io');
const { logEvent } = require('../lib/logger');
const { sendTelegram } = require('../lib/telegram');
const { closePosition, listPositions } = require('./paper-trader');
const { fetchBars } = require('../data/market');

const MAX_HOLD_DAYS = {
  PEAD: 30,
  INSIDER_CLUSTER: 60,
  MEAN_REVERSION: 10,
};

function loadPositionState() {
  return readJson(config.positionsPath, { positions: {} });
}

function savePositionState(state) {
  writeJson(config.positionsPath, state);
}

function daysHeld(entryTime) {
  const entry = Date.parse(entryTime);
  if (!Number.isFinite(entry)) return 0;
  const diff = Date.now() - entry;
  return diff / (24 * 60 * 60 * 1000);
}

async function updateTrailingStop(positionState, marketPrice) {
  const state = { ...positionState };
  const entry = Number(state.entryPrice);
  if (!Number.isFinite(entry) || entry <= 0) return state;
  const gainPct = (marketPrice - entry) / entry;
  if (!state.trailingActive && gainPct >= config.trailingActivationPct) {
    state.trailingActive = true;
    state.trailingStop = marketPrice * (1 - config.trailingDistancePct);
  }
  if (state.trailingActive) {
    const newStop = marketPrice * (1 - config.trailingDistancePct);
    if (!state.trailingStop || newStop > state.trailingStop) {
      state.trailingStop = newStop;
    }
  }
  return state;
}

async function manageExits() {
  const state = loadPositionState();
  const alpacaPositions = await listPositions();
  let updated = false;

  for (const pos of alpacaPositions) {
    const symbol = pos.symbol;
    const positionState = state.positions[symbol];
    if (!positionState) continue;

    const bars = await fetchBars(symbol, { timeframe: '1Day', limit: 2 });
    if (bars.length === 0) continue;
    const lastPrice = bars[bars.length - 1].c;

    const updatedState = await updateTrailingStop(positionState, lastPrice);
    state.positions[symbol] = updatedState;
    updated = true;

    const entry = Number(positionState.entryPrice);
    const hardStop = entry * (1 + config.hardStopPct);
    const trailingStop = updatedState.trailingStop;
    const holdDays = daysHeld(positionState.entryTime);
    const maxHold = MAX_HOLD_DAYS[positionState.strategy] || 30;

    const shouldExitHard = lastPrice <= hardStop;
    const shouldExitTrail = trailingStop && lastPrice <= trailingStop;
    const shouldExitTime = holdDays >= maxHold;

    if (shouldExitHard || shouldExitTrail || shouldExitTime) {
      await closePosition(symbol);
      const qty = Number(positionState.qty || pos.qty || 0);
      const pnl = qty * (lastPrice - entry);
      const pnlPct = entry ? (lastPrice - entry) / entry : 0;
      const reason = shouldExitHard ? 'hard_stop' : shouldExitTrail ? 'trailing_stop' : 'time_exit';
      logEvent('trade_closed', {
        symbol,
        reason,
        price: lastPrice,
        qty,
        pnl,
        pnlPct,
        strategy: positionState.strategy,
      });
      await sendTelegram(`Closed ${symbol} (${positionState.strategy}) reason=${reason} pnl=${pnl.toFixed(2)}`);
      delete state.positions[symbol];
      updated = true;
    }
  }

  if (updated) savePositionState(state);
}

module.exports = { manageExits, loadPositionState, savePositionState };
