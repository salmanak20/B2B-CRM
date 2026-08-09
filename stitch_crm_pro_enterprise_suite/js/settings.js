import { getCurrentUser } from './auth.js';
import { initApp } from './app.js';

document.addEventListener('DOMContentLoaded', async () => {
  await initApp();

  const user = getCurrentUser();
  if (!user) return;

  const nameInput = document.getElementById('profile-name') || document.querySelector('input[value*="Salman"], input[name="name"]');
  const emailInput = document.getElementById('profile-email') || document.querySelector('input[type="email"]');
  const roleInput = document.getElementById('profile-role') || document.querySelector('input[value*="Admin"]');

  if (nameInput && user.full_name) nameInput.value = user.full_name;
  if (emailInput && user.email) emailInput.value = user.email;
  if (roleInput && user.role) roleInput.value = user.role.name;
});
