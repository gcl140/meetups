// Event detail page: RSVP, leave, admin invite/remove, actions, photos and
// planning calls all go through the API so none of these require a full
// page reload, the DOM is patched in place after each call succeeds.

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('event-detail-root');
  if (!root) return;

  const slug = root.dataset.eventSlug;
  const isAdmin = root.dataset.isAdmin === 'true';

  // "YYYY-MM-DDTHH:MM" in local time, suitable for a datetime-local input's min attribute.
  function nowLocalInputValue() {
    const now = new Date();
    now.setSeconds(0, 0);
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  // ---- RSVP ----
  document.querySelectorAll('[data-rsvp]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const status = btn.dataset.rsvp;
      try {
        await api(`/api/events/${slug}/rsvp/`, { method: 'PATCH', body: { rsvp_status: status } });
        document.querySelectorAll('[data-rsvp]').forEach((b) => b.classList.toggle('btn-primary', b === btn));
        document.querySelectorAll('[data-rsvp]').forEach((b) => b.classList.toggle('btn-outline', b !== btn));
        const badge = document.getElementById('my-rsvp-badge');
        if (badge) {
          badge.textContent = btn.textContent.trim();
          badge.className = `badge-${status}`;
        }
        showToast('RSVP updated.');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // ---- Leave event ----
  const leaveBtn = document.getElementById('leave-event-btn');
  if (leaveBtn) {
    leaveBtn.addEventListener('click', async () => {
      if (!confirm('Leave this event?')) return;
      try {
        await api(`/api/events/${slug}/leave/`, { method: 'POST' });
        window.location.href = '/';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // ---- Admin: remove member ----
  document.querySelectorAll('[data-remove-user]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm('Remove this person from the event?')) return;
      const userId = btn.dataset.removeUser;
      try {
        await api(`/api/events/${slug}/members/${userId}/remove/`, { method: 'POST' });
        document.getElementById(`member-row-${userId}`)?.remove();
        showToast('Member removed.');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });

  // ---- Admin: invite by email ----
  const inviteForm = document.getElementById('invite-form');
  if (inviteForm) {
    inviteForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const emailInput = inviteForm.querySelector('input[name="email"]');
      try {
        const data = await api(`/api/events/${slug}/invite/`, { method: 'POST', body: { email: emailInput.value } });
        showToast(data.detail);
        emailInput.value = '';
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // ---- Share link copy ----
  const copyBtn = document.getElementById('copy-share-link');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(copyBtn.dataset.shareUrl);
      showToast('Share link copied.');
    });
  }

  // ---- Actions (before/after event) ----
  const actionForm = document.getElementById('action-form');
  if (actionForm) {
    actionForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(actionForm);
      const body = Object.fromEntries(formData.entries());
      try {
        const action = await api(`/api/events/${slug}/actions/`, { method: 'POST', body });
        addActionRow(action);
        actionForm.reset();
        showToast('Action added.');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  document.querySelectorAll('[data-delete-action]').forEach(bindDeleteAction);
  document.querySelectorAll('[data-toggle-action-complete]').forEach(bindToggleActionComplete);

  function bindDeleteAction(btn) {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.deleteAction;
      if (!confirm('Delete this action item?')) return;
      try {
        await api(`/api/actions/${id}/`, { method: 'DELETE' });
        document.getElementById(`action-row-${id}`)?.remove();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  function bindToggleActionComplete(btn) {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.toggleActionComplete;
      try {
        const action = await api(`/api/actions/${id}/complete/`, { method: 'POST' });
        applyActionCompletion(id, action);
        showToast(action.my_is_completed ? 'Marked complete.' : 'Marked incomplete.');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  function applyActionCompletion(id, action) {
    const row = document.getElementById(`action-row-${id}`);
    if (!row) return;
    const title = row.querySelector('p.font-medium');
    const deadline = row.querySelector('[data-action-deadline]');
    const doneBy = row.querySelector('[data-action-done-by]');
    const btn = row.querySelector('[data-toggle-action-complete]');

    if (title) title.classList.toggle('line-through', action.my_is_completed);
    if (title) title.classList.toggle('text-wood-400', action.my_is_completed);
    if (deadline) {
      let text = `Due ${new Date(action.deadline).toLocaleString()}`;
      if (action.my_is_completed) text += " · You've done this";
      deadline.textContent = text;
    }
    if (doneBy) {
      const names = action.completed_by_names || [];
      doneBy.textContent = `Done by: ${names.join(', ')}`;
      doneBy.classList.toggle('hidden', names.length === 0);
    }
    if (btn) {
      btn.classList.toggle('btn-secondary', !action.my_is_completed);
      btn.classList.toggle('btn-outline', action.my_is_completed);
      btn.innerHTML = action.my_is_completed
        ? '<i class="fa-solid fa-rotate-left"></i> Undo'
        : '<i class="fa-solid fa-check"></i> Complete';
    }
  }

  function addActionRow(action) {
    const list = document.getElementById(`actions-${action.action_type}`);
    if (!list) return;
    const li = document.createElement('li');
    li.id = `action-row-${action.id}`;
    li.className = 'flex items-center justify-between gap-3 py-2 border-b border-wood-100 last:border-0';

    const text = document.createElement('div');
    text.className = 'min-w-0';
    const title = document.createElement('p');
    title.className = 'font-medium text-wood-900';
    title.textContent = action.title;
    const deadline = document.createElement('p');
    deadline.dataset.actionDeadline = '';
    deadline.className = 'text-xs text-wood-500';
    deadline.textContent = `Due ${new Date(action.deadline).toLocaleString()}`;
    const doneBy = document.createElement('p');
    doneBy.dataset.actionDoneBy = '';
    doneBy.className = 'text-xs text-wood-400 hidden';
    text.append(title, deadline, doneBy);

    li.appendChild(text);

    const actions = document.createElement('div');
    actions.className = 'flex gap-2 shrink-0';

    const complete = document.createElement('button');
    complete.className = 'btn-sm btn-secondary';
    complete.innerHTML = '<i class="fa-solid fa-check"></i> Complete';
    complete.dataset.toggleActionComplete = action.id;
    bindToggleActionComplete(complete);
    actions.appendChild(complete);

    if (isAdmin) {
      const del = document.createElement('button');
      del.className = 'btn-outline btn-sm';
      del.textContent = 'Delete';
      del.dataset.deleteAction = action.id;
      bindDeleteAction(del);
      actions.appendChild(del);
    }
    li.appendChild(actions);
    list.appendChild(li);
  }

  // ---- Photos ----
  const photoForm = document.getElementById('photo-form');
  if (photoForm) {
    photoForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        const photo = await api(`/api/events/${slug}/photos/`, {
          method: 'POST', body: new FormData(photoForm), isFormData: true,
        });
        addPhotoCard(photo);
        photoForm.reset();
        showToast('Photo added.');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  document.querySelectorAll('[data-delete-photo]').forEach(bindDeletePhoto);

  function bindDeletePhoto(btn) {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.deletePhoto;
      if (!confirm('Delete this photo?')) return;
      try {
        await api(`/api/photos/${id}/`, { method: 'DELETE' });
        document.getElementById(`photo-card-${id}`)?.remove();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  function addPhotoCard(photo) {
    const gallery = document.getElementById('photo-gallery');
    if (!gallery) return;
    const card = document.createElement('div');
    card.id = `photo-card-${photo.id}`;
    card.className = 'relative rounded-xl overflow-hidden border border-wood-200';

    if (photo.image) {
      const img = document.createElement('img');
      img.src = photo.image;
      img.className = 'w-full h-32 object-cover';
      card.appendChild(img);
    } else if (photo.external_url) {
      const link = document.createElement('a');
      link.href = photo.external_url;
      link.target = '_blank';
      link.className = 'block p-4 text-sm underline';
      link.textContent = photo.caption || photo.external_url;
      card.appendChild(link);
    }

    if (photo.caption && photo.image) {
      const cap = document.createElement('p');
      cap.className = 'text-xs px-2 py-1 text-wood-600';
      cap.textContent = photo.caption;
      card.appendChild(cap);
    }

    const del = document.createElement('button');
    del.className = 'absolute top-1 right-1 btn-danger btn-sm';
    del.textContent = '✕';
    del.dataset.deletePhoto = photo.id;
    bindDeletePhoto(del);
    card.appendChild(del);

    gallery.prepend(card);
  }

  // ---- Planning calls ----
  const callForm = document.getElementById('call-form');
  if (callForm) {
    // Client-side nudge only -- the server rejects a past scheduled_at (or
    // an ends_at at/before it) regardless, this just stops the obvious case
    // before a round trip.
    const startInput = callForm.querySelector('input[name="scheduled_at"]');
    const endInput = callForm.querySelector('input[name="ends_at"]');
    if (startInput && endInput) {
      const nowValue = nowLocalInputValue();
      startInput.min = nowValue;
      endInput.min = startInput.value || nowValue;
      startInput.addEventListener('input', () => {
        endInput.min = startInput.value || nowValue;
      });
    }

    callForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(callForm);
      const body = Object.fromEntries(formData.entries());
      // Unlike text fields, DRF's DateTimeField rejects '' outright rather
      // than treating it as "not provided" -- drop it so leaving the
      // optional end time blank doesn't itself trip the past-date check.
      if (!body.ends_at) delete body.ends_at;
      try {
        const call = await api(`/api/events/${slug}/calls/`, { method: 'POST', body });
        addCallRow(call);
        callForm.reset();
        showToast('Planning call added.');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  document.querySelectorAll('[data-delete-call]').forEach(bindDeleteCall);
  document.querySelectorAll('[data-call-rsvp]').forEach(bindCallRsvp);
  document.querySelectorAll('[data-call-menu-trigger]').forEach(bindCallMenu);

  function closeAllCallMenus() {
    document.querySelectorAll('[id^="call-menu-"]').forEach((panel) => {
      panel.classList.add('hidden');
      document.querySelector(`[data-call-menu-trigger="${panel.id.replace('call-menu-', '')}"]`)
        ?.setAttribute('aria-expanded', 'false');
    });
  }

  function bindCallMenu(btn) {
    const panel = document.getElementById(`call-menu-${btn.dataset.callMenuTrigger}`);
    if (!panel) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = !panel.classList.contains('hidden');
      closeAllCallMenus();
      panel.classList.toggle('hidden', isOpen);
      btn.setAttribute('aria-expanded', String(!isOpen));
    });
  }

  document.addEventListener('click', closeAllCallMenus);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllCallMenus();
  });

  function bindDeleteCall(btn) {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.deleteCall;
      if (!confirm('Delete this planning call?')) return;
      try {
        await api(`/api/calls/${id}/`, { method: 'DELETE' });
        document.getElementById(`call-row-${id}`)?.remove();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  function bindCallRsvp(btn) {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.callRsvp;
      const willAttend = btn.dataset.attend === 'true';
      try {
        const call = await api(`/api/calls/${id}/rsvp/`, { method: 'POST', body: { will_attend: willAttend } });
        applyCallRsvp(id, call);
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  function applyCallRsvp(id, call) {
    const row = document.getElementById(`call-row-${id}`);
    if (!row) return;
    row.querySelectorAll('[data-call-rsvp]').forEach((b) => {
      const active = b.dataset.attend === String(call.my_will_attend);
      b.classList.toggle('btn-primary', active);
      b.classList.toggle('btn-outline', !active);
    });
    const icsLink = row.querySelector('[data-call-ics-link]');
    if (icsLink) icsLink.classList.toggle('hidden', call.my_will_attend !== true);

    const attendees = row.querySelector(`#call-attendees-${id}`);
    if (attendees) {
      attendees.innerHTML = '<i class="fa-solid fa-user-group text-copper-500 mr-1"></i>' + (
        call.attendees && call.attendees.length
          ? `Attending: ${call.attendees.join(', ')}`
          : "No one has said they're attending yet."
      );
    }
  }

  function addCallRow(call) {
    const list = document.getElementById('calls-list');
    if (!list) return;
    const li = document.createElement('li');
    li.id = `call-row-${call.id}`;
    li.className = 'py-3 border-b border-wood-100 last:border-0';

    // Title and call_link come from an admin's free-text/URL input, so they're
    // set via textContent/href below rather than interpolated into this markup.
    li.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p data-call-title class="font-medium text-wood-900"></p>
          <p data-call-when class="text-xs text-wood-500 mt-0.5"></p>
        </div>
        <div class="relative shrink-0">
          <button type="button" data-call-menu-trigger="${call.id}" class="icon-btn" aria-label="More options" aria-haspopup="true" aria-expanded="false">
            <i class="fa-solid fa-ellipsis-vertical"></i>
          </button>
          <div id="call-menu-${call.id}" class="dropdown-panel hidden">
            <a data-call-ics-link href="/events/${slug}/calls/${call.id}/export.ics" class="dropdown-item hidden">
              <i class="fa-solid fa-calendar-days w-4"></i>Add to calendar
            </a>
            ${isAdmin ? `<button type="button" data-delete-call="${call.id}" class="dropdown-item-danger"><i class="fa-solid fa-trash w-4"></i>Delete call</button>` : ''}
          </div>
        </div>
      </div>
      <div class="flex flex-col gap-2 mt-2.5">
        <a data-call-join-link target="_blank" class="btn-outline btn-sm w-full hidden"><i class="fa-solid fa-video"></i> Join call</a>
        <div class="flex gap-2">
          <button data-call-rsvp="${call.id}" data-attend="true" class="btn-sm flex-1 btn-outline"><i class="fa-solid fa-check"></i> I'll attend</button>
          <button data-call-rsvp="${call.id}" data-attend="false" class="btn-sm flex-1 btn-outline"><i class="fa-solid fa-xmark"></i> Can't make it</button>
        </div>
      </div>
      <p id="call-attendees-${call.id}" class="text-xs text-wood-500 mt-2">
        <i class="fa-solid fa-user-group text-copper-500 mr-1"></i>No one has said they're attending yet.
      </p>
    `;

    li.querySelector('[data-call-title]').textContent = call.title;

    let whenText = new Date(call.scheduled_at).toLocaleString();
    if (call.ends_at) {
      const endTime = new Date(call.ends_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      whenText += `–${endTime} (${call.duration_minutes} min)`;
    }
    li.querySelector('[data-call-when]').textContent = whenText;

    const joinLink = li.querySelector('[data-call-join-link]');
    if (call.call_link) {
      joinLink.href = call.call_link;
      joinLink.classList.remove('hidden');
    } else {
      joinLink.remove();
    }

    li.querySelectorAll('[data-call-rsvp]').forEach(bindCallRsvp);
    const deleteBtn = li.querySelector('[data-delete-call]');
    if (deleteBtn) bindDeleteCall(deleteBtn);
    bindCallMenu(li.querySelector('[data-call-menu-trigger]'));

    list.appendChild(li);
  }

  // ---- Cover image lightbox ----
  const coverTrigger = document.getElementById('cover-image-trigger');
  const lightbox = document.getElementById('image-lightbox');
  if (coverTrigger && lightbox) {
    coverTrigger.addEventListener('click', () => lightbox.showModal());
    lightbox.querySelector('[data-lightbox-close]')?.addEventListener('click', () => lightbox.close());
    lightbox.addEventListener('click', (e) => {
      if (e.target === lightbox) lightbox.close();
    });
  }

  // ---- Attendance modal ----
  const attendanceBtn = document.getElementById('open-attendance-btn');
  const attendanceModal = document.getElementById('attendance-modal');
  const attendanceList = document.getElementById('attendance-list');
  if (attendanceBtn && attendanceModal && attendanceList) {
    const currentUserId = root.dataset.userId;

    function renderAttendanceRow(record) {
      const li = document.createElement('li');
      li.id = `attendance-row-${record.user}`;
      li.className = 'flex items-center justify-between gap-3 py-2';

      const name = document.createElement('span');
      name.className = 'font-medium text-wood-900';
      name.textContent = record.user_name;

      const btn = document.createElement('button');
      const canToggle = isAdmin || String(record.user) === String(currentUserId);
      btn.disabled = !canToggle;
      btn.className = record.checked_in_at ? 'btn-primary btn-sm' : 'btn-outline btn-sm';
      btn.innerHTML = record.checked_in_at
        ? '<i class="fa-solid fa-check"></i> Checked in'
        : '<i class="fa-regular fa-circle"></i> Check in';
      if (canToggle) {
        btn.addEventListener('click', async () => {
          try {
            await api(`/api/events/${slug}/attendance/${record.user}/toggle/`, { method: 'POST' });
            loadAttendance();
          } catch (err) {
            showToast(err.message, 'error');
          }
        });
      }

      li.append(name, btn);
      return li;
    }

    async function loadAttendance() {
      try {
        const records = await api(`/api/events/${slug}/attendance/`);
        attendanceList.innerHTML = '';
        records.forEach((r) => attendanceList.appendChild(renderAttendanceRow(r)));
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    attendanceBtn.addEventListener('click', () => {
      attendanceModal.showModal();
      loadAttendance();
    });
    attendanceModal.querySelector('[data-attendance-close]')?.addEventListener('click', () => attendanceModal.close());
    attendanceModal.addEventListener('click', (e) => {
      if (e.target === attendanceModal) attendanceModal.close();
    });
  }
});
