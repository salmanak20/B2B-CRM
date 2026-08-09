import { apiGet, apiPost, apiPut, apiDelete } from './api.js';
import { initApp } from './app.js';
import { canCreateOrEdit, canDelete } from './rbac.js';

let currentPage = 1;
const pageSize = 10;
let currentSearch = '';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();
  setupContactModal();
  await loadContacts();
});

async function loadContacts() {
  const tableBody = document.querySelector('tbody');
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">Loading contacts...</td></tr>`;

  try {
    const skip = (currentPage - 1) * pageSize;
    const response = await apiGet('/contacts', { search: currentSearch, skip, limit: pageSize });

    const contacts = Array.isArray(response) ? response : (response.items || []);

    if (contacts.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">No contacts found</td></tr>`;
      return;
    }

    tableBody.innerHTML = contacts.map(c => `
      <tr class="hover:bg-surface-variant/20 transition-colors">
        <td class="py-3 px-4 font-semibold text-on-surface">
          ${escapeHtml(c.first_name)} ${escapeHtml(c.last_name)}
        </td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.email || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.phone || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.job_title || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant font-semibold text-primary">
          ${c.company ? escapeHtml(c.company.name) : 'N/A'}
        </td>
        <td class="py-3 px-4 text-right space-x-2">
          ${canCreateOrEdit() ? `<button data-edit-id="${c.id}" class="btn-edit text-primary hover:text-primary-container p-1" title="Edit"><span class="material-symbols-outlined text-[20px]">edit</span></button>` : ''}
          ${canDelete() ? `<button data-delete-id="${c.id}" class="btn-delete text-error hover:opacity-80 p-1" title="Delete"><span class="material-symbols-outlined text-[20px]">delete</span></button>` : ''}
        </td>
      </tr>
    `).join('');

    tableBody.querySelectorAll('[data-edit-id]').forEach(btn => {
      btn.addEventListener('click', () => openContactModal(btn.getAttribute('data-edit-id')));
    });

    tableBody.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () => deleteContact(btn.getAttribute('data-delete-id')));
    });

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-error">${err.message || 'Failed to load contacts'}</td></tr>`;
  }
}

async function deleteContact(id) {
  if (!confirm('Are you sure you want to delete this contact?')) return;
  try {
    await apiDelete(`/contacts/${id}`);
    await loadContacts();
  } catch (err) {
    alert(`Failed to delete contact: ${err.message}`);
  }
}

function setupContactModal() {
  let modal = document.getElementById('contact-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'contact-modal';
    modal.className = 'hidden fixed inset-0 z-50 bg-inverse-surface/50 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML = `
      <div class="bg-surface/95 backdrop-blur-xl border border-outline-variant/50 rounded-xl p-6 w-full max-w-lg shadow-2xl">
        <div class="flex justify-between items-center mb-4">
          <h2 id="contact-modal-title" class="font-headline-md text-headline-md font-bold text-on-surface">Add Contact</h2>
          <button id="btn-close-contact-modal" class="text-outline hover:text-on-surface"><span class="material-symbols-outlined">close</span></button>
        </div>
        <form id="contact-form" class="space-y-4">
          <input type="hidden" id="contact-id" />
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">First Name *</label>
              <input type="text" id="contact-first-name" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Last Name *</label>
              <input type="text" id="contact-last-name" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Email *</label>
              <input type="email" id="contact-email" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Phone</label>
              <input type="text" id="contact-phone" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Job Title</label>
            <input type="text" id="contact-job-title" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Company</label>
            <select id="contact-company-id" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md">
              <option value="">Select Company...</option>
            </select>
          </div>
          <div class="flex justify-end gap-3 pt-4 border-t border-outline-variant/30">
            <button type="button" id="btn-cancel-contact" class="px-4 py-2 border border-outline-variant rounded-lg font-label-md text-on-surface hover:bg-surface-variant/30">Cancel</button>
            <button type="submit" class="px-4 py-2 bg-primary-container text-on-primary rounded-lg font-label-md hover:opacity-90">Save Contact</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);
  }

  document.querySelectorAll('button:has(span:contains("Add")), button:has(span:contains("Create")), [data-action="add-contact"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openContactModal();
    });
  });

  const closeBtn = document.getElementById('btn-close-contact-modal');
  const cancelBtn = document.getElementById('btn-cancel-contact');
  const form = document.getElementById('contact-form');

  if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('contact-id').value;
      const companyVal = document.getElementById('contact-company-id').value;
      const data = {
        first_name: document.getElementById('contact-first-name').value.trim(),
        last_name: document.getElementById('contact-last-name').value.trim(),
        email: document.getElementById('contact-email').value.trim(),
        phone: document.getElementById('contact-phone').value.trim() || null,
        job_title: document.getElementById('contact-job-title').value.trim() || null,
        company_id: companyVal ? parseInt(companyVal, 10) : null
      };

      try {
        if (id) {
          await apiPut(`/contacts/${id}`, data);
        } else {
          await apiPost('/contacts', data);
        }
        modal.classList.add('hidden');
        await loadContacts();
      } catch (err) {
        alert(`Error saving contact: ${err.message}`);
      }
    });
  }
}

async function openContactModal(contactId = null) {
  const modal = document.getElementById('contact-modal');
  const title = document.getElementById('contact-modal-title');
  const idInput = document.getElementById('contact-id');
  const firstNameInput = document.getElementById('contact-first-name');
  const lastNameInput = document.getElementById('contact-last-name');
  const emailInput = document.getElementById('contact-email');
  const phoneInput = document.getElementById('contact-phone');
  const jobTitleInput = document.getElementById('contact-job-title');
  const companySelect = document.getElementById('contact-company-id');

  if (!modal) return;

  // Populate Companies dropdown
  try {
    const companies = await apiGet('/companies', { limit: 100 });
    const compList = Array.isArray(companies) ? companies : (companies.items || []);
    companySelect.innerHTML = '<option value="">Select Company...</option>' + 
      compList.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
  } catch (e) {}

  if (contactId) {
    title.textContent = 'Edit Contact';
    try {
      const contact = await apiGet(`/contacts/${contactId}`);
      idInput.value = contact.id;
      firstNameInput.value = contact.first_name || '';
      lastNameInput.value = contact.last_name || '';
      emailInput.value = contact.email || '';
      phoneInput.value = contact.phone || '';
      jobTitleInput.value = contact.job_title || '';
      companySelect.value = contact.company_id || '';
    } catch (err) {
      alert(`Error fetching contact details: ${err.message}`);
      return;
    }
  } else {
    title.textContent = 'Add Contact';
    idInput.value = '';
    firstNameInput.value = '';
    lastNameInput.value = '';
    emailInput.value = '';
    phoneInput.value = '';
    jobTitleInput.value = '';
    companySelect.value = '';
  }

  modal.classList.remove('hidden');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
