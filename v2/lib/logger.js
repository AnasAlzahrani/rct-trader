const { appendJsonLine } = require('./io');
const config = require('../config');

function logEvent(type, payload = {}) {
  const entry = {
    type,
    ts: new Date().toISOString(),
    ...payload,
  };
  appendJsonLine(config.tradesLogPath, entry);
  return entry;
}

module.exports = {
  logEvent,
};
