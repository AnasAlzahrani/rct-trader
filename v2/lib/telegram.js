const { execFile } = require('child_process');
const { promisify } = require('util');
const config = require('../config');

const execFileAsync = promisify(execFile);

function redactChatId(chatId) {
  return String(chatId).replace(/.(?=.{4})/g, '*');
}

async function sendViaBotApi(chatId, text) {
  if (!config.telegram.token) {
    return { chatId, ok: false, status: null, description: 'TELEGRAM_BOT_TOKEN missing' };
  }

  const url = `https://api.telegram.org/bot${config.telegram.token}/sendMessage`;
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
    const body = await response.json().catch(() => ({}));
    return { chatId, ok: response.ok && body.ok !== false, status: response.status, description: body.description || null, via: 'bot-api' };
  } catch (err) {
    return { chatId, ok: false, status: null, description: err.message, via: 'bot-api' };
  }
}

async function sendViaOpenClaw(chatId, text) {
  try {
    const { stdout } = await execFileAsync(
      'openclaw',
      ['message', 'send', '--channel', 'telegram', '--target', String(chatId), '--message', text, '--json'],
      { timeout: 30000, maxBuffer: 1024 * 1024 }
    );
    const body = JSON.parse(stdout);
    return { chatId, ok: body?.payload?.ok === true || body?.ok === true, status: null, description: null, via: 'openclaw' };
  } catch (err) {
    return { chatId, ok: false, status: null, description: err.message, via: 'openclaw' };
  }
}

async function sendTelegram(text) {
  if (config.telegram.chatIds.length === 0) {
    return { ok: false, skipped: true, results: [] };
  }

  const results = await Promise.all(
    config.telegram.chatIds.map(async (chatId) => {
      const botResult = await sendViaBotApi(chatId, text);
      if (botResult.ok) return botResult;

      // The historical raw bot token can expire/revoke. OpenClaw's configured
      // Telegram delivery is the operational fallback and was smoke-tested.
      const openClawResult = await sendViaOpenClaw(chatId, text);
      return openClawResult.ok ? openClawResult : { ...openClawResult, botApiFailure: botResult.description || botResult.status };
    })
  );

  const ok = results.every((result) => result.ok);
  if (!ok) {
    console.error('Telegram delivery failed:', results.map((result) => ({ ...result, chatId: redactChatId(result.chatId) })));
  }
  return { ok, skipped: false, results };
}

module.exports = { sendTelegram };
