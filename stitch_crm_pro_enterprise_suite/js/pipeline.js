import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from './api.js';
import { initApp } from './app.js';
import { canCreateOrEdit, canDelete } from './rbac.js';

let activePipelineId = null;

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();

  const isDealDetailPage = window.location.pathname.includes('deal_details_crm_pro');
  if (isDealDetailPage) {
    await initDealDetailsPage();
  } else {
    await initPipelineKanbanPage();
  }
});

async function initPipelineKanbanPage() {
  setupDealModal();

  try {
    const pipelines = await apiGet('/pipelines');
    const pipelineList = Array.isArray(pipelines) ? pipelines : (pipelines.items || []);

    if (pipelineList.length > 0) {
      activePipelineId = pipelineList[0].id;
      renderPipelineSelector(pipelineList);
      await loadKanbanBoard(activePipelineId);
    }
  } catch (err) {
    console.error('Failed to load pipelines:', err);
  }
}

function renderPipelineSelector(pipelines) {
  const container = document.querySelector('[data-pipeline-selector]') || document.querySelector('select');
  if (!container) return;

  if (container.tagName === 'SELECT') {
    container.innerHTML = pipelines.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
    container.addEventListener('change', async (e) => {
      activePipelineId = parseInt(e.target.value, 10);
      await loadKanbanBoard(activePipelineId);
    });
  }
}

async function loadKanbanBoard(pipelineId) {
  const boardContainer = document.querySelector('[data-kanban-board]') || document.querySelector('.grid');
  if (!boardContainer) return;

  try {
    const board = await apiGet(`/pipelines/${pipelineId}/board`);
    const stages = board.stages || [];

    boardContainer.innerHTML = stages.map(stage => `
      <div class="flex flex-col bg-surface-container-low/60 backdrop-blur-md rounded-xl p-4 border border-outline-variant/30 min-w-[280px]" data-stage-id="${stage.id}">
        <div class="flex items-center justify-between pb-3 border-b border-outline-variant/30 mb-3">
          <div class="flex items-center gap-2">
            <span class="font-headline-md text-body-md font-bold text-on-surface">${escapeHtml(stage.name)}</span>
            <span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-surface-container-high text-on-surface-variant">${stage.deals ? stage.deals.length : 0}</span>
          </div>
          <span class="font-label-md text-xs font-bold text-primary">$${Number(stage.total_value || 0).toLocaleString()}</span>
        </div>

        <!-- Cards Container -->
        <div class="kanban-cards-dropzone space-y-3 flex-1 overflow-y-auto min-h-[300px]" data-stage-id="${stage.id}">
          ${(stage.deals || []).map(deal => `
            <div class="kanban-card p-4 rounded-lg bg-surface/90 border border-outline-variant/30 shadow-sm hover:shadow-md cursor-grab transition-all" 
                 draggable="true" 
                 data-deal-id="${deal.id}">
              <div class="flex justify-between items-start mb-2">
                <a href="../deal_details_crm_pro/code.html?id=${deal.id}" class="font-body-md font-semibold text-on-surface hover:text-primary transition-colors">${escapeHtml(deal.title)}</a>
                ${canCreateOrEdit() ? `
                  <button data-edit-deal="${deal.id}" class="text-outline hover:text-on-surface p-1">
                    <span class="material-symbols-outlined text-[16px]">edit</span>
                  </button>
                ` : ''}
              </div>
              <div class="font-headline-md text-headline-md font-bold text-primary mb-2">$${Number(deal.value || 0).toLocaleString()}</div>
              <div class="flex items-center justify-between text-body-sm text-on-surface-variant pt-2 border-t border-outline-variant/20">
                <span class="flex items-center gap-1"><span class="material-symbols-outlined text-[16px]">corporate_fare</span> ${escapeHtml(deal.company ? deal.company.name : 'N/A')}</span>
                <span class="font-label-md text-[11px] text-outline">${deal.expected_close_date ? deal.expected_close_date.substring(0, 10) : ''}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');

    // Bind Edit deal buttons
    boardContainer.querySelectorAll('[data-edit-deal]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openDealModal(btn.getAttribute('data-edit-deal'));
      });
    });

    // Attach Drag and Drop handlers
    setupDragAndDrop(boardContainer);

  } catch (err) {
    boardContainer.innerHTML = `<div class="p-8 text-center text-error font-body-md">${err.message || 'Failed to load Kanban board'}</div>`;
  }
}

