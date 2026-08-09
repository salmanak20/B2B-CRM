import { apiGet } from './api.js';

let searchTimeout = null;

export function initGlobalSearch() {
  const searchInputs = document.querySelectorAll('input[placeholder*="Search"], input[type="search"]');
  if (!searchInputs || searchInputs.length === 0) return;

  searchInputs.forEach(input => {
    // Avoid double binding
    if (input.dataset.searchBound) return;
    input.dataset.searchBound = "true";

    // Wrap input container for dropdown if needed
    const parent = input.parentElement;
    if (!parent) return;

    // Create dropdown element
    const dropdown = document.createElement('div');
    dropdown.className = 'global-search-dropdown hidden absolute top-full left-0 right-0 mt-2 bg-surface/95 backdrop-blur-xl border border-outline-variant/50 rounded-xl shadow-2xl z-50 max-h-[480px] overflow-y-auto p-4 space-y-4';
    parent.style.position = 'relative';
    parent.appendChild(dropdown);

    input.addEventListener('input', (e) => {
      const query = e.target.value.trim();
      if (searchTimeout) clearTimeout(searchTimeout);

      if (query.length < 2) {
        dropdown.innerHTML = '';
        dropdown.classList.add('hidden');
        return;
      }

      searchTimeout = setTimeout(async () => {
        try {
          dropdown.innerHTML = '<div class="p-3 text-body-sm text-on-surface-variant text-center">Searching...</div>';
          dropdown.classList.remove('hidden');

          const results = await apiGet('/search', { q: query });
          renderSearchResults(results, dropdown);
        } catch (err) {
          dropdown.innerHTML = `<div class="p-3 text-body-sm text-error text-center">${err.message || 'Search failed'}</div>`;
        }
      }, 300);
    });

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
      if (!parent.contains(e.target)) {
        dropdown.classList.add('hidden');
      }
    });
  });
}

function getRelativeUrl(path) {
  const currentPath = window.location.pathname;
  if (currentPath.includes('/stitch_crm_pro_enterprise_suite/')) {
    return `../${path}`;
  }
  return `../${path}`;
}

function renderSearchResults(data, container) {
  const hasCompanies = data.companies && data.companies.length > 0;
  const hasContacts = data.contacts && data.contacts.length > 0;
  const hasLeads = data.leads && data.leads.length > 0;
  const hasDeals = data.deals && data.deals.length > 0;
  const hasTasks = data.tasks && data.tasks.length > 0;

  if (!hasCompanies && !hasContacts && !hasLeads && !hasDeals && !hasTasks) {
    container.innerHTML = '<div class="p-3 text-body-sm text-on-surface-variant text-center">No results found</div>';
    return;
  }

  let html = '';

  if (hasCompanies) {
    html += `
      <div>
        <div class="font-label-md text-label-md text-outline uppercase tracking-wider mb-2">Companies (${data.companies.length})</div>
        <div class="space-y-1">
          ${data.companies.map(c => `
            <a href="${getRelativeUrl('company_details_crm_pro/code.html')}?id=${c.id}" class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-variant/40 transition-colors">
              <span class="material-symbols-outlined text-primary text-[20px]">corporate_fare</span>
              <div>
                <div class="font-body-md text-body-md font-semibold text-on-surface">${escapeHtml(c.name)}</div>
                <div class="font-body-sm text-body-sm text-on-surface-variant">${escapeHtml(c.industry || 'N/A')}</div>
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
  }

  if (hasContacts) {
    html += `
      <div>
        <div class="font-label-md text-label-md text-outline uppercase tracking-wider mb-2">Contacts (${data.contacts.length})</div>
        <div class="space-y-1">
          ${data.contacts.map(c => `
            <a href="${getRelativeUrl('contacts_crm_pro/code.html')}?id=${c.id}" class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-variant/40 transition-colors">
              <span class="material-symbols-outlined text-secondary text-[20px]">person</span>
              <div>
                <div class="font-body-md text-body-md font-semibold text-on-surface">${escapeHtml(c.first_name)} ${escapeHtml(c.last_name)}</div>
                <div class="font-body-sm text-body-sm text-on-surface-variant">${escapeHtml(c.email || '')}</div>
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
  }

  if (hasLeads) {
    html += `
      <div>
        <div class="font-label-md text-label-md text-outline uppercase tracking-wider mb-2">Leads (${data.leads.length})</div>
        <div class="space-y-1">
          ${data.leads.map(l => `
            <a href="${getRelativeUrl('lead_details_crm_pro/code.html')}?id=${l.id}" class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-variant/40 transition-colors">
              <span class="material-symbols-outlined text-tertiary text-[20px]">filter_alt</span>
              <div>
                <div class="font-body-md text-body-md font-semibold text-on-surface">${escapeHtml(l.title)}</div>
                <div class="font-body-sm text-body-sm text-on-surface-variant">${escapeHtml(l.company_name || l.status)}</div>
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
  }

  if (hasDeals) {
    html += `
      <div>
        <div class="font-label-md text-label-md text-outline uppercase tracking-wider mb-2">Deals (${data.deals.length})</div>
        <div class="space-y-1">
          ${data.deals.map(d => `
            <a href="${getRelativeUrl('deal_details_crm_pro/code.html')}?id=${d.id}" class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-variant/40 transition-colors">
              <span class="material-symbols-outlined text-primary-container text-[20px]">monetization_on</span>
              <div>
                <div class="font-body-md text-body-md font-semibold text-on-surface">${escapeHtml(d.title)}</div>
                <div class="font-body-sm text-body-sm text-on-surface-variant">$${Number(d.value || 0).toLocaleString()}</div>
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
  }

  if (hasTasks) {
    html += `
      <div>
        <div class="font-label-md text-label-md text-outline uppercase tracking-wider mb-2">Tasks (${data.tasks.length})</div>
        <div class="space-y-1">
          ${data.tasks.map(t => `
            <a href="${getRelativeUrl('tasks_activities_crm_pro/code.html')}?id=${t.id}" class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-variant/40 transition-colors">
              <span class="material-symbols-outlined text-outline text-[20px]">check_box</span>
              <div>
                <div class="font-body-md text-body-md font-semibold text-on-surface">${escapeHtml(t.title)}</div>
                <div class="font-body-sm text-body-sm text-on-surface-variant">Due: ${t.due_date ? t.due_date.substring(0, 10) : 'N/A'}</div>
              </div>
            </a>
          `).join('')}
        </div>
      </div>
    `;
  }

  container.innerHTML = html;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
