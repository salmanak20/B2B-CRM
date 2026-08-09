import { apiGet } from './api.js';
import { initApp } from './app.js';
import { isManagerOrAdmin } from './rbac.js';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();

  if (!isManagerOrAdmin()) {
    alert('Access denied. Administrator or Sales Manager role required.');
    window.location.href = '../analytics_reports_crm_pro/code.html';
    return;
  }

  await Promise.all([loadUsers(), loadRoles(), loadAuditLogs()]);
});

async function loadUsers() {
  const tableBody = document.querySelector('#users-table tbody') || document.querySelectorAll('tbody')[0];
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-body-md text-on-surface-variant">Loading users...</td></tr>`;

  try {
    const users = await apiGet('/users');
    const list = Array.isArray(users) ? users : (users.items || []);

    if (list.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-body-md text-on-surface-variant">No users found</td></tr>`;
      return;
    }

    tableBody.innerHTML = list.map(u => `
      <tr class="hover:bg-surface-variant/20 transition-colors">
        <td class="py-3 px-4 font-semibold text-on-surface">${escapeHtml(u.full_name || u.email)}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(u.email)}</td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary-container/20 text-primary">
            ${escapeHtml(u.role ? u.role.name : 'Viewer')}
          </span>
        </td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${u.is_active ? 'bg-secondary-container/20 text-secondary' : 'bg-error-container text-on-error-container'}">
            ${u.is_active ? 'Active' : 'Inactive'}
          </span>
        </td>
        <td class="py-3 px-4 text-right text-body-sm text-outline">
          ${u.created_at ? new Date(u.created_at).toLocaleDateString() : ''}
        </td>
      </tr>
    `).join('');

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-body-md text-error">${err.message || 'Failed to load users'}</td></tr>`;
  }
}

async function loadRoles() {
  const container = document.querySelector('#roles-list') || document.querySelector('[data-section="roles"]');
  if (!container) return;

  try {
    const roles = await apiGet('/roles');
    const list = Array.isArray(roles) ? roles : (roles.items || []);

    container.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        ${list.map(r => `
          <div class="p-4 rounded-xl border border-outline-variant/30 bg-surface/80">
            <div class="font-headline-md font-bold text-on-surface mb-1">${escapeHtml(r.name)}</div>
            <div class="font-body-sm text-on-surface-variant">${escapeHtml(r.description || 'No description')}</div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="p-4 text-center text-error">${err.message}</div>`;
  }
}

async function loadAuditLogs() {
  const tableBody = document.querySelector('#audit-logs-table tbody') || document.querySelectorAll('tbody')[1];
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">Loading audit logs...</td></tr>`;

  try {
    const logs = await apiGet('/audit-logs', { limit: 50 });
    const list = Array.isArray(logs) ? logs : (logs.items || []);

    if (list.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">No audit logs found</td></tr>`;
      return;
    }

    tableBody.innerHTML = list.map(l => `
      <tr class="hover:bg-surface-variant/20 transition-colors">
        <td class="py-3 px-4 font-semibold text-on-surface">${escapeHtml(l.user ? l.user.full_name : (l.user_id ? `User #${l.user_id}` : 'System'))}</td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase ${getActionBadgeClass(l.action)}">
            ${escapeHtml(l.action)}
          </span>
        </td>
        <td class="py-3 px-4 text-on-surface-variant font-semibold">${escapeHtml(l.entity || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">#${l.entity_id || 'N/A'}</td>
        <td class="py-3 px-4 text-on-surface-variant max-w-xs truncate">${escapeHtml(l.description || '')}</td>
        <td class="py-3 px-4 text-right text-body-sm text-outline">
          ${l.created_at ? new Date(l.created_at).toLocaleString() : ''}
        </td>
      </tr>
    `).join('');

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-error">${err.message || 'Failed to load audit logs'}</td></tr>`;
  }
}

function getActionBadgeClass(action) {
  switch ((action || '').toLowerCase()) {
    case 'create': return 'bg-secondary-container/20 text-secondary';
    case 'update': return 'bg-primary-container/20 text-primary';
    case 'delete': return 'bg-error-container text-on-error-container';
    default: return 'bg-surface-variant text-on-surface-variant';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
