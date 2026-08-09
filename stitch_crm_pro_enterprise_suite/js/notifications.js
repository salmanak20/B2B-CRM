import { apiGet, apiPatch, apiDelete } from './api.js';

export async function initNotifications() {
  const bellIcons = document.querySelectorAll('.material-symbols-outlined');
  let bellBtn = null;

  bellIcons.forEach(icon => {
    if (icon.textContent.trim() === 'notifications') {
      bellBtn = icon.closest('button') || icon.parentElement;
    }
  });

  if (!bellBtn) return;

  // Add badge container if not existing
  let badge = bellBtn.querySelector('.notification-badge');
  if (!badge) {
    badge = document.createElement('span');
    badge.className = 'notification-badge hidden absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-error text-[10px] font-bold text-on-error';
    bellBtn.style.position = 'relative';
    bellBtn.appendChild(badge);
  }

  // Load unread count
  await refreshUnreadCount(badge);

  // Dropdown overlay
  const parent = bellBtn.parentElement;
  if (!parent) return;

  const dropdown = document.createElement('div');
  dropdown.className = 'notification-dropdown hidden absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-xl bg-surface/95 backdrop-blur-xl border border-outline-variant/50 p-4 shadow-2xl z-50';
  parent.style.position = 'relative';
  parent.appendChild(dropdown);

  bellBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    const isHidden = dropdown.classList.contains('hidden');
    if (isHidden) {
      dropdown.classList.remove('hidden');
      await loadNotificationList(dropdown, badge);
    } else {
      dropdown.classList.add('hidden');
    }
  });

  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });
}

export async function refreshUnreadCount(badgeElement) {
  try {
    const list = await apiGet('/notifications', { limit: 50 });
    const notifications = Array.isArray(list) ? list : (list.items || []);
    const unreadCount = notifications.filter(n => !n.is_read).length;

    if (badgeElement) {
      if (unreadCount > 0) {
        badgeElement.textContent = unreadCount > 99 ? '99+' : unreadCount;
        badgeElement.classList.remove('hidden');
      } else {
        badgeElement.classList.add('hidden');
      }
    }
    return notifications;
  } catch (e) {
    return [];
  }
}

async function loadNotificationList(container, badge) {
  container.innerHTML = '<div class="p-3 text-center text-body-sm text-on-surface-variant">Loading notifications...</div>';

  try {
    const list = await apiGet('/notifications', { limit: 10 });
    const notifications = Array.isArray(list) ? list : (list.items || []);

    if (notifications.length === 0) {
      container.innerHTML = `
        <div class="flex items-center justify-between border-b border-outline-variant/30 pb-3 mb-3">
          <h3 class="font-headline-md text-body-lg font-bold text-on-surface">Notifications</h3>
        </div>
        <div class="p-4 text-center text-body-sm text-on-surface-variant">No notifications</div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="flex items-center justify-between border-b border-outline-variant/30 pb-3 mb-3">
        <h3 class="font-headline-md text-body-lg font-bold text-on-surface">Notifications</h3>
        <button id="btn-mark-all-read" class="text-label-md font-label-md text-primary hover:underline">Mark all read</button>
      </div>
      <div class="space-y-2 max-h-72 overflow-y-auto">
        ${notifications.map(n => `
          <div class="p-3 rounded-lg border border-outline-variant/20 ${n.is_read ? 'bg-surface' : 'bg-primary-container/10'} flex items-start justify-between gap-2">
            <div>
              <div class="font-body-md text-body-md font-semibold text-on-surface">${escapeHtml(n.title)}</div>
              <div class="font-body-sm text-body-sm text-on-surface-variant mt-1">${escapeHtml(n.message)}</div>
              <div class="font-label-md text-[11px] text-outline mt-1">${n.created_at ? new Date(n.created_at).toLocaleString() : ''}</div>
            </div>
            ${!n.is_read ? `
              <button data-mark-read="${n.id}" class="text-primary hover:text-primary-container p-1" title="Mark read">
                <span class="material-symbols-outlined text-[18px]">check_circle</span>
              </button>
            ` : ''}
          </div>
        `).join('')}
      </div>
      <div class="border-t border-outline-variant/30 pt-3 mt-3 text-center">
        <a href="../notifications_crm_pro/code.html" class="text-label-md font-label-md text-primary hover:underline">View all notifications</a>
      </div>
    `;

    // Bind mark read actions
    container.querySelectorAll('[data-mark-read]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-mark-read');
        await apiPatch(`/notifications/${id}/read`);
        await refreshUnreadCount(badge);
        await loadNotificationList(container, badge);
      });
    });

    const markAllBtn = container.querySelector('#btn-mark-all-read');
    if (markAllBtn) {
      markAllBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await apiPatch('/notifications/read-all');
        await refreshUnreadCount(badge);
        await loadNotificationList(container, badge);
      });
    }

  } catch (err) {
    container.innerHTML = `<div class="p-3 text-center text-body-sm text-error">${err.message || 'Failed to load notifications'}</div>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
