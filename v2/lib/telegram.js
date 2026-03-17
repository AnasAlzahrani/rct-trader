const config = require('../config');

async function sendTelegram(text) {
  if (!config.telegram.token || config.telegram.chatIds.length === 0) return;
  const url = `https://api.telegram.org/bot${config.telegram.token}/sendMessage`;
  await Promise.all(
    config.telegram.chatIds.map(async (chatId) => {
      try {
        await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: chatId, text }),
        });
      } catch (err) {
        // best-effort
      }
    })
  );
}

module.exports = { sendTelegram };
