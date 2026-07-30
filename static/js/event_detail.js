// Event detail page: RSVP, leave, admin invite/remove, actions, photos and
// planning calls all go through the API so none of these require a full
// page reload — the DOM is patched in place after each call succeeds.

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('event-detail-root');
  if (!root) return;

  const slug = root.dataset.eventSlug;
  const isAdmin = root.dataset.isAdmin === 'true';

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

  function addActionRow(action) {
    const list = document.getElementById(`actions-${action.action_type}`);
    if (!list) return;
    const li = document.createElement('li');
    li.id = `action-row-${action.id}`;
    li.className = 'flex items-center justify-between gap-3 py-2 border-b border-wood-100 last:border-0';

    const text = document.createElement('div');
    const title = document.createElement('p');
    title.className = 'font-medium text-wood-900';
    title.textContent = action.title;
    const deadline = document.createElement('p');
    deadline.className = 'text-xs text-wood-500';
    deadline.textContent = `Due ${new Date(action.deadline).toLocaleString()}`;
    text.append(title, deadline);

    li.appendChild(text);

    if (isAdmin) {
      const del = document.createElement('button');
      del.className = 'btn-outline btn-sm';
      del.textContent = 'Delete';
      del.dataset.deleteAction = action.id;
      bindDeleteAction(del);
      li.appendChild(del);
    }
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
    callForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(callForm);
      const body = Object.fromEntries(formData.entries());
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

  function addCallRow(call) {
    const list = document.getElementById('calls-list');
    if (!list) return;
    const li = document.createElement('li');
    li.id = `call-row-${call.id}`;
    li.className = 'flex items-center justify-between gap-3 py-2 border-b border-wood-100 last:border-0';

    const text = document.createElement('div');
    const title = document.createElement('p');
    title.className = 'font-medium text-wood-900';
    title.textContent = call.title;
    const when = document.createElement('p');
    when.className = 'text-xs text-wood-500';
    when.textContent = new Date(call.scheduled_at).toLocaleString();
    text.append(title, when);
    li.appendChild(text);

    if (call.call_link) {
      const link = document.createElement('a');
      link.href = call.call_link;
      link.target = '_blank';
      link.className = 'btn-outline btn-sm';
      link.textContent = 'Join call';
      li.appendChild(link);
    }

    if (isAdmin) {
      const del = document.createElement('button');
      del.className = 'btn-outline btn-sm';
      del.textContent = 'Delete';
      del.dataset.deleteCall = call.id;
      bindDeleteCall(del);
      li.appendChild(del);
    }
    list.appendChild(li);
  }
});
