import { apiGet, apiPost, apiPut, apiDelete } from './api.js';
import { initApp } from './app.js';
import { canCreateOrEdit, canDelete } from './rbac.js';

let currentPage = 1;
const pageSize = 10;
let currentSearch = '';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();

  const isDetailPage = window.location.pathname.includes('company_details_crm_pro');
  if (isDetailPage) {
    await initCompanyDetailsPage();
  } else {
    await initCompaniesListPage();
  }
});

async function initCompaniesListPage() {
  const searchInput = document.getElementById('search-companies') || document.querySelector('input[placeholder*="Company"]');
  const createBtn = document.getElementById('btn-create-company') || document.querySelector('button:has(span:contains("Add")), button:has(span:contains("Create"))');
  
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      currentSearch = e.target.value.trim();
      currentPage = 1;
      loadCompanies();
    });
  }

  // Bind Create Company Modal
  setupCompanyModal();
  await loadCompanies();
}

async function loadCompanies() {
  const tableBody = document.querySelector('tbody');
  if (!tableBody) return;

  tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">Loading companies...</td></tr>`;

  try {
    const skip = (currentPage - 1) * pageSize;
    const response = await apiGet('/companies', { search: currentSearch, skip, limit: pageSize });
    
    const companies = Array.isArray(response) ? response : (response.items || []);
    const total = response.total !== undefined ? response.total : companies.length;

    if (companies.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-on-surface-variant">No companies found</td></tr>`;
      return;
    }

    tableBody.innerHTML = companies.map(c => `
      <tr class="hover:bg-surface-variant/20 transition-colors">
        <td class="py-3 px-4 font-semibold text-on-surface">
          <a href="../company_details_crm_pro/code.html?id=${c.id}" class="text-primary hover:underline">${escapeHtml(c.name)}</a>
        </td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.industry || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.website || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.phone || 'N/A')}</td>
        <td class="py-3 px-4 text-on-surface-variant">${escapeHtml(c.city || '')}${c.country ? `, ${c.country}` : ''}</td>
        <td class="py-3 px-4 text-right space-x-2">
          ${canCreateOrEdit() ? `<button data-edit-id="${c.id}" class="btn-edit text-primary hover:text-primary-container p-1" title="Edit"><span class="material-symbols-outlined text-[20px]">edit</span></button>` : ''}
          ${canDelete() ? `<button data-delete-id="${c.id}" class="btn-delete text-error hover:opacity-80 p-1" title="Delete"><span class="material-symbols-outlined text-[20px]">delete</span></button>` : ''}
        </td>
      </tr>
    `).join('');

    // Bind Edit and Delete Buttons
    tableBody.querySelectorAll('[data-edit-id]').forEach(btn => {
      btn.addEventListener('click', () => openCompanyModal(btn.getAttribute('data-edit-id')));
    });

    tableBody.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', () => deleteCompany(btn.getAttribute('data-delete-id')));
    });

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-body-md text-error">${err.message || 'Failed to load companies'}</td></tr>`;
  }
}

async function deleteCompany(id) {
  if (!confirm('Are you sure you want to delete this company?')) return;
  try {
    await apiDelete(`/companies/${id}`);
    await loadCompanies();
  } catch (err) {
    alert(`Failed to delete company: ${err.message}`);
  }
}

