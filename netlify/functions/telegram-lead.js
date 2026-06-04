const TELEGRAM_API = 'https://api.telegram.org';

function json(statusCode, body) {
  return {
    statusCode,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store'
    },
    body: JSON.stringify(body)
  };
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function clean(value, maxLength = 400) {
  return String(value || '').trim().slice(0, maxLength);
}

function validate(payload) {
  const name = clean(payload.name, 160);
  const phone = clean(payload.phone, 60);
  const email = clean(payload.email, 180);
  const residence = clean(payload.residenceLabel || payload.residence, 120);
  const preferredTime = clean(payload.preferredTime, 160);
  const message = clean(payload.message, 1200);
  const source = clean(payload.source, 80);
  const locale = clean(payload.locale, 8);
  const page = clean(payload.page, 500);
  const referrer = clean(payload.referrer, 500);
  const honeypot = clean(payload.honeypot, 200);
  const submittedAt = clean(payload.submittedAt, 80);

  if (honeypot) return { ok: true, spam: true };
  if (name.length < 2) return { ok: false, error: 'name_required' };
  if (!/^[+0-9\s\-().]{6,60}$/.test(phone)) return { ok: false, error: 'phone_required' };
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return { ok: false, error: 'email_invalid' };

  return {
    ok: true,
    data: { name, phone, email, residence, preferredTime, message, source, locale, page, referrer, submittedAt }
  };
}

function getClientIp(event) {
  const headers = event.headers || {};
  const forwarded = headers['x-forwarded-for'] || headers['X-Forwarded-For'] || '';
  return String(forwarded).split(',')[0].trim() || event.headers?.['client-ip'] || '';
}

function buildMessage(data, event) {
  const ip = getClientIp(event);
  const country =
    event.headers?.['x-country'] ||
    event.headers?.['x-nf-client-connection-country'] ||
    event.headers?.['X-Country'] ||
    '';

  return [
    '<b>🏡 Rock House Prague · новая заявка</b>',
    '<b>Получатель:</b> Viktor',
    '',
    `<b>Имя:</b> ${escapeHtml(data.name)}`,
    `<b>Телефон:</b> <code>${escapeHtml(data.phone)}</code>`,
    data.email ? `<b>Email:</b> <code>${escapeHtml(data.email)}</code>` : null,
    data.residence ? `<b>Townhouse:</b> ${escapeHtml(data.residence)}` : null,
    data.preferredTime ? `<b>Желаемое время:</b> ${escapeHtml(data.preferredTime)}` : null,
    data.message ? `<b>Сообщение:</b> ${escapeHtml(data.message)}` : null,
    '',
    `<b>Источник:</b> ${escapeHtml(data.source || 'contact-form')}`,
    `<b>Язык:</b> ${escapeHtml(data.locale || 'cs')}`,
    data.submittedAt ? `<b>Время:</b> ${escapeHtml(data.submittedAt)}` : null,
    data.page ? `<b>Страница:</b> ${escapeHtml(data.page)}` : null,
    data.referrer ? `<b>Referrer:</b> ${escapeHtml(data.referrer)}` : null,
    ip ? `<b>IP:</b> <code>${escapeHtml(ip)}</code>${country ? ` · ${escapeHtml(country)}` : ''}` : null
  ]
    .filter(Boolean)
    .join('\n');
}

async function sendTelegramMessage(text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID || '6688224061';

  if (!token) {
    console.log('[telegram:missing-env]\n' + text);
    return { ok: false, error: 'telegram_env_missing' };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${TELEGRAM_API}/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const body = await response.text();
      console.error(`[telegram] HTTP ${response.status}: ${body}`);
      return { ok: false, error: `telegram_http_${response.status}` };
    }

    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[telegram] ${message}`);
    return { ok: false, error: message };
  } finally {
    clearTimeout(timeout);
  }
}

exports.handler = async function handler(event) {
  if (event.httpMethod !== 'POST') {
    return json(405, { ok: false, error: 'method_not_allowed' });
  }

  let payload;
  try {
    payload = JSON.parse(event.body || '{}');
  } catch {
    return json(400, { ok: false, error: 'invalid_json' });
  }

  const validation = validate(payload);
  if (!validation.ok) return json(400, { ok: false, error: validation.error });
  if (validation.spam) return json(200, { ok: true });

  const result = await sendTelegramMessage(buildMessage(validation.data, event));
  if (!result.ok) return json(502, { ok: false, error: result.error || 'telegram_failed' });

  return json(200, { ok: true });
};
