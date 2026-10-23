export const IS_DESKTOP = import.meta.env.MODE === 'desktop';
if (IS_DESKTOP && typeof document !== 'undefined') void import('./desktop_navigation.js');

function desktopApiBase() {
  const value = import.meta.env.VITE_API_BASE_URL;
  if (!value) throw new Error('Desktop API is not configured. Set VITE_API_BASE_URL to the approved HTTPS /api/v1 endpoint.');
  let url;
  try { url = new URL(value); } catch { throw new Error('VITE_API_BASE_URL must be an absolute HTTPS URL.'); }
  if (url.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(url.hostname)) {
    throw new Error('Desktop API must use HTTPS outside local development.');
  }
  if (url.pathname.replace(/\/$/, '') !== '/api/v1' || url.search || url.hash) {
    throw new Error('VITE_API_BASE_URL must end with /api/v1 and contain no query or fragment.');
  }
  return url.toString().replace(/\/$/, '');
}

// Browser sessions use the existing same-origin Vercel proxy. The desktop
// build targets the explicitly configured hosted API using the same backend.
export const API_BASE_URL = IS_DESKTOP ? desktopApiBase() : '/api/v1';
export function desktopRequestSignal() { return IS_DESKTOP ? AbortSignal.timeout(30000) : undefined; }
export function reportDesktopConnectionError() { if (IS_DESKTOP) window.dispatchEvent(new Event('crm:connection-error')); }

const APP_ROUTES = new Set([
  '/platform-admin/login', '/platform-admin', '/usage', '/subscription', '/login',
  '/dashboard', '/analytics', '/reports', '/companies', '/contacts', '/leads',
  '/deals', '/tasks', '/notifications', '/users', '/settings', '/team',
  '/automations', '/calendar',
]);

export function routeUrl(path) {
  if (!IS_DESKTOP) return path;
  const url = new URL(path, globalThis.location?.href || 'https://tauri.localhost/');
  if (url.origin !== (globalThis.location?.origin || url.origin) || !APP_ROUTES.has(url.pathname)) return path;
  return `${url.pathname}.html${url.search}${url.hash}`;
}

export function navigate(path, { replace = false } = {}) {
  const destination = routeUrl(path);
  if (replace) location.replace(destination);
  else location.assign(destination);
}

export function resolveApiUrl(path) {
  if (!IS_DESKTOP || /^https?:\/\//i.test(path)) return path;
  const base = new URL(API_BASE_URL);
  const pathname = path.startsWith('/api/v1/') ? path : `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  return new URL(pathname, base.origin).toString();
}

export async function openExternal(value) {
  const url = new URL(value, globalThis.location?.href);
  if (url.protocol !== 'https:') throw new Error('Only approved HTTPS links can be opened externally.');
  if (!IS_DESKTOP) { location.assign(url.toString()); return; }
  const approvedHosts = new Set([
    new URL(API_BASE_URL).hostname,
    'b2-b-crm.vercel.app',
    ...(import.meta.env.VITE_EXTERNAL_LINK_HOSTS || '').split(',').map(host => host.trim().toLowerCase()).filter(Boolean),
  ]);
  if (!approvedHosts.has(url.hostname.toLowerCase())) throw new Error('This external destination is not approved for the desktop app.');
  const { invoke } = await import('@tauri-apps/api/core');
  await invoke('open_approved_url', { value: url.toString() });
}

// Previous browser-stored credentials are deleted during startup, never reused.
export const TOKEN_KEY = 'crm_access_token';
export const USER_KEY = 'crm_current_user';
