// Shared fetch() helper: attaches the CSRF token Django expects on
// unsafe methods and centralizes JSON handling + toast errors, so every
// other JS file can make one-line API calls instead of full page reloads.

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const CSRF_TOKEN = getCookie('csrftoken');

async function api(path, { method = 'GET', body = null, isFormData = false } = {}) {
  // Marks every request made through this helper as AJAX, so views that
  // render both a full page and a JSON/fragment response (e.g. the event
  // edit modal) can tell which one to send back.
  const headers = { 'X-Requested-With': 'fetch' };
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
    // DRF's default validation errors come back as {field: ["msg"]} or
    // {non_field_errors: ["msg"]} rather than {detail: "msg"} -- fall back
    // to the first error message found so those aren't silently swallowed
    // into a generic "Something went wrong."
    let message = 'Something went wrong.';
    if (data && typeof data === 'object') {
      if (data.detail) {
        message = data.detail;
      } else {
        const firstValue = Object.values(data)[0];
        if (Array.isArray(firstValue) && firstValue.length) message = firstValue[0];
        else if (typeof firstValue === 'string') message = firstValue;
      }
    }
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
