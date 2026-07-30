// Edit event as a modal (native <dialog>) instead of navigating to its
// own page. Fetches the same form the standalone /edit/ page renders
// (events/_event_form_fields.html), just as a fragment, and posts back
// to the same URL; the view detects the X-Requested-With: fetch header
// and responds with JSON instead of a redirect.

document.addEventListener('DOMContentLoaded', () => {
  const editBtn = document.getElementById('edit-event-btn');
  const modal = document.getElementById('edit-event-modal');
  const modalContent = document.getElementById('edit-event-modal-content');
  const root = document.getElementById('event-detail-root');
  if (!editBtn || !modal || !modalContent || !root) return;

  const slug = root.dataset.eventSlug;

  function bindForm() {
    window.initGeolocationButton?.(modalContent);
    window.initCoverPreview?.(modalContent);

    modalContent.querySelector('[data-modal-close]')?.addEventListener('click', () => modal.close());

    const form = modalContent.querySelector('[data-modal-form]');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      const originalLabel = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving…';

      try {
        const data = await api(form.getAttribute('action'), {
          method: 'POST', body: new FormData(form), isFormData: true,
        });
        if (data.success) {
          modal.close();
          window.location.reload();
          return;
        }
        modalContent.innerHTML = data.html;
        bindForm();
        showToast('Please fix the highlighted fields.', 'error');
      } catch (err) {
        showToast(err.message, 'error');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalLabel;
      }
    });
  }

  async function openModal() {
    modalContent.innerHTML = '<div class="p-10 text-center text-wood-400"><i class="fa-solid fa-spinner fa-spin text-2xl"></i></div>';
    modal.showModal();
    try {
      const response = await fetch(`/events/${slug}/edit/`, {
        headers: { 'X-Requested-With': 'fetch' },
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error('Could not load the edit form.');
      modalContent.innerHTML = await response.text();
      bindForm();
    } catch (err) {
      modalContent.innerHTML = `<p class="p-6 text-sm text-red-700">${err.message}</p>`;
    }
  }

  editBtn.addEventListener('click', openModal);

  // Click on the backdrop (outside the dialog's own box) closes it.
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.close();
  });
});
