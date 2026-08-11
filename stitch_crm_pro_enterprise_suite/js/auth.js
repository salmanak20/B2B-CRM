import { API_BASE_URL, TOKEN_KEY, USER_KEY } from './config.js';
import { apiPost, apiGet, getLoginUrl } from './api.js';

export async function login(username, password) {
  // Backend auth/login endpoint accepts Form Data (OAuth2PasswordRequestForm) or JSON
  // Let's send form data for standard OAuth2 login endpoint
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData
  });

  if (!response.ok) {
    let errorMsg = 'Login failed. Invalid credentials.';
    try {
      const errData = await response.json();
      if (errData && errData.detail) {
        errorMsg = errData.detail;
      }
    } catch(e) {}
    throw new Error(errorMsg);
  }

  const data = await response.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  
  // Fetch current user details
  const user = await fetchCurrentUser();
  return user;
}

export async function fetchCurrentUser() {
  try {
    const user = await apiGet('/auth/me');
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  } catch (error) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    throw error;
  }
}

export function getCurrentUser() {
  const userStr = localStorage.getItem(USER_KEY);
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch (e) {
    return null;
  }
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = getLoginUrl();
}

export async function checkAuth() {
  const token = localStorage.getItem(TOKEN_KEY);
  const isLoginPage = window.location.pathname.includes('/crm_pro_enterprise/');

  if (!token) {
    if (!isLoginPage) {
      window.location.href = getLoginUrl();
    }
    return null;
  }

  let currentUser = getCurrentUser();
  if (!currentUser) {
    try {
      currentUser = await fetchCurrentUser();
    } catch (err) {
      if (!isLoginPage) {
        window.location.href = getLoginUrl();
      }
      return null;
    }
  }

  if (isLoginPage && currentUser) {
    // Already logged in, redirect to dashboard
    window.location.href = '../analytics_reports_crm_pro/code.html';
  }

  return currentUser;
}
