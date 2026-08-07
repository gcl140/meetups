// Rich-text editing for the event description field, via Quill
// (https://quilljs.com). The real form field is a hidden <textarea id="id_description">
// -- Quill mounts over a separate <div id="description-editor"> and every
// keystroke syncs its HTML back into the hidden textarea, so it still
// submits like any other form field (works for both a plain POST and the
// edit modal's FormData-based fetch). The server re-sanitizes on save
// (events/richtext.py) regardless of what the client sends.
//
// Exposed as window.initDescriptionEditor(root) so the edit modal can
// re-run this after swapping in fresh form HTML fetched after
// DOMContentLoaded already fired.

function initDescriptionEditor(root = document) {
  const editorEl = root.querySelector('#description-editor');
  const textarea = root.querySelector('#id_description');
  if (!editorEl || !textarea || editorEl.dataset.quillBound) return;
  if (typeof Quill === 'undefined') return;
  editorEl.dataset.quillBound = 'true';

  const quill = new Quill(editorEl, {
    theme: 'snow',
    placeholder: "What's this about?",
    modules: {
      toolbar: [
        ['bold', 'italic', 'strike'],
        ['link', 'code'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['blockquote'],
        ['clean'],
      ],
    },
  });

  if (textarea.value.trim()) {
    quill.clipboard.dangerouslyPasteHTML(textarea.value);
  }

  quill.on('text-change', () => {
    textarea.value = quill.root.innerHTML;
  });

  editorEl.closest('form')?.addEventListener('submit', () => {
    textarea.value = quill.root.innerHTML;
  });
}

window.initDescriptionEditor = initDescriptionEditor;
document.addEventListener('DOMContentLoaded', () => initDescriptionEditor(document));
