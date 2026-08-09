import { login, checkAuth } from './auth.js';

document.addEventListener('DOMContentLoaded', async () => {
  // If user is already authenticated, redirect to dashboard
  await checkAuth();

  const form = document.querySelector('form');
  const emailInput = document.getElementById('email') || document.querySelector('input[type="email"]');
  const passwordInput = document.getElementById('password') || document.querySelector('input[type="password"]');
  const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

  if (!form) return;

  // Error Banner Container
  let errorBanner = document.getElementById('login-error-banner');
  if (!errorBanner) {
    errorBanner = document.createElement('div');
    errorBanner.id = 'login-error-banner';
    errorBanner.className = 'hidden mb-4 p-3 rounded-lg bg-error-container text-on-error-container text-body-sm font-body-sm';
    form.parentNode.insertBefore(errorBanner, form);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorBanner.classList.add('hidden');
    
    const email = emailInput ? emailInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value : '';

    if (!email || !password) {
      errorBanner.textContent = 'Please enter both email and password.';
      errorBanner.classList.remove('hidden');
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Signing in...';
    }

    try {
      await login(email, password);
      // Redirect to dashboard
      window.location.href = '../analytics_reports_crm_pro/code.html';
    } catch (err) {
      errorBanner.textContent = err.message || 'Invalid email or password.';
      errorBanner.classList.remove('hidden');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In';
      }
    }
  });
});
