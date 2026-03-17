const config = require('./config');
const { runScanner } = require('./signals/scanner');
const { scoreSignals } = require('./signals/scorer');
const { getAccount, listPositions, placeOrder } = require('./execution/paper-trader');
const { manageExits, loadPositionState, savePositionState } = require('./execution/exits');
const { canAddPosition, positionSize, shouldHaltTrading } = require('./execution/risk');
const { fetchBars } = require('./data/market');
const { logEvent } = require('./lib/logger');
const { sendTelegram } = require('./lib/telegram');
const { readJson, writeJson } = require('./lib/io');
const { nextRunAt, toDateString } = require('./lib/time');
const { computeStats } = require('./execution/stats');

async function refreshDayStartEquity() {
  const state = readJson(config.statePath, {});
  const today = toDateString();
  if (state.dayStartDate !== today) {
    const account = await getAccount();
    state.dayStartDate = today;
    state.dayStartEquity = Number(account.equity || account.last_equity || 0);
    writeJson(config.statePath, state);
  }
  return state;
}

function openPositionsSet(alpacaPositions) {
  return new Set(alpacaPositions.map((p) => p.symbol));
}

async function runScanAndTrade() {
  const account = await getAccount();
  const equity = Number(account.equity || account.last_equity || 0);
  const state = await refreshDayStartEquity();

  if (shouldHaltTrading({ equity, dayStartEquity: state.dayStartEquity })) {
    logEvent('trading_halted', { equity, dayStartEquity: state.dayStartEquity });
    return;
  }

  const positions = await listPositions();
  const openSet = openPositionsSet(positions);
  const signals = await runScanner();
  const ranked = scoreSignals(signals);
  const positionState = loadPositionState();

  for (const signal of ranked) {
    if (openSet.has(signal.symbol)) continue;
    const riskCheck = canAddPosition({ positions, equity, symbol: signal.symbol });
    if (!riskCheck.ok) continue;

    let lastPrice = null;
    try {
      const bars = await fetchBars(signal.symbol, { timeframe: '1Day', limit: 2 });
      if (bars.length === 0) continue;
      lastPrice = bars[bars.length - 1].c;
    } catch (err) {
      continue;
    }

    const qty = positionSize({ equity, price: lastPrice });
    if (qty < 1) continue;

    const order = await placeOrder({ symbol: signal.symbol, qty, side: 'buy' });
    logEvent('order_submitted', {
      symbol: signal.symbol,
      qty,
      strategy: signal.strategy,
      orderId: order.id,
      price: lastPrice,
    });

    positionState.positions[signal.symbol] = {
      symbol: signal.symbol,
      qty,
      entryPrice: lastPrice,
      entryTime: new Date().toISOString(),
      strategy: signal.strategy,
      trailingActive: false,
      trailingStop: null,
    };
    savePositionState(positionState);

    logEvent('trade_opened', {
      symbol: signal.symbol,
      qty,
      entryPrice: lastPrice,
      strategy: signal.strategy,
      score: signal.totalScore,
    });

    await sendTelegram(`Opened ${signal.strategy} trade: ${signal.symbol} qty ${qty} @ ${lastPrice.toFixed(2)}`);
  }

  const stats = computeStats();
  logEvent('stats_snapshot', stats);
}

function scheduleDailyScan() {
  const next = nextRunAt(config.scanTime);
  if (!next) {
    throw new Error(`Invalid scan time: ${config.scanTime}`);
  }
  const delay = next.getTime() - Date.now();
  setTimeout(async () => {
    try {
      await runScanAndTrade();
    } catch (err) {
      logEvent('scan_error', { message: err.message });
    }
    scheduleDailyScan();
  }, delay);
}

function scheduleExitManager() {
  setInterval(async () => {
    try {
      await manageExits();
    } catch (err) {
      logEvent('exit_error', { message: err.message });
    }
  }, 5 * 60 * 1000);
}

async function start() {
  logEvent('bot_start', { scanTime: config.scanTime });
  scheduleDailyScan();
  scheduleExitManager();
}

start();
