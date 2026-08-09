import { apiGet, apiPatch, apiDelete } from './api.js';
import { initApp } from './app.js';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();
  await loadNotificationsPage();
});

async function loadNotificationsPage() {
  const container = document.querySelector('#notifications-page-list') || document.querySelector('.space-y-4');
  if (!container) return;

  container.innerHTML = `<div class="p-8 text-center text-body-md text-on-surface-variant">Loading notifications...</div>`;

  try {
    const list = await apiGet('/notifications', { limit: 50 });
    const notifications = Array.isArray(list) ? list : (list.items || []);

    if (notifications.length === 0) {
      container.innerHTML = `
        <div class="p-12 text-center bg-surface-container-low rounded-xl border border-outline-variant/30">
          <span class="material-symbols-outlined text-outline text-[48px] mb-2">notifications_off</span>
          <h3 class="font-headline-md text-headline-md font-bold text-on-surface">No Notifications</h3>
          <p class="font-body-md text-on-surface-variant mt-1">You're all caught up!</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="flex justify-between items-center pb-4 mb-4 border-b border-outline-variant/30">
        <span class="font-body-md font-semibold text-on-surface">${notifications.length} Notification(s)</span>
        <button id="btn-page-mark-all" class="font-label-md text-label-md text-primary hover:underline flex items-center gap-1">
          <span class="material-symbols-outlined text-[18px]">done_all</span> Mark all read
        </button>
      </div>
      <div class="space-y-3">
        ${notifications.map(n => `
          <div class="p-4 rounded-xl border border-outline-variant/30 ${n.is_read ? 'bg-surface/80' : 'bg-primary-container/10 border-primary-container/40'} flex items-start justify-between gap-4 transition-colors">
            <div class="flex items-start gap-3">
              <span class="material-symbols-outlined text-primary text-[24px] mt-0.5">${getNotificationIcon(n.notification_type)}</span>
              <div>
                <div class="font-body-md font-bold text-on-surface">${escapeHtml(n.title)}</div>
                <div class="font-body-md text-on-surface-variant mt-1">${escapeHtml(n.message)}</div>
                <div class="font-label-md text-[11px] text-outline mt-2">${n.created_at ? new Date(n.created_at).toLocaleString() : ''}</div>
              </div>
            </div>
            <div class="flex items-center gap-2">
              ${!n.is_read ? `
                <button data-mark-read-id="${n.id}" class="text-primary hover:text-primary-container p-1" title="Mark Read">
                  <span class="material-symbols-outlined text-[20px]">check_circle</span>
                </button>
              ` : ''}
              <button data-delete-id="${n.id}" class="text-error hover:opacity-80 p-1" title="Delete">
                <span class="material-symbols-outlined text-[20px]">delete</span>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    container.querySelectorAll('[data-mark-read-id]').forEach(btn => {
      btn.addEventListener('click', async () => {
        await apiPatch(`/notifications/${btn.getAttribute('data-mark-read-id')}/read`);
        await loadNotificationsPage();
      });
    });

    container.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (confirm('Delete notification?')) {
          await apiDelete(`/notifications/${btn.getAttribute('data-delete-id')}`);
          await loadNotificationsPage();
        }
      });
    });

    const markAllBtn = container.querySelector('#btn-page-mark-all');
    if (markAllBtn) {
      markAllBtn.addEventListener('click', async () => {
        await apiPatch('/notifications/read-all');
        await loadNotificationsPage();
      });
    }

  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-error font-body-md">${err.message || 'Failed to load notifications'}</div>`;
  }
}

function getNotificationIcon(type) {
  switch ((type || '').toLowerCase()) {
    case 'task': return 'task_alt';
    case 'deal': return 'monetization_on';
    case 'lead': return 'filter_alt';
    case 'system': return 'info';
    default: return 'notifications';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
