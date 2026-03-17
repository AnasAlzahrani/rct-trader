const config = require('../config');

function alpacaHeaders() {
  return {
    'APCA-API-KEY-ID': config.alpaca.apiKey,
    'APCA-API-SECRET-KEY': config.alpaca.secretKey,
    'Content-Type': 'application/json',
  };
}

async function alpacaRequest(path, options = {}) {
  const url = `${config.alpaca.baseUrl}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: { ...alpacaHeaders(), ...(options.headers || {}) },
  });
  if (!res.ok) {
    throw new Error(`Alpaca request failed ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function getAccount() {
  return alpacaRequest('/v2/account');
}

async function listPositions() {
  return alpacaRequest('/v2/positions');
}

async function getPosition(symbol) {
  return alpacaRequest(`/v2/positions/${symbol}`);
}

async function placeOrder({ symbol, qty, side = 'buy', type = 'market', time_in_force = 'day' }) {
  return alpacaRequest('/v2/orders', {
    method: 'POST',
    body: JSON.stringify({ symbol, qty: String(qty), side, type, time_in_force }),
  });
}

async function closePosition(symbol) {
  return alpacaRequest(`/v2/positions/${symbol}`, { method: 'DELETE' });
}

module.exports = {
  getAccount,
  listPositions,
  getPosition,
  placeOrder,
  closePosition,
};
