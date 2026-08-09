import { getCurrentUser } from './auth.js';

export const ROLES = {
  ADMIN: 'Administrator',
  MANAGER: 'Sales Manager',
  REP: 'Sales Representative',
  VIEWER: 'Viewer'
};

export function getUserRole() {
  const user = getCurrentUser();
  if (!user) return null;
  return user.role ? user.role.name : null;
}

export function isAdmin() {
  const role = getUserRole();
  return role === ROLES.ADMIN;
}

export function isManagerOrAdmin() {
  const role = getUserRole();
  return role === ROLES.ADMIN || role === ROLES.MANAGER;
}

export function isViewer() {
  const role = getUserRole();
  return role === ROLES.VIEWER;
}

export function canCreateOrEdit() {
  const role = getUserRole();
  return role === ROLES.ADMIN || role === ROLES.MANAGER || role === ROLES.REP;
}

export function canDelete() {
  const role = getUserRole();
  return role === ROLES.ADMIN || role === ROLES.MANAGER;
}

export function applyRoleUI() {
  const role = getUserRole();
  const user = getCurrentUser();

  // Update profile user display in UI if elements exist
  const userElements = document.querySelectorAll('[data-user-name]');
  userElements.forEach(el => {
    if (user && user.full_name) {
      el.textContent = user.full_name;
    }
  });

  const roleElements = document.querySelectorAll('[data-user-role]');
  roleElements.forEach(el => {
    if (role) {
      el.textContent = role;
    }
  });

  // Hide action buttons for Viewer role
  if (isViewer()) {
    document.querySelectorAll('.btn-create, .btn-edit, .btn-delete, [data-action="create"], [data-action="edit"], [data-action="delete"]').forEach(btn => {
      btn.style.display = 'none';
    });
  }

  // Hide Audit Logs and User Management link if not Admin/Manager
  if (!isManagerOrAdmin()) {
    document.querySelectorAll('[data-nav="user-management"]').forEach(el => {
      el.style.display = 'none';
    });
  }
}
