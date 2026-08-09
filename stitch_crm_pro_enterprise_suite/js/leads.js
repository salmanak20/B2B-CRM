import { apiGet, apiPost, apiPut, apiDelete } from './api.js';
import { initApp } from './app.js';
import { canCreateOrEdit, canDelete } from './rbac.js';

let currentPage = 1;
const pageSize = 10;
let currentSearch = '';
let currentStatus = '';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();

  const isDetailPage = window.location.pathname.includes('lead_details_crm_pro');
  if (isDetailPage) {
    await initLeadDetailsPage();
  } else {
    await initLeadsListPage();
  }
});

async function initLeadsListPage() {
  const searchInput = document.getElementById('search-leads') || document.querySelector('input[placeholder*="Lead"]');
  const statusSelect = document.getElementById('filter-status');

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      currentSearch = e.target.value.trim();
      currentPage = 1;
      loadLeads();
    });
  }

  if (statusSelect) {
    statusSelect.addEventListener('change', (e) => {
      currentStatus = e.target.value;
      currentPage = 1;
      loadLeads();
    });
  }

  setupLeadModal();
  await loadLeads();
}

async function loadLeads() {
  const tableBody = document.querySelector('tbody');
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-body-md text-on-surface-variant">Loading leads...</td></tr>`;

  try {
    const skip = (currentPage - 1) * pageSize;
    const response = await apiGet('/leads', { search: currentSearch, status: currentStatus, skip, limit: pageSize });

    const leads = Array.isArray(response) ? response : (response.items || []);

    if (leads.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-body-md text-on-surface-variant">No leads found</td></tr>`;
      return;
    }

    tableBody.innerHTML = leads.map(l => `
      <tr class="hover:bg-surface-variant/20 transition-colors">
        <td class="py-3 px-4 font-semibold text-on-surface">
          <a href="../lead_details_crm_pro/code.html?id=${l.id}" class="text-primary hover:underline">${escapeHtml(l.title)}</a>
        </td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(l.contact_name || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(l.company_name || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(l.source || 'N/A')}</td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusBadgeClass(l.status)}">
            ${escapeHtml(l.status)}
          </span>
        </td>
        <td class="py-3 px-4 font-semibold text-primary">$${Number(l.estimated_value || 0).toLocaleString()}</td>
        <td class="py-3 px-4 text-right space-x-2">
          ${canCreateOrEdit() ? `<button data-edit-id="${l.id}" class="btn-edit text-primary hover:text-primary-container p-1" title="Edit"><span class="material-symbols-outlined text-[20px]">edit</span></button>` : ''}
          ${canDelete() ? `<button data-delete-id="${l.id}" class="btn-delete text-error hover:opacity-80 p-1" title="Delete"><span class="material-symbols-outlined text-[20px]">delete</span></button>` : ''}
        </td>
      </tr>
    `).join('');

    tableBody.querySelectorAll('[data-edit-id]').forEach(btn => {
      btn.addEventListener('click', () => openLeadModal(btn.getAttribute('data-edit-id')));
    });

    tableBody.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () => deleteLead(btn.getAttribute('data-delete-id')));
    });

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-body-md text-error">${err.message || 'Failed to load leads'}</td></tr>`;
  }
}

function getStatusBadgeClass(status) {
  switch ((status || '').toLowerCase()) {
    case 'new': return 'bg-secondary-container/20 text-secondary';
    case 'contacted': return 'bg-primary-container/20 text-primary';
    case 'qualified': return 'bg-tertiary-container/20 text-tertiary';
    case 'unqualified': return 'bg-error-container text-on-error-container';
    case 'converted': return 'bg-surface-container-highest text-on-surface';
    default: return 'bg-surface-variant text-on-surface-variant';
  }
}

async function deleteLead(id) {
  if (!confirm('Are you sure you want to delete this lead?')) return;
  try {
    await apiDelete(`/leads/${id}`);
    await loadLeads();
  } catch (err) {
    alert(`Failed to delete lead: ${err.message}`);
  }
}

