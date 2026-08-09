import { apiGet } from './api.js';
import { initApp } from './app.js';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();
  await loadDashboardData();
});

async function loadDashboardData() {
  try {
    // Fetch all dashboard summary endpoints in parallel
    const [summary, salesPerf, leadAnalytics, pipelineAnalytics, revenueTrend, activitySummary, teamPerf] = await Promise.allSettled([
      apiGet('/dashboard/summary'),
      apiGet('/dashboard/sales-performance'),
      apiGet('/dashboard/lead-analytics'),
      apiGet('/dashboard/pipeline-analytics'),
      apiGet('/dashboard/revenue-trend'),
      apiGet('/dashboard/activity-summary'),
      apiGet('/dashboard/team-performance')
    ]);

    if (summary.status === 'fulfilled' && summary.value) {
      updateKpiCards(summary.value);
    }

    if (salesPerf.status === 'fulfilled' && salesPerf.value) {
      renderSalesPerformance(salesPerf.value);
    }

    if (leadAnalytics.status === 'fulfilled' && leadAnalytics.value) {
      renderLeadAnalytics(leadAnalytics.value);
    }

    if (pipelineAnalytics.status === 'fulfilled' && pipelineAnalytics.value) {
      renderPipelineAnalytics(pipelineAnalytics.value);
    }

    if (revenueTrend.status === 'fulfilled' && revenueTrend.value) {
      renderRevenueTrend(revenueTrend.value);
    }

    if (activitySummary.status === 'fulfilled' && activitySummary.value) {
      renderActivitySummary(activitySummary.value);
    }

    if (teamPerf.status === 'fulfilled' && teamPerf.value) {
      renderTeamPerformance(teamPerf.value);
    }

  } catch (err) {
    console.error('Error loading dashboard data:', err);
  }
}

function updateKpiCards(data) {
  // Update KPI card values dynamically if elements exist or find cards by text
  const cards = document.querySelectorAll('.font-headline-lg, .text-headline-lg');
  
  // Total Revenue
  if (data.total_revenue !== undefined) {
    const revEl = document.querySelector('[data-kpi="revenue"]') || cards[0];
    if (revEl) revEl.textContent = `$${Number(data.total_revenue || 0).toLocaleString()}`;
  }

  // Active Deals
  if (data.active_deals_count !== undefined) {
    const dealsEl = document.querySelector('[data-kpi="deals"]') || cards[1];
    if (dealsEl) dealsEl.textContent = Number(data.active_deals_count || 0).toLocaleString();
  }

  // Conversion Rate
  if (data.conversion_rate !== undefined) {
    const convEl = document.querySelector('[data-kpi="conversion"]') || cards[2];
    if (convEl) convEl.textContent = `${Number(data.conversion_rate || 0).toFixed(1)}%`;
  }

  // Total Leads
  if (data.total_leads_count !== undefined) {
    const leadsEl = document.querySelector('[data-kpi="leads"]') || cards[3];
    if (leadsEl) leadsEl.textContent = Number(data.total_leads_count || 0).toLocaleString();
  }
}

function renderSalesPerformance(data) {
  const container = document.querySelector('[data-section="sales-performance"]');
  if (!container) return;

  if (Array.isArray(data) && data.length > 0) {
    container.innerHTML = `
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b border-outline-variant/30 text-label-md text-outline">
              <th class="py-3 px-4">Period</th>
              <th class="py-3 px-4">Deals Won</th>
              <th class="py-3 px-4">Revenue</th>
              <th class="py-3 px-4">Win Rate</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant/20 font-body-sm text-on-surface">
            ${data.map(item => `
              <tr>
                <td class="py-3 px-4 font-semibold">${item.period || item.month || 'Current'}</td>
                <td class="py-3 px-4">${item.deals_won || 0}</td>
                <td class="py-3 px-4 font-semibold text-primary">$${Number(item.revenue || 0).toLocaleString()}</td>
                <td class="py-3 px-4">${Number(item.win_rate || 0).toFixed(1)}%</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }
}

