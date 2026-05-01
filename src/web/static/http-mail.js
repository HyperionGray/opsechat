function showMailSection(name) {
  ['create', 'compose', 'read'].forEach((section) => {
    const element = document.getElementById(`${section}-section`);
    if (element) {
      element.style.display = section === name ? 'block' : 'none';
    }
  });
}

function copyText(elementId) {
  const text = document.getElementById(elementId)?.textContent || '';
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      alert('Copied!');
    });
    return;
  }

  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.left = '-9999px';
  document.body.appendChild(textArea);
  textArea.select();
  try {
    document.execCommand('copy');
    alert('Copied!');
  } finally {
    document.body.removeChild(textArea);
  }
}

function renderInbox(messages, address, readKey, path) {
  const container = document.getElementById('js-inbox-messages');
  if (!container) {
    return;
  }

  if (messages.length === 0) {
    container.innerHTML = '<p style="color:#888;margin-top:10px;">No messages in this mailbox.</p>';
    return;
  }

  let html = `<h3 style="margin-top:20px;">Messages (${messages.length})</h3>`;
  messages.forEach((msg) => {
    html += `
      <div class="msg-card">
        <div class="msg-meta">From: ${escapeHtml(msg.sender)} &nbsp;|&nbsp; ${escapeHtml(msg.timestamp)}</div>
        <div class="msg-subject">${escapeHtml(msg.subject)}</div>
        <div class="msg-body">${escapeHtml(msg.body)}</div>
        <div class="msg-actions">
          <button class="danger js-delete-msg"
                  data-address="${escapeHtml(address)}"
                  data-msg-id="${escapeHtml(msg.id)}"
                  data-read-key="${escapeHtml(readKey)}">🗑 Delete</button>
        </div>
      </div>
    `;
  });

  html += `
    <div style="margin-top:30px;border-top:1px solid #333;padding-top:15px;">
      <h3 style="color:#f00;">Danger Zone</h3>
      <button class="danger js-destroy-mailbox"
              data-address="${escapeHtml(address)}"
              data-read-key="${escapeHtml(readKey)}">💣 Destroy Mailbox</button>
    </div>
  `;

  container.innerHTML = html;

  container.querySelectorAll('.js-delete-msg').forEach((button) => {
    button.addEventListener('click', () => {
      if (!window.confirm('Delete this message?')) {
        return;
      }
      deleteMessage(path, button.dataset.address, button.dataset.msgId, button.dataset.readKey);
    });
  });

  container.querySelectorAll('.js-destroy-mailbox').forEach((button) => {
    button.addEventListener('click', () => {
      if (!window.confirm('Destroy mailbox and ALL messages permanently?')) {
        return;
      }
      destroyMailbox(path, button.dataset.address, button.dataset.readKey);
    });
  });
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function createMailbox(path) {
  const button = document.getElementById('create-btn');
  if (!button) {
    return;
  }
  button.disabled = true;
  button.textContent = 'Creating...';

  try {
    const response = await fetch(`/${path}/mail/new`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    });
    const data = await response.json();
    if (!data.success) {
      throw new Error(data.error || 'Unknown error');
    }

    document.getElementById('result-address').textContent = data.address;
    document.getElementById('result-read-key').textContent = data.read_key;
    document.getElementById('result-send-url').textContent = `${window.location.origin}${data.send_url}`;
    document.getElementById('new-mailbox-result').style.display = 'block';
  } catch (error) {
    alert(`Request failed: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = 'Create Another Mailbox';
  }
}

function updateComposeAction(path) {
  const address = document.getElementById('compose-address-input')?.value.trim();
  const form = document.getElementById('compose-form');
  if (address && form) {
    form.action = `/${path}/mail/${encodeURIComponent(address)}/send`;
  }
}

async function fetchInbox(path) {
  const address = document.getElementById('read-address')?.value.trim();
  const readKey = document.getElementById('read-key-input')?.value.trim();

  if (!address || !readKey) {
    alert('Please enter both mailbox address and read key.');
    return;
  }

  try {
    const response = await fetch(`/${path}/mail/${encodeURIComponent(address)}/inbox?key=${encodeURIComponent(readKey)}`, {
      headers: { Accept: 'application/json' },
    });
    if (response.status === 403) {
      throw new Error('Invalid read key — access denied');
    }
    if (response.status === 404) {
      throw new Error('Mailbox not found');
    }

    const data = await response.json();
    renderInbox(data.messages, address, readKey, path);
  } catch (error) {
    document.getElementById('js-inbox-messages').innerHTML =
      `<div class="error-box">⚠️ ${error.message}</div>`;
  }
}

async function deleteMessage(path, address, msgId, readKey) {
  const response = await fetch(`/${path}/mail/${encodeURIComponent(address)}/delete/${encodeURIComponent(msgId)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ read_key: readKey }),
  });
  const data = await response.json();
  if (data.success) {
    fetchInbox(path);
  } else {
    alert(`Error: ${data.error || 'Could not delete'}`);
  }
}

async function destroyMailbox(path, address, readKey) {
  const response = await fetch(`/${path}/mail/${encodeURIComponent(address)}/destroy`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ read_key: readKey }),
  });
  const data = await response.json();
  if (data.success) {
    document.getElementById('js-inbox-messages').innerHTML =
      '<div class="success-box">✅ Mailbox destroyed.</div>';
  } else {
    alert(`Error: ${data.error || 'Could not destroy mailbox'}`);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const path = document.body.dataset.path;
  const initialSection = document.body.dataset.initialSection || 'create';

  showMailSection(initialSection);

  document.querySelectorAll('[data-mail-section]').forEach((button) => {
    button.addEventListener('click', () => showMailSection(button.dataset.mailSection));
  });

  document.getElementById('create-btn')?.addEventListener('click', () => createMailbox(path));
  document.getElementById('compose-address-input')?.addEventListener('input', () => updateComposeAction(path));
  document.getElementById('open-inbox-btn')?.addEventListener('click', () => fetchInbox(path));
  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', () => copyText(button.dataset.copyTarget));
  });
});
