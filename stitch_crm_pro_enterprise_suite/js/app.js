import { checkAuth, logout, getCurrentUser } from './auth.js';
import { applyRoleUI, getUserRole } from './rbac.js';
import { initGlobalSearch } from './search.js';
import { initNotifications } from './notifications.js';
import { initExportButtons } from './exports.js';

export async function initApp() {
  const user = await checkAuth();
  if (!user && !window.location.pathname.includes('/crm_pro_enterprise/')) {
    return;
  }

  // Bind Sidebar Links
  bindSidebarNav();

  // Apply RBAC UI hiding
  applyRoleUI();

  // Bind Header Search & Notifications
  initGlobalSearch();
  initNotifications();
  initExportButtons();

  // Bind Logout Button
  document.querySelectorAll('[data-action="logout"], button:has(span:contains("logout")), a[href*="login"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      logout();
    });
  });
}

function bindSidebarNav() {
  const navMap = {
    'Dashboard': '../analytics_reports_crm_pro/code.html',
    'Analytics': '../analytics_reports_crm_pro/code.html',
    'Companies': '../companies_crm_pro/code.html',
    'Contacts': '../contacts_crm_pro/code.html',
    'Leads': '../leads_management_crm_pro/code.html',
    'Pipelines': '../workflow_automation_crm_pro/code.html',
    'Workflow': '../workflow_automation_crm_pro/code.html',
    'Deals': '../workflow_automation_crm_pro/code.html',
    'Tasks': '../tasks_activities_crm_pro/code.html',
    'Activities': '../tasks_activities_crm_pro/code.html',
    'Team': '../team_performance_crm_pro/code.html',
    'Notifications': '../notifications_crm_pro/code.html',
    'User Management': '../user_management_crm_pro/code.html',
    'Settings': '../settings_crm_pro/code.html'
  };

  const navLinks = document.querySelectorAll('aside a, nav a');
  navLinks.forEach(link => {
    const text = link.textContent.trim();
    for (const [key, targetUrl] of Object.entries(navMap)) {
      if (text.includes(key)) {
        link.href = targetUrl;
        break;
      }
    }
  });
}
