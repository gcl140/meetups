// Event form: live-preview the cover image as soon as one is chosen,
// instead of only seeing it after saving.
//
// Exposed as window.initCoverPreview(root) so the edit modal can re-run
// this after swapping in fresh form HTML fetched after DOMContentLoaded
// already fired.

function initCoverPreview(root = document) {
  const input = root.querySelector('#id_cover_image');
  const preview = root.querySelector('#cover-preview-img');
  const fallback = root.querySelector('#cover-preview-fallback');
  if (!input || !preview || input.dataset.previewBound) return;
  input.dataset.previewBound = 'true';

  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      preview.src = e.target.result;
      preview.classList.remove('hidden');
      fallback?.classList.add('hidden');
    };
    reader.readAsDataURL(file);
  });
}

window.initCoverPreview = initCoverPreview;
document.addEventListener('DOMContentLoaded', () => initCoverPreview(document));