function setupDragAndDrop(boardContainer) {
  let draggedDealId = null;

  boardContainer.querySelectorAll('.kanban-card').forEach(card => {
    card.addEventListener('dragstart', (e) => {
      draggedDealId = card.getAttribute('data-deal-id');
      e.dataTransfer.setData('text/plain', draggedDealId);
      card.classList.add('opacity-50');
    });

    card.addEventListener('dragend', () => {
      card.classList.remove('opacity-50');
    });
  });

  boardContainer.querySelectorAll('.kanban-cards-dropzone').forEach(zone => {
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('bg-primary-container/10');
    });

    zone.addEventListener('dragleave', () => {
      zone.classList.remove('bg-primary-container/10');
    });

    zone.addEventListener('drop', async (e) => {
      e.preventDefault();
      zone.classList.remove('bg-primary-container/10');
      
      const newStageId = parseInt(zone.getAttribute('data-stage-id'), 10);
      const dealId = e.dataTransfer.getData('text/plain') || draggedDealId;

      if (dealId && newStageId) {
        try {
          await apiPatch(`/deals/${dealId}/stage`, { stage_id: newStageId });
          await loadKanbanBoard(activePipelineId);
        } catch (err) {
          alert(`Failed to move deal: ${err.message}`);
        }
      }
    });
  });
}

