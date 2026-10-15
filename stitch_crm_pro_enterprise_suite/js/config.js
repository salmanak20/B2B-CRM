// Browser sessions require one origin. Vite/Vercel proxy this path to the backend.
export const API_BASE_URL = '/api/v1';
// Previous browser-stored credentials are deleted during startup, never reused.
export const TOKEN_KEY = 'crm_access_token';
export const USER_KEY = 'crm_current_user';
