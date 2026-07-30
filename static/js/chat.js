// Event chat room over a Channels WebSocket. Plain messages broadcast to
// everyone in the room; messages starting with "/" are handled by the
// rule-based bot (see chat/bot.py) which replies in the same room.

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('chat-root');
  if (!root) return;

  const slug = root.dataset.eventSlug;
  const currentUserName = root.dataset.userName;
  const log = document.getElementById('chat-log');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');

  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws/chat/${slug}/`);

  function appendMessage(msg) {
    const row = document.createElement('div');
    const isMine = !msg.is_bot && msg.sender === currentUserName;
    row.className = `max-w-[80%] rounded-xl px-3 py-2 text-sm ${
      msg.is_bot
        ? 'bg-copper-500/10 text-copper-700 border border-copper-400/40 self-start'
        : isMine
        ? 'bg-wood-700 text-cream-50 self-end'
        : 'bg-wood-100 text-wood-900 self-start'
    }`;

    if (!msg.is_bot) {
      const sender = document.createElement('p');
      sender.className = 'text-xs font-semibold opacity-70 mb-0.5';
      sender.textContent = msg.sender;
      row.appendChild(sender);
    }

    const body = document.createElement('p');
    body.style.whiteSpace = 'pre-wrap';
    body.textContent = msg.content;
    row.appendChild(body);

    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'history') {
      data.messages.forEach(appendMessage);
    } else if (data.type === 'message') {
      appendMessage(data);
    }
  });

  socket.addEventListener('close', () => {
    showToast('Chat disconnected. Refresh to reconnect.', 'error');
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    socket.send(JSON.stringify({ message: text }));
    input.value = '';
  });
});