function setupCompanyModal() {
  let modal = document.getElementById('company-modal');
  if (!modal) {
    // Dynamically inject create/edit company modal into DOM
    modal = document.createElement('div');
    modal.id = 'company-modal';
    modal.className = 'hidden fixed inset-0 z-50 bg-inverse-surface/50 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML = `
      <div class="bg-surface/95 backdrop-blur-xl border border-outline-variant/50 rounded-xl p-6 w-full max-w-lg shadow-2xl">
        <div class="flex justify-between items-center mb-4">
          <h2 id="company-modal-title" class="font-headline-md text-headline-md font-bold text-on-surface">Add Company</h2>
          <button id="btn-close-company-modal" class="text-outline hover:text-on-surface"><span class="material-symbols-outlined">close</span></button>
        </div>
        <form id="company-form" class="space-y-4">
          <input type="hidden" id="company-id" />
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Company Name *</label>
            <input type="text" id="company-name" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Industry</label>
              <input type="text" id="company-industry" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Website</label>
              <input type="text" id="company-website" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Phone</label>
              <input type="text" id="company-phone" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">City</label>
              <input type="text" id="company-city" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Country</label>
            <input type="text" id="company-country" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div class="flex justify-end gap-3 pt-4 border-t border-outline-variant/30">
            <button type="button" id="btn-cancel-company" class="px-4 py-2 border border-outline-variant rounded-lg font-label-md text-on-surface hover:bg-surface-variant/30">Cancel</button>
            <button type="submit" class="px-4 py-2 bg-primary-container text-on-primary rounded-lg font-label-md hover:opacity-90">Save Company</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // Bind Open Trigger buttons in header/page
  document.querySelectorAll('button:has(span:contains("Add")), button:has(span:contains("Create")), [data-action="add-company"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openCompanyModal();
    });
  });

  const closeBtn = document.getElementById('btn-close-company-modal');
  const cancelBtn = document.getElementById('btn-cancel-company');
  const form = document.getElementById('company-form');

  if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('company-id').value;
      const data = {
        name: document.getElementById('company-name').value.trim(),
        industry: document.getElementById('company-industry').value.trim() || null,
        website: document.getElementById('company-website').value.trim() || null,
        phone: document.getElementById('company-phone').value.trim() || null,
        city: document.getElementById('company-city').value.trim() || null,
        country: document.getElementById('company-country').value.trim() || null
      };

      try {
        if (id) {
          await apiPut(`/companies/${id}`, data);
        } else {
          await apiPost('/companies', data);
        }
        modal.classList.add('hidden');
        await loadCompanies();
      } catch (err) {
        alert(`Error saving company: ${err.message}`);
      }
    });
  }
}

async function openCompanyModal(companyId = null) {
  const modal = document.getElementById('company-modal');
  const title = document.getElementById('company-modal-title');
  const idInput = document.getElementById('company-id');
  const nameInput = document.getElementById('company-name');
  const industryInput = document.getElementById('company-industry');
  const websiteInput = document.getElementById('company-website');
  const phoneInput = document.getElementById('company-phone');
  const cityInput = document.getElementById('company-city');
  const countryInput = document.getElementById('company-country');

  if (!modal) return;

  if (companyId) {
    title.textContent = 'Edit Company';
    try {
      const company = await apiGet(`/companies/${companyId}`);
      idInput.value = company.id;
      nameInput.value = company.name || '';
      industryInput.value = company.industry || '';
      websiteInput.value = company.website || '';
      phoneInput.value = company.phone || '';
      cityInput.value = company.city || '';
      countryInput.value = company.country || '';
    } catch (err) {
      alert(`Error fetching company details: ${err.message}`);
      return;
    }
  } else {
    title.textContent = 'Add Company';
    idInput.value = '';
    nameInput.value = '';
    industryInput.value = '';
    websiteInput.value = '';
    phoneInput.value = '';
    cityInput.value = '';
    countryInput.value = '';
  }

  modal.classList.remove('hidden');
}

async function initCompanyDetailsPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const companyId = urlParams.get('id');

  if (!companyId) {
    alert('No company ID specified');
    return;
  }

  try {
    const company = await apiGet(`/companies/${companyId}`);
    
    // Populate details screen titles and fields
    const titleEl = document.querySelector('h1, h2');
    if (titleEl) titleEl.textContent = company.name;

    const nameEl = document.querySelector('[data-field="name"]');
    if (nameEl) nameEl.textContent = company.name;

    const industryEl = document.querySelector('[data-field="industry"]');
    if (industryEl) industryEl.textContent = company.industry || 'N/A';

    const websiteEl = document.querySelector('[data-field="website"]');
    if (websiteEl) websiteEl.textContent = company.website || 'N/A';

    const phoneEl = document.querySelector('[data-field="phone"]');
    if (phoneEl) phoneEl.textContent = company.phone || 'N/A';

    setupCompanyModal();
    const editBtn = document.querySelector('.btn-edit, [data-action="edit"]');
    if (editBtn) {
      editBtn.addEventListener('click', () => openCompanyModal(companyId));
    }

  } catch (err) {
    alert(`Failed to load company details: ${err.message}`);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