function setupLeadModal() {
  let modal = document.getElementById('lead-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'lead-modal';
    modal.className = 'hidden fixed inset-0 z-50 bg-inverse-surface/50 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML = `
      <div class="bg-surface/95 backdrop-blur-xl border border-outline-variant/50 rounded-xl p-6 w-full max-w-lg shadow-2xl">
        <div class="flex justify-between items-center mb-4">
          <h2 id="lead-modal-title" class="font-headline-md text-headline-md font-bold text-on-surface">Add Lead</h2>
          <button id="btn-close-lead-modal" class="text-outline hover:text-on-surface"><span class="material-symbols-outlined">close</span></button>
        </div>
        <form id="lead-form" class="space-y-4">
          <input type="hidden" id="lead-id" />
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Lead Title *</label>
            <input type="text" id="lead-title" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Contact Name</label>
              <input type="text" id="lead-contact-name" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Company Name</label>
              <input type="text" id="lead-company-name" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Status</label>
              <select id="lead-status" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md">
                <option value="new">New</option>
                <option value="contacted">Contacted</option>
                <option value="qualified">Qualified</option>
                <option value="unqualified">Unqualified</option>
                <option value="converted">Converted</option>
              </select>
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Source</label>
              <input type="text" id="lead-source" placeholder="Website, Referral, etc." class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Estimated Value ($)</label>
            <input type="number" step="0.01" id="lead-value" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div class="flex justify-end gap-3 pt-4 border-t border-outline-variant/30">
            <button type="button" id="btn-cancel-lead" class="px-4 py-2 border border-outline-variant rounded-lg font-label-md text-on-surface hover:bg-surface-variant/30">Cancel</button>
            <button type="submit" class="px-4 py-2 bg-primary-container text-on-primary rounded-lg font-label-md hover:opacity-90">Save Lead</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);
  }

  document.querySelectorAll('button:has(span:contains("Add")), button:has(span:contains("Create")), [data-action="add-lead"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openLeadModal();
    });
  });

  const closeBtn = document.getElementById('btn-close-lead-modal');
  const cancelBtn = document.getElementById('btn-cancel-lead');
  const form = document.getElementById('lead-form');

  if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('lead-id').value;
      const val = document.getElementById('lead-value').value;
      const data = {
        title: document.getElementById('lead-title').value.trim(),
        contact_name: document.getElementById('lead-contact-name').value.trim() || null,
        company_name: document.getElementById('lead-company-name').value.trim() || null,
        status: document.getElementById('lead-status').value,
        source: document.getElementById('lead-source').value.trim() || null,
        estimated_value: val ? parseFloat(val) : 0
      };

      try {
        if (id) {
          await apiPut(`/leads/${id}`, data);
        } else {
          await apiPost('/leads', data);
        }
        modal.classList.add('hidden');
        await loadLeads();
      } catch (err) {
        alert(`Error saving lead: ${err.message}`);
      }
    });
  }
}

async function openLeadModal(leadId = null) {
  const modal = document.getElementById('lead-modal');
  const title = document.getElementById('lead-modal-title');
  const idInput = document.getElementById('lead-id');
  const titleInput = document.getElementById('lead-title');
  const contactNameInput = document.getElementById('lead-contact-name');
  const companyNameInput = document.getElementById('lead-company-name');
  const statusInput = document.getElementById('lead-status');
  const sourceInput = document.getElementById('lead-source');
  const valueInput = document.getElementById('lead-value');

  if (!modal) return;

  if (leadId) {
    title.textContent = 'Edit Lead';
    try {
      const lead = await apiGet(`/leads/${leadId}`);
      idInput.value = lead.id;
      titleInput.value = lead.title || '';
      contactNameInput.value = lead.contact_name || '';
      companyNameInput.value = lead.company_name || '';
      statusInput.value = lead.status || 'new';
      sourceInput.value = lead.source || '';
      valueInput.value = lead.estimated_value || 0;
    } catch (err) {
      alert(`Error fetching lead details: ${err.message}`);
      return;
    }
  } else {
    title.textContent = 'Add Lead';
    idInput.value = '';
    titleInput.value = '';
    contactNameInput.value = '';
    companyNameInput.value = '';
    statusInput.value = 'new';
    sourceInput.value = '';
    valueInput.value = '';
  }

  modal.classList.remove('hidden');
}

async function initLeadDetailsPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const leadId = urlParams.get('id');

  if (!leadId) {
    alert('No lead ID specified');
    return;
  }

  try {
    const lead = await apiGet(`/leads/${leadId}`);
    
    const titleEl = document.querySelector('h1, h2');
    if (titleEl) titleEl.textContent = lead.title;

    setupLeadModal();
    const editBtn = document.querySelector('.btn-edit, [data-action="edit"]');
    if (editBtn) {
      editBtn.addEventListener('click', () => openLeadModal(leadId));
    }
  } catch (err) {
    alert(`Failed to load lead details: ${err.message}`);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
