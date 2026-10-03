const API_BASE = import.meta.env.VITE_API_URL || '';

function getHeaders() {
  const token = sessionStorage.getItem('vida_token');
  const userId = sessionStorage.getItem('vida_user_id');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  return headers;
}

async function request(method, path, body) {
  const opts = { method, headers: getHeaders() };
  if (body && method !== 'GET') opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  const data = await res.json();

  if (!res.ok) {
    const err = new Error(data?.error?.message || (typeof data?.error === 'string' && data.error) || `Request failed: ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
};

let sessionPromise = null;
export function createSession() {
  if (!sessionPromise) sessionPromise = startSession().finally(() => { sessionPromise = null; });
  return sessionPromise;
}

async function startSession(options = {}) {
  const res = await fetch(`${API_BASE}/api/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) throw new Error('Could not start your session. Please retry.');
  const data = await res.json();
  sessionStorage.setItem('vida_token', data.token);
  sessionStorage.setItem('vida_user_id', data.user_id);
  return { userId: data.user_id, token: data.token };
}

export function getSession() {
  const token = sessionStorage.getItem('vida_token');
  const userId = sessionStorage.getItem('vida_user_id');
  if (token && userId) return { token, userId };
  return null;
}

export async function pollJob(jobId, { interval = 2000, maxAttempts = 30, onProgress } = {}) {
  for (let i = 0; i < maxAttempts; i++) {
    const data = await api.get(`/api/jobs/${jobId}`);
    onProgress?.(data);
    if (data.status === 'completed') {
      if (data.result?.error) throw new Error(data.result.error);
      return data;
    }
    if (data.status === 'failed') throw new Error(data.error || 'Job failed');
    await new Promise(r => setTimeout(r, interval));
    if (i > 5) interval = Math.min(interval * 1.5, 5000);
  }
  throw new Error('Job timed out');
}

export function createDemoSession(demo_profile, timezone) { return startSession({demo_profile, timezone}); }