function setupDealModal() {
  let modal = document.getElementById('deal-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'deal-modal';
    modal.className = 'hidden fixed inset-0 z-50 bg-inverse-surface/50 backdrop-blur-sm flex items-center justify-center p-4';
    modal.innerHTML = `
      <div class="bg-surface/95 backdrop-blur-xl border border-outline-variant/50 rounded-xl p-6 w-full max-w-lg shadow-2xl">
        <div class="flex justify-between items-center mb-4">
          <h2 id="deal-modal-title" class="font-headline-md text-headline-md font-bold text-on-surface">Add Deal</h2>
          <button id="btn-close-deal-modal" class="text-outline hover:text-on-surface"><span class="material-symbols-outlined">close</span></button>
        </div>
        <form id="deal-form" class="space-y-4">
          <input type="hidden" id="deal-id" />
          <div>
            <label class="block font-label-md text-label-md text-on-surface mb-1">Deal Title *</label>
            <input type="text" id="deal-title" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Deal Value ($) *</label>
              <input type="number" step="0.01" id="deal-value" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Expected Close Date</label>
              <input type="date" id="deal-close-date" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Company</label>
              <select id="deal-company-id" class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md">
                <option value="">Select Company...</option>
              </select>
            </div>
            <div>
              <label class="block font-label-md text-label-md text-on-surface mb-1">Pipeline Stage</label>
              <select id="deal-stage-id" required class="w-full h-10 px-3 border border-outline-variant rounded-md bg-surface-bright text-on-surface font-body-md">
                <option value="">Select Stage...</option>
              </select>
            </div>
          </div>
          <div class="flex justify-end gap-3 pt-4 border-t border-outline-variant/30">
            <button type="button" id="btn-cancel-deal" class="px-4 py-2 border border-outline-variant rounded-lg font-label-md text-on-surface hover:bg-surface-variant/30">Cancel</button>
            <button type="submit" class="px-4 py-2 bg-primary-container text-on-primary rounded-lg font-label-md hover:opacity-90">Save Deal</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(modal);
  }

  document.querySelectorAll('button:has(span:contains("Add")), button:has(span:contains("Create")), [data-action="add-deal"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openDealModal();
    });
  });

  const closeBtn = document.getElementById('btn-close-deal-modal');
  const cancelBtn = document.getElementById('btn-cancel-deal');
  const form = document.getElementById('deal-form');

  if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('deal-id').value;
      const compVal = document.getElementById('deal-company-id').value;
      const stageVal = document.getElementById('deal-stage-id').value;

      const data = {
        title: document.getElementById('deal-title').value.trim(),
        value: parseFloat(document.getElementById('deal-value').value),
        expected_close_date: document.getElementById('deal-close-date').value || null,
        company_id: compVal ? parseInt(compVal, 10) : null,
        pipeline_stage_id: parseInt(stageVal, 10),
        pipeline_id: activePipelineId
      };

      try {
        if (id) {
          await apiPut(`/deals/${id}`, data);
        } else {
          await apiPost('/deals', data);
        }
        modal.classList.add('hidden');
        if (activePipelineId) await loadKanbanBoard(activePipelineId);
      } catch (err) {
        alert(`Error saving deal: ${err.message}`);
      }
    });
  }
}

async function openDealModal(dealId = null) {
  const modal = document.getElementById('deal-modal');
  const title = document.getElementById('deal-modal-title');
  const idInput = document.getElementById('deal-id');
  const titleInput = document.getElementById('deal-title');
  const valueInput = document.getElementById('deal-value');
  const dateInput = document.getElementById('deal-close-date');
  const companySelect = document.getElementById('deal-company-id');
  const stageSelect = document.getElementById('deal-stage-id');

  if (!modal) return;

  // Populate options
  try {
    const companies = await apiGet('/companies', { limit: 100 });
    const compList = Array.isArray(companies) ? companies : (companies.items || []);
    companySelect.innerHTML = '<option value="">Select Company...</option>' + compList.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');

    if (activePipelineId) {
      const board = await apiGet(`/pipelines/${activePipelineId}/board`);
      const stages = board.stages || [];
      stageSelect.innerHTML = '<option value="">Select Stage...</option>' + stages.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
    }
  } catch (e) {}

  if (dealId) {
    title.textContent = 'Edit Deal';
    try {
      const deal = await apiGet(`/deals/${dealId}`);
      idInput.value = deal.id;
      titleInput.value = deal.title || '';
      valueInput.value = deal.value || 0;
      dateInput.value = deal.expected_close_date ? deal.expected_close_date.substring(0, 10) : '';
      companySelect.value = deal.company_id || '';
      stageSelect.value = deal.pipeline_stage_id || '';
    } catch (err) {
      alert(`Error fetching deal details: ${err.message}`);
      return;
    }
  } else {
    title.textContent = 'Add Deal';
    idInput.value = '';
    titleInput.value = '';
    valueInput.value = '';
    dateInput.value = '';
    companySelect.value = '';
    stageSelect.value = '';
  }

  modal.classList.remove('hidden');
}

async function initDealDetailsPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const dealId = urlParams.get('id');

  if (!dealId) {
    alert('No deal ID specified');
    return;
  }

  try {
    const [deal, timeline] = await Promise.all([
      apiGet(`/deals/${dealId}`),
      apiGet(`/deals/${dealId}/timeline`)
    ]);

    const titleEl = document.querySelector('h1, h2');
    if (titleEl) titleEl.textContent = deal.title;

    renderDealTimeline(timeline);
    setupDealModal();

    const editBtn = document.querySelector('.btn-edit, [data-action="edit"]');
    if (editBtn) {
      editBtn.addEventListener('click', () => openDealModal(dealId));
    }
  } catch (err) {
    alert(`Failed to load deal details: ${err.message}`);
  }
}

function renderDealTimeline(timeline) {
  const container = document.querySelector('[data-section="timeline"]');
  if (!container) return;

  const events = Array.isArray(timeline) ? timeline : (timeline.events || []);
  container.innerHTML = `
    <div class="space-y-4 relative before:absolute before:inset-0 before:left-3 before:w-0.5 before:bg-outline-variant/30">
      ${events.map(ev => `
        <div class="relative flex items-start gap-4 pl-8">
          <div class="absolute left-1.5 top-1.5 w-3 h-3 rounded-full bg-primary ring-4 ring-surface"></div>
          <div class="p-3 rounded-lg bg-surface-container-low/80 border border-outline-variant/20 flex-1">
            <div class="font-body-md font-semibold text-on-surface">${escapeHtml(ev.title || ev.action)}</div>
            <div class="font-body-sm text-on-surface-variant mt-1">${escapeHtml(ev.description || '')}</div>
            <div class="font-label-md text-[11px] text-outline mt-2">${ev.timestamp ? new Date(ev.timestamp).toLocaleString() : ''}</div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
