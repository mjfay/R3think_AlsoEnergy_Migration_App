// In Tauri production the Rust shell injects __BACKEND_PORT__ into the webview
// after it loads. We must read it lazily on each call — not once at module load —
// because it may not be set yet when this module is first imported.
// In dev (plain Vite) the variable is never set and we fall back to /api
// which the Vite proxy forwards to localhost:8000.
function base() {
  return window.__BACKEND_PORT__
    ? `http://127.0.0.1:${window.__BACKEND_PORT__}/api`
    : '/api'
}

async function req(path, options = {}) {
  const res = await fetch(`${base()}${path}`, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function get(path) {
  return req(path)
}

async function post(path, body) {
  return req(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

async function del(path) {
  return req(path, { method: 'DELETE' })
}

export const api = {
  health: () => req('/health'),
  stats: () => req('/stats'),

  syncSites: () => req('/sync/sites', { method: 'POST' }),
  syncSite: (id) => req(`/sync/site/${id}`, { method: 'POST' }),

  sites: () => req('/sites'),
  site: (id) => req(`/sites/${id}`),
  hardware: (siteId, hwId) => req(`/sites/${siteId}/hardware/${hwId}`),
  exportSite: (id) => `${base()}/export/site/${id}`,

  gateways: () => req('/gateways'),
  gateway: (id) => req(`/gateways/${encodeURIComponent(id)}`),

  credentialsStatus: () => req('/credentials/status'),
  post: (path, body) => post(path, body),
  delete: (path) => del(path),
  get: (path) => get(path),
}

export const getBase = () => base()
