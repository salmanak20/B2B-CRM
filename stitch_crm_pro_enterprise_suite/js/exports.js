import { apiFetch } from './api.js';

export async function downloadCsvExport(entityType) {
  try {
    const blob = await apiFetch(`/exports/${entityType}`, { method: 'GET' });
    if (!blob) return;

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${entityType}_export_${new Date().toISOString().substring(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Failed to export ${entityType}: ${err.message}`);
  }
}

export function initExportButtons() {
  document.querySelectorAll('[data-export]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const entity = btn.getAttribute('data-export');
      if (entity) {
        downloadCsvExport(entity);
      }
    });
  });
}
