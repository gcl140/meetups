// Attendance tracker: loads the roster via the API and lets the admin (or
// members, for themselves) toggle check-in state without reloading.

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.getElementById('attendance-root');
  if (!root) return;

  const slug = root.dataset.eventSlug;
  const currentUserId = root.dataset.userId;
  const isAdmin = root.dataset.isAdmin === 'true';
  const list = document.getElementById('attendance-list');

  function renderRow(record) {
    const li = document.createElement('li');
    li.id = `attendance-row-${record.user}`;
    li.className = 'flex items-center justify-between gap-3 py-2 border-b border-wood-100 last:border-0';

    const name = document.createElement('span');
    name.className = 'font-medium text-wood-900';
    name.textContent = record.user_name;

    const btn = document.createElement('button');
    const canToggle = isAdmin || String(record.user) === String(currentUserId);
    btn.disabled = !canToggle;
    btn.className = record.checked_in_at ? 'btn-primary btn-sm' : 'btn-outline btn-sm';
    btn.textContent = record.checked_in_at ? 'Checked in ✓' : 'Check in';
    if (canToggle) {
      btn.addEventListener('click', async () => {
        try {
          await api(`/api/events/${slug}/attendance/${record.user}/toggle/`, { method: 'POST' });
          renderList(await refresh());
        } catch (err) {
          showToast(err.message, 'error');
        }
      });
    }

    li.append(name, btn);
    return li;
  }

  function renderList(records) {
    list.innerHTML = '';
    records.forEach((r) => list.appendChild(renderRow(r)));
  }

  async function refresh() {
    const records = await api(`/api/events/${slug}/attendance/`);
    return records;
  }

  try {
    renderList(await refresh());
  } catch (err) {
    showToast(err.message, 'error');
  }
});
