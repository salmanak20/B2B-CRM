import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from './api.js';
import { initApp } from './app.js';
import { canCreateOrEdit, canDelete } from './rbac.js';

let currentTaskStatus = '';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();
  setupTaskModal();
  setupActivityModal();
  await Promise.all([loadTasks(), loadActivities()]);
});

async function loadTasks() {
  const tableBody = document.querySelector('#tasks-table tbody') || document.querySelector('tbody');
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">Loading tasks...</td></tr>`;

  try {
    const tasks = await apiGet('/tasks', { status: currentTaskStatus, limit: 50 });
    const taskList = Array.isArray(tasks) ? tasks : (tasks.items || []);

    if (taskList.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">No tasks found</td></tr>`;
      return;
    }

    tableBody.innerHTML = taskList.map(t => `
      <tr class="hover:bg-surface-variant/20 transition-colors">
        <td class="py-3 px-4">
          <input type="checkbox" data-task-toggle="${t.id}" ${t.status === 'completed' ? 'checked' : ''} class="h-4 w-4 text-primary rounded" />
        </td>
        <td class="py-3 px-4 font-semibold ${t.status === 'completed' ? 'line-through text-outline' : 'text-on-surface'}">
          ${escapeHtml(t.title)}
        </td>
        <td class="py-3 px-4 text-on-surface-variant">${t.due_date ? t.due_date.substring(0, 10) : 'No due date'}</td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase ${getPriorityClass(t.priority)}">
            ${escapeHtml(t.priority || 'medium')}
          </span>
        </td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(t.assignee ? t.assignee.full_name : 'Unassigned')}</td>
        <td class="py-3 px-4 text-right space-x-2">
          ${canCreateOrEdit() ? `<button data-edit-task="${t.id}" class="text-primary hover:text-primary-container p-1"><span class="material-symbols-outlined text-[20px]">edit</span></button>` : ''}
          ${canDelete() ? `<button data-delete-task="${t.id}" class="text-error hover:opacity-80 p-1"><span class="material-symbols-outlined text-[20px]">delete</span></button>` : ''}
        </td>
      </tr>
    `).join('');

    // Bind status check toggle
    tableBody.querySelectorAll('[data-task-toggle]').forEach(chk => {
      chk.addEventListener('change', async () => {
        const id = chk.getAttribute('data-task-toggle');
        const newStatus = chk.checked ? 'completed' : 'pending';
        try {
          await apiPatch(`/tasks/${id}/status`, { status: newStatus });
          await loadTasks();
        } catch (err) {
          alert(`Failed to update task status: ${err.message}`);
          chk.checked = !chk.checked;
        }
      });
    });

    tableBody.querySelectorAll('[data-edit-task]').forEach(btn => {
      btn.addEventListener('click', () => openTaskModal(btn.getAttribute('data-edit-task')));
    });

    tableBody.querySelectorAll('[data-delete-task]').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (confirm('Delete this task?')) {
          await apiDelete(`/tasks/${btn.getAttribute('data-delete-task')}`);
          await loadTasks();
        }
      });
    });

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-error">${err.message || 'Failed to load tasks'}</td></tr>`;
  }
}

function getPriorityClass(priority) {
  switch ((priority || '').toLowerCase()) {
    case 'high': return 'bg-error-container text-on-error-container';
    case 'medium': return 'bg-secondary-container/20 text-secondary';
    case 'low': return 'bg-surface-container-high text-on-surface-variant';
    default: return 'bg-surface-variant text-on-surface-variant';
  }
}

