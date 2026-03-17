const config = require('../config');
const { readJsonLines } = require('../lib/io');

function computeStats() {
  const events = readJsonLines(config.tradesLogPath);
  const trades = events.filter((e) => e.type === 'trade_closed');
  if (trades.length === 0) {
    return {
      trades: 0,
      winRate: 0,
      profitFactor: 0,
      sharpe: 0,
      maxDrawdown: 0,
    };
  }

  let wins = 0;
  let grossProfit = 0;
  let grossLoss = 0;
  const returns = [];
  let equityCurve = [0];
  let cumulative = 0;
  let peak = 0;
  let maxDrawdown = 0;

  for (const trade of trades) {
    const pnl = Number(trade.pnl || 0);
    const pnlPct = Number(trade.pnlPct || 0);
    returns.push(pnlPct);
    cumulative += pnl;
    equityCurve.push(cumulative);
    if (cumulative > peak) peak = cumulative;
    const drawdown = peak - cumulative;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    if (pnl > 0) {
      wins += 1;
      grossProfit += pnl;
    } else {
      grossLoss += Math.abs(pnl);
    }
  }

  const winRate = wins / trades.length;
  const profitFactor = grossLoss === 0 ? grossProfit : grossProfit / grossLoss;
  const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - avg, 2), 0) / returns.length;
  const std = Math.sqrt(variance);
  const sharpe = std === 0 ? 0 : (avg / std) * Math.sqrt(252);

  return {
    trades: trades.length,
    winRate,
    profitFactor,
    sharpe,
    maxDrawdown,
  };
}

module.exports = { computeStats };
