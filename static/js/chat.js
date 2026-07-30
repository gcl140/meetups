// Shared chat widget: powers both the full chat room (chat/room.html) and
// the read-along snippet embedded on the event detail page. History and
// "load older" both go through the paginated REST API; the WebSocket is
// only used to push new messages/reactions live to everyone in the room.

const COMMON_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🙏', '🎉', '🔥', '👀', '🙌', '😅', '💯'];

function formatTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

function initChatWidget(root) {
  const slug = root.dataset.eventSlug;
  const currentUserId = Number(root.dataset.userId);

  const log = root.querySelector('[data-chat-log]');
  const olderBtn = root.querySelector('[data-chat-older]');
  const form = root.querySelector('[data-chat-form]');
  const input = root.querySelector('[data-chat-input]');
  const emojiBtn = root.querySelector('[data-chat-emoji-btn]');
  const emojiPanel = root.querySelector('[data-chat-emoji-panel]');
  const attachInput = root.querySelector('[data-chat-attach-input]');

  let nextPage = 1;
  let hasMore = true;
  const renderedIds = new Set();

  function reactionBar(message) {
    const bar = document.createElement('div');
    bar.className = 'flex flex-wrap items-center gap-1 mt-1';

    Object.entries(message.reactions || {}).forEach(([emoji, info]) => {
      if (info.count < 1) return;
      const pill = document.createElement('button');
      const mine = info.user_ids.includes(currentUserId);
      pill.type = 'button';
      pill.className = `text-xs rounded-full px-2 py-0.5 border ${
        mine ? 'bg-copper-500/20 border-copper-400 text-copper-700' : 'bg-wood-50 border-wood-200 text-wood-600'
      }`;
      pill.textContent = `${emoji} ${info.count}`;
      pill.addEventListener('click', () => toggleReaction(message.id, emoji));
      bar.appendChild(pill);
    });

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'text-xs text-wood-400 hover:text-copper-600 px-1';
    addBtn.innerHTML = '<i class="fa-regular fa-face-smile"></i>';
    addBtn.addEventListener('click', (e) => openReactionPicker(e, message.id));
    bar.appendChild(addBtn);

    return bar;
  }

  let openPicker = null;
  function closeReactionPicker() {
    if (openPicker) { openPicker.remove(); openPicker = null; }
  }
  function openReactionPicker(e, messageId) {
    closeReactionPicker();
    const panel = document.createElement('div');
    panel.className = 'absolute z-10 mt-1 flex flex-wrap gap-1 bg-white border border-wood-200 rounded-lg shadow-wood p-2 w-40';
    COMMON_EMOJIS.forEach((emoji) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'text-lg hover:scale-110 transition-transform';
      btn.textContent = emoji;
      btn.addEventListener('click', () => { toggleReaction(messageId, emoji); closeReactionPicker(); });
      panel.appendChild(btn);
    });
    e.target.closest('div').appendChild(panel);
    openPicker = panel;
    setTimeout(() => document.addEventListener('click', closeReactionPicker, { once: true }), 0);
  }

  async function toggleReaction(messageId, emoji) {
    try {
      await api(`/api/events/${slug}/chat/messages/${messageId}/react/`, {
        method: 'POST', body: { emoji },
      });
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function applyReactionUpdate(data) {
    const bar = log.querySelector(`[data-message-id="${data.id}"] [data-reaction-bar]`);
    if (!bar) return;
    const fresh = reactionBar({ id: data.id, reactions: data.reactions });
    fresh.setAttribute('data-reaction-bar', '');
    bar.replaceWith(fresh);
  }

  function buildBubble(message) {
    const wrap = document.createElement('div');
    wrap.dataset.messageId = message.id;
    const isMine = !message.is_bot && message.sender_id === currentUserId;
    wrap.className = `relative max-w-[85%] rounded-xl px-3 py-2 text-sm ${
      message.is_bot
        ? 'bg-copper-500/10 text-copper-700 border border-copper-400/40 self-start'
        : isMine
        ? 'bg-wood-700 text-cream-50 self-end'
        : 'bg-wood-100 text-wood-900 self-start'
    }`;

    if (!message.is_bot) {
      const sender = document.createElement('p');
      sender.className = 'text-xs font-semibold opacity-70 mb-0.5';
      sender.textContent = message.sender;
      wrap.appendChild(sender);
    }

    if (message.content) {
      const body = document.createElement('p');
      body.style.whiteSpace = 'pre-wrap';
      body.textContent = message.content;
      wrap.appendChild(body);
    }

    if (message.attachment_url) {
      if (message.is_image) {
        const img = document.createElement('img');
        img.src = message.attachment_url;
        img.className = 'mt-1 max-h-48 rounded-lg border border-black/10';
        wrap.appendChild(img);
      } else {
        const link = document.createElement('a');
        link.href = message.attachment_url;
        link.target = '_blank';
        link.className = 'mt-1 flex items-center gap-2 text-xs underline';
        link.innerHTML = `<i class="fa-regular fa-file-lines"></i> ${message.attachment_name || 'Attachment'}`;
        wrap.appendChild(link);
      }
    }

    const time = document.createElement('p');
    time.className = 'text-[10px] opacity-50 mt-0.5';
    time.textContent = formatTime(message.created_at);
    wrap.appendChild(time);

    if (!message.is_bot) {
      const bar = reactionBar(message);
      bar.setAttribute('data-reaction-bar', '');
      wrap.appendChild(bar);
    }

    return wrap;
  }

  function appendLive(message) {
    log.appendChild(buildBubble(message));
    renderedIds.add(message.id);
    log.scrollTop = log.scrollHeight;
  }

  function prependHistory(messages) {
    const frag = document.createDocumentFragment();
    const previousHeight = log.scrollHeight;
    messages.forEach((m) => {
      if (renderedIds.has(m.id)) return;
      renderedIds.add(m.id);
      frag.appendChild(buildBubble(m));
    });
    log.prepend(frag);
    log.scrollTop = log.scrollHeight - previousHeight;
  }

  function appendHistory(messages) {
    messages.forEach((m) => {
      if (renderedIds.has(m.id)) return;
      renderedIds.add(m.id);
      log.appendChild(buildBubble(m));
    });
    log.scrollTop = log.scrollHeight;
  }

  async function loadPage(page) {
    const data = await api(`/api/events/${slug}/chat/messages/?page=${page}`);
    hasMore = Boolean(data.next);
    nextPage = page + 1;
    if (olderBtn) olderBtn.classList.toggle('hidden', !hasMore);
    return data.results.slice().reverse();
  }

  async function loadInitial() {
    try {
      const messages = await loadPage(1);
      appendHistory(messages);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  if (olderBtn) {
    olderBtn.addEventListener('click', async () => {
      olderBtn.disabled = true;
      olderBtn.textContent = 'Loading…';
      try {
        const messages = await loadPage(nextPage);
        prependHistory(messages);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        olderBtn.disabled = false;
        olderBtn.textContent = 'Load older messages';
      }
    });
  }

  // ---- Emoji picker for composing ----
  if (emojiBtn && emojiPanel) {
    COMMON_EMOJIS.forEach((emoji) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'text-lg hover:scale-110 transition-transform';
      btn.textContent = emoji;
      btn.addEventListener('click', () => {
        input.value += emoji;
        input.focus();
        emojiPanel.classList.add('hidden');
      });
      emojiPanel.appendChild(btn);
    });
    emojiBtn.addEventListener('click', () => emojiPanel.classList.toggle('hidden'));
  }

  // ---- Attachments ----
  if (attachInput) {
    attachInput.addEventListener('change', async () => {
      const file = attachInput.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      try {
        await api(`/api/events/${slug}/chat/attachments/`, { method: 'POST', body: formData, isFormData: true });
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        attachInput.value = '';
      }
    });
  }

  // ---- WebSocket: live delivery only ----
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws/chat/${slug}/`);

  socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'message') {
      if (!renderedIds.has(data.id)) appendLive(data);
    } else if (data.type === 'reaction_update') {
      applyReactionUpdate(data);
    }
  });

  socket.addEventListener('close', () => {
    if (form) showToast('Chat disconnected. Refresh to reconnect.', 'error');
  });

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      socket.send(JSON.stringify({ message: text }));
      input.value = '';
      emojiPanel?.classList.add('hidden');
    });
  }

  loadInitial();
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-chat-widget]').forEach(initChatWidget);
});
