const config = require('../config');

async function sendTelegram(text) {
  if (!config.telegram.token || config.telegram.chatIds.length === 0) {
    return { ok: false, skipped: true, results: [] };
  }

  const url = `https://api.telegram.org/bot${config.telegram.token}/sendMessage`;
  const results = await Promise.all(
    config.telegram.chatIds.map(async (chatId) => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: chatId, text }),
        });
        const body = await response.json().catch(() => ({}));
        return { chatId, ok: response.ok && body.ok !== false, status: response.status, description: body.description || null };
      } catch (err) {
        return { chatId, ok: false, status: null, description: err.message };
      }
    })
  );

  const ok = results.every((result) => result.ok);
  if (!ok) {
    console.error('Telegram delivery failed:', results.map((result) => ({ ...result, chatId: String(result.chatId).replace(/.(?=.{4})/g, '*') })));
  }
  return { ok, skipped: false, results };
}

module.exports = { sendTelegram };
