// Dashboard: joining an open event happens via the API so the card
// updates in place instead of a full page reload/redirect.

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-join-slug]');
  if (!btn) return;

  const slug = btn.dataset.joinSlug;
  btn.disabled = true;
  btn.textContent = 'Joining…';

  try {
    await api(`/api/events/${slug}/join/`, { method: 'POST' });
    showToast("You're going! Redirecting to the event…");
    window.location.href = `/events/${slug}/`;
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.textContent = 'Join event';
  }
});
