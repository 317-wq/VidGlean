// HTTP 客户端与 SSE 解析
const params = new URLSearchParams(location.search);
const urlToken = params.get('token') || '';
if (urlToken) sessionStorage.setItem('vg-token', urlToken);
// 地址栏里的 token 用一次就抹掉；刷新页面时从 sessionStorage 取回
export const TOKEN = urlToken || sessionStorage.getItem('vg-token') || '';
if (urlToken) {
  history.replaceState(null, '', location.pathname + location.hash);
}

function headers(extra = {}) {
  const result = { 'Content-Type': 'application/json', ...extra };
  if (TOKEN) result['X-VG-Token'] = TOKEN;
  return result;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: headers(options.headers || {}),
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }
  if (!response.ok || !payload || payload.ok === false) {
    const detail = payload && payload.error ? payload.error : {};
    const error = new Error(detail.message || `请求失败（${response.status}）`);
    error.code = detail.code || `HTTP_${response.status}`;
    error.detail = detail.detail || '';
    throw error;
  }
  return payload.data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body || {}) }),
  put: (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body || {}) }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body || {}) }),
  del: (path) => request(path, { method: 'DELETE' }),
};

export function eventSource() {
  const query = TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : '';
  return new EventSource(`/api/events${query}`);
}

export async function chatStream(docId, message, handlers) {
  const response = await fetch(`/api/documents/${docId}/chat`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ message }),
  });
  if (!response.ok || !response.body) {
    let detail = {};
    try {
      detail = (await response.json()).error || {};
    } catch (error) {
      detail = {};
    }
    throw new Error(detail.message || '对话请求失败');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let done = false;
  while (!done) {
    const chunk = await reader.read();
    done = chunk.done;
    buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !done });
    let index = buffer.indexOf('\n\n');
    while (index >= 0) {
      const raw = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      index = buffer.indexOf('\n\n');
      const event = { type: 'message', data: '' };
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) event.type = line.slice(6).trim();
        else if (line.startsWith('data:')) event.data += line.slice(5).trim();
      }
      let payload = {};
      try {
        payload = JSON.parse(event.data || '{}');
      } catch (error) {
        payload = {};
      }
      if (event.type === 'delta' && handlers.onDelta) handlers.onDelta(payload.text || '');
      else if (event.type === 'done' && handlers.onDone) handlers.onDone(payload);
      else if (event.type === 'error' && handlers.onError) handlers.onError(payload);
    }
  }
}
