require('dotenv').config({ path: '../.env' });

const config = {
  alpaca: {
    apiKey: process.env.ALPACA_API_KEY || '',
    secretKey: process.env.ALPACA_SECRET_KEY || '',
    baseUrl: process.env.ALPACA_BASE_URL || 'https://paper-api.alpaca.markets',
    dataUrl: process.env.ALPACA_DATA_URL || 'https://data.alpaca.markets',
  },
  telegram: {
    token: process.env.TELEGRAM_BOT_TOKEN || '',
    chatIds: (process.env.TELEGRAM_CHAT_IDS || '')
      .split(',')
      .map((id) => id.trim())
      .filter(Boolean),
  },
  fmp: {
    apiKey: process.env.FMP_API_KEY || '',
  },
  scanTime: process.env.SCAN_TIME || '09:35',
  timeZone: process.env.SCAN_TIMEZONE || 'local',
  maxPositions: Number(process.env.MAX_POSITIONS || 10),
  maxPositionPct: Number(process.env.MAX_POSITION_PCT || 0.02),
  hardStopPct: Number(process.env.HARD_STOP_PCT || -0.05),
  trailingActivationPct: Number(process.env.TRAILING_ACTIVATION_PCT || 0.03),
  trailingDistancePct: Number(process.env.TRAILING_DISTANCE_PCT || 0.02),
  sectorLimitPct: Number(process.env.SECTOR_LIMIT_PCT || 0.3),
  dailyLossLimitPct: Number(process.env.DAILY_LOSS_LIMIT_PCT || -0.02),
  tradesLogPath: process.env.TRADES_LOG_PATH || 'trades.json',
  statePath: process.env.STATE_PATH || 'data/state.json',
  positionsPath: process.env.POSITIONS_PATH || 'data/positions.json',
  sectorMapPath: process.env.SECTOR_MAP_PATH || 'data/sector-map.json',
  sp500Path: process.env.SP500_PATH || 'data/sp500.json',
};

module.exports = config;
