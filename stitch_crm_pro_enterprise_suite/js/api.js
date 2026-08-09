import { API_BASE_URL, TOKEN_KEY, USER_KEY } from './config.js';

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getLoginUrl() {
  // Relative URL to login page based on directory depth
  const path = window.location.pathname;
  if (path.includes('/crm_pro_enterprise/')) {
    return 'code.html';
  }
  return '../crm_pro_enterprise/code.html';
}

export async function apiFetch(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers
  };

  try {
    const response = await fetch(url, config);

    if (response.status === 401) {
      // Unauthorized: Clear session and redirect to login if not already on login page
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      if (!window.location.pathname.includes('/crm_pro_enterprise/')) {
        window.location.href = getLoginUrl();
      }
      throw new ApiError('Unauthorized. Please log in again.', 401, null);
    }

    if (response.status === 204) {
      return null;
    }

    // Check if response is blob / CSV
    const contentType = response.headers.get('content-type');
    if (contentType && (contentType.includes('text/csv') || contentType.includes('application/octet-stream'))) {
      if (!response.ok) {
        throw new ApiError('Export failed', response.status, null);
      }
      return await response.blob();
    }

    let data;
    try {
      data = await response.json();
    } catch (e) {
      data = null;
    }

    if (!response.ok) {
      let message = `Request failed with status ${response.status}`;
      if (data && data.detail) {
        if (typeof data.detail === 'string') {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          message = data.detail.map(err => `${err.loc ? err.loc.join('.') + ': ' : ''}${err.msg}`).join(', ');
        }
      }
      throw new ApiError(message, response.status, data);
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(error.message || 'Network error occurred', 0, null);
  }
}

export function apiGet(endpoint, params = {}) {
  const query = new URLSearchParams();
  Object.keys(params).forEach(key => {
    if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
      query.append(key, params[key]);
    }
  });
  const queryString = query.toString();
  const fullEndpoint = queryString ? `${endpoint}?${queryString}` : endpoint;
  return apiFetch(fullEndpoint, { method: 'GET' });
}

export function apiPost(endpoint, data = {}) {
  return apiFetch(endpoint, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

export function apiPut(endpoint, data = {}) {
  return apiFetch(endpoint, {
    method: 'PUT',
    body: JSON.stringify(data)
  });
}

export function apiPatch(endpoint, data = {}) {
  return apiFetch(endpoint, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export function apiDelete(endpoint) {
  return apiFetch(endpoint, {
    method: 'DELETE'
  });
}
