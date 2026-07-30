// Shared fetch() helper: attaches the CSRF token Django expects on
// unsafe methods and centralizes JSON handling + toast errors, so every
// other JS file can make one-line API calls instead of full page reloads.

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const CSRF_TOKEN = getCookie('csrftoken');

async function api(path, { method = 'GET', body = null, isFormData = false } = {}) {
  const headers = {};
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers['X-CSRFToken'] = CSRF_TOKEN;
  }
  if (body && !isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    const message = (data && data.detail) || 'Something went wrong.';
    throw new Error(message);
  }
  return data;
}

function showToast(message, kind = 'success') {
  const el = document.createElement('div');
  el.className = kind === 'error' ? 'toast-error' : 'toast-success';
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}
