// Centralized API Configuration
export const API_BASE_URL = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL)
  ? import.meta.env.VITE_API_BASE_URL
  : 'https://b2b-crm-cjy7.onrender.com/api/v1';

export const TOKEN_KEY = 'crm_access_token';
export const USER_KEY = 'crm_current_user';