function renderLeadAnalytics(data) {
  const container = document.querySelector('[data-section="lead-analytics"]');
  if (!container) return;

  const byStatus = data.by_status || {};
  const bySource = data.by_source || {};

  let statusHtml = Object.entries(byStatus).map(([status, count]) => `
    <div class="flex items-center justify-between py-2 border-b border-outline-variant/20">
      <span class="font-body-md text-on-surface capitalize">${status.replace('_', ' ')}</span>
      <span class="font-headline-md font-bold text-primary">${count}</span>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="space-y-4">
      <h3 class="font-headline-md text-headline-md text-on-surface font-semibold mb-2">Leads by Status</h3>
      <div class="space-y-1">${statusHtml || '<p class="text-on-surface-variant text-body-sm">No lead data</p>'}</div>
    </div>
  `;
}

function renderPipelineAnalytics(data) {
  const container = document.querySelector('[data-section="pipeline-analytics"]');
  if (!container) return;

  const stages = data.by_stage || [];
  let html = stages.map(s => `
    <div class="py-2 border-b border-outline-variant/20">
      <div class="flex justify-between text-body-md font-semibold text-on-surface mb-1">
        <span>${s.stage_name || s.name}</span>
        <span>$${Number(s.total_value || 0).toLocaleString()} (${s.count || 0})</span>
      </div>
      <div class="w-full bg-surface-container-high h-2 rounded-full overflow-hidden">
        <div class="bg-primary h-full rounded-full" style="width: ${Math.min(100, s.count * 10)}%"></div>
      </div>
    </div>
  `).join('');

  container.innerHTML = `<div class="space-y-2">${html || '<p class="text-on-surface-variant text-body-sm">No pipeline data</p>'}</div>`;
}

function renderRevenueTrend(data) {
  const container = document.querySelector('[data-section="revenue-trend"]');
  if (!container) return;

  const points = Array.isArray(data) ? data : (data.trend || []);
  if (points.length === 0) return;

  container.innerHTML = `
    <div class="flex items-end gap-3 h-40 pt-4 px-2 border-b border-outline-variant/30">
      ${points.map(pt => {
        const maxVal = Math.max(...points.map(p => p.revenue || 1));
        const heightPct = Math.max(10, Math.round(((pt.revenue || 0) / maxVal) * 100));
        return `
          <div class="flex-1 flex flex-col items-center gap-2 h-full justify-end">
            <div class="w-full bg-primary-container hover:bg-primary rounded-t-lg transition-all" style="height: ${heightPct}%" title="$${Number(pt.revenue || 0).toLocaleString()}"></div>
            <span class="font-label-md text-[11px] text-outline">${pt.period || pt.date || ''}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderActivitySummary(data) {
  const container = document.querySelector('[data-section="activity-summary"]');
  if (!container) return;

  const activities = Array.isArray(data) ? data : (data.summary || []);
  container.innerHTML = `
    <div class="space-y-2">
      ${activities.map(act => `
        <div class="flex items-center justify-between p-2 rounded-lg bg-surface-container-low">
          <span class="font-body-md text-on-surface font-semibold capitalize">${act.activity_type || act.type}</span>
          <span class="font-body-md text-primary font-bold">${act.count || 0}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderTeamPerformance(data) {
  const container = document.querySelector('[data-section="team-performance"]');
  if (!container) return;

  const members = Array.isArray(data) ? data : (data.team || []);
  container.innerHTML = `
    <div class="overflow-x-auto">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-outline-variant/30 text-label-md text-outline">
            <th class="py-3 px-4">Sales Rep</th>
            <th class="py-3 px-4">Deals Closed</th>
            <th class="py-3 px-4">Revenue Generated</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-outline-variant/20 font-body-sm text-on-surface">
          ${members.map(m => `
            <tr>
              <td class="py-3 px-4 font-semibold">${m.user_name || m.name}</td>
              <td class="py-3 px-4">${m.deals_closed || 0}</td>
              <td class="py-3 px-4 font-bold text-primary">$${Number(m.revenue_generated || 0).toLocaleString()}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}