async function loadActivities() {
  const container = document.querySelector('#activities-list') || document.querySelector('[data-section="activities"]');
  if (!container) return;

  container.innerHTML = `<div class="p-4 text-center text-body-sm text-on-surface-variant">Loading activities...</div>`;

  try {
    const activities = await apiGet('/activities', { limit: 20 });
    const list = Array.isArray(activities) ? activities : (activities.items || []);

    if (list.length === 0) {
      container.innerHTML = `<div class="p-4 text-center text-body-sm text-on-surface-variant">No recent activities</div>`;
      return;
    }

    container.innerHTML = `
      <div class="space-y-3">
        ${list.map(a => `
          <div class="p-3 rounded-lg border border-outline-variant/30 bg-surface/80 flex items-start gap-3">
            <span class="material-symbols-outlined text-primary text-[20px]">${getActivityIcon(a.activity_type)}</span>
            <div class="flex-1">
              <div class="font-body-md font-semibold text-on-surface">${escapeHtml(a.subject || a.title)}</div>
              <div class="font-body-sm text-on-surface-variant mt-1">${escapeHtml(a.notes || a.description || '')}</div>
              <div class="font-label-md text-[11px] text-outline mt-1">${a.created_at ? new Date(a.created_at).toLocaleString() : ''}</div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="p-4 text-center text-body-sm text-error">${err.message || 'Failed to load activities'}</div>`;
  }
}

function getActivityIcon(type) {
  switch ((type || '').toLowerCase()) {
    case 'call': return 'call';
    case 'email': return 'mail';
    case 'meeting': return 'groups';
    case 'note': return 'edit_note';
    default: return 'event';
  }
}

function setupTaskModal() {
  let modal = document.getElementById('task-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'task-modal';
    modal.className = 'hidden fixed inset-0 z-50 bg-inverse-surface/50 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML = `
      <div class="bg-surface/95 backdrop-blur-xl border border-outline-variant/50 rounded-xl p-6 w-full max-w-lg shadow-2xl">
        <div class="flex justify-between items-center mb-4">
          <h2 id="task-modal-title" class="font-headline-md text-headline-md font-bold text-on-surface">Add Task</h2>
          <button id="btn-close-task-modal" class="text-outline hover:text-on-surface"><span class="material-symbols-outlined">close</span></button>
        </div>
        <form id="task-form" class="space-y-4">
          <input type="hidden" id="task-id" />
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Task Title *</label>
            <input type="text" id="task-title" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Priority</label>
              <select id="task-priority" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md">
                <option value="high">High</option>
                <option value="medium" selected>Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Due Date</label>
              <input type="date" id="task-due-date" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Description</label>
            <textarea id="task-description" rows="3" class="w-full p-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md"></textarea>
          </div>
          <div class="flex justify-end gap-3 pt-4 border-t border-outline-variant/30">
            <button type="button" id="btn-cancel-task" class="px-4 py-2 border border-outline-variant rounded-lg font-label-md text-on-surface hover:bg-surface-variant/30">Cancel</button>
            <button type="submit" class="px-4 py-2 bg-primary-container text-on-primary rounded-lg font-label-md hover:opacity-90">Save Task</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);
  }

  document.querySelectorAll('button:has(span:contains("Add Task")), [data-action="add-task"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openTaskModal();
    });
  });

  const closeBtn = document.getElementById('btn-close-task-modal');
  const cancelBtn = document.getElementById('btn-cancel-task');
  const form = document.getElementById('task-form');

  if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('task-id').value;
      const data = {
        title: document.getElementById('task-title').value.trim(),
        priority: document.getElementById('task-priority').value,
        due_date: document.getElementById('task-due-date').value || null,
        description: document.getElementById('task-description').value.trim() || null
      };

      try {
        if (id) {
          await apiPut(`/tasks/${id}`, data);
        } else {
          await apiPost('/tasks', data);
        }
        modal.classList.add('hidden');
        await loadTasks();
      } catch (err) {
        alert(`Error saving task: ${err.message}`);
      }
    });
  }
}

async function openTaskModal(taskId = null) {
  const modal = document.getElementById('task-modal');
  const title = document.getElementById('task-modal-title');
  const idInput = document.getElementById('task-id');
  const titleInput = document.getElementById('task-title');
  const priorityInput = document.getElementById('task-priority');
  const dueInput = document.getElementById('task-due-date');
  const descInput = document.getElementById('task-description');

  if (!modal) return;

  if (taskId) {
    title.textContent = 'Edit Task';
    try {
      const task = await apiGet(`/tasks/${taskId}`);
      idInput.value = task.id;
      titleInput.value = task.title || '';
      priorityInput.value = task.priority || 'medium';
      dueInput.value = task.due_date ? task.due_date.substring(0, 10) : '';
      descInput.value = task.description || '';
    } catch (err) {
      alert(`Error loading task: ${err.message}`);
      return;
    }
  } else {
    title.textContent = 'Add Task';
    idInput.value = '';
    titleInput.value = '';
    priorityInput.value = 'medium';
    dueInput.value = '';
    descInput.value = '';
  }

  modal.classList.remove('hidden');
}

function setupActivityModal() {
  document.querySelectorAll('button:has(span:contains("Add Activity")), [data-action="add-activity"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const subject = prompt('Activity Subject:');
      if (!subject) return;
      const type = prompt('Activity Type (call, email, meeting, note):', 'call') || 'note';
      try {
        await apiPost('/activities', { subject, activity_type: type });
        await loadActivities();
      } catch (err) {
        alert(`Failed to log activity: ${err.message}`);
      }
    });
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
