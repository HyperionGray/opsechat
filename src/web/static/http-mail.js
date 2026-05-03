function showMailSection(name) {
  ['create', 'compose', 'read'].forEach((section) => {
    const element = document.getElementById(`${section}-section`);
    if (element) {
      element.style.display = section === name ? 'block' : 'none';
    }
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

function toBase64(bytes) {
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

function fromBase64(value) {
  const binary = window.atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function deriveMessageKey(passphrase, saltBytes) {
  const encoder = new TextEncoder();
  const baseKey = await window.crypto.subtle.importKey(
    'raw',
    encoder.encode(passphrase),
    'PBKDF2',
    false,
    ['deriveKey'],
  );

  return window.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      hash: 'SHA-256',
      salt: saltBytes,
      iterations: 120000,
    },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

async function encryptText(passphrase, saltBytes, plaintext) {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveMessageKey(passphrase, saltBytes);
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    encoded,
  );

  return {
    iv: toBase64(iv),
    ciphertext: toBase64(new Uint8Array(ciphertext)),
  };
}

async function decryptText(passphrase, saltBytes, payload) {
  const iv = fromBase64(payload.iv);
  const ciphertext = fromBase64(payload.ciphertext);
  const key = await deriveMessageKey(passphrase, saltBytes);
  const plaintext = await window.crypto.subtle.decrypt(
    { name: 'AES-GCM', iv },
    key,
    ciphertext,
  );
  return new TextDecoder().decode(plaintext);
}

async function buildEncryptedPayload() {
  if (!window.crypto?.subtle) {
    throw new Error('This browser does not support Web Crypto encryption.');
  }

  const address = document.getElementById('compose-address-input')?.value.trim();
  const inboxKey = document.getElementById('compose-key')?.value.trim();
  const sender = document.getElementById('compose-sender')?.value.trim() || 'anonymous';
  const subject = document.getElementById('compose-subject')?.value.trim() || '(no subject)';
  const body = document.getElementById('compose-body')?.value.trim();
  const maxMessageLength = Number(document.body.dataset.maxMessageLength || '2000');

  if (!address) {
    throw new Error('Recipient inbox username is required.');
  }
  if (!inboxKey) {
    throw new Error('Recipient inbox key is required for browser-side encryption.');
  }
  if (!body) {
    throw new Error('Message body is required.');
  }
  if (body.length > maxMessageLength) {
    throw new Error(`Message body exceeds ${maxMessageLength} characters.`);
  }

  const salt = window.crypto.getRandomValues(new Uint8Array(16));
  const payload = {
    version: 'shared-secret-v1',
    salt: toBase64(salt),
    sender: await encryptText(inboxKey, salt, sender),
    subject: await encryptText(inboxKey, salt, subject),
    body: await encryptText(inboxKey, salt, body),
  };

  return {
    address,
    ciphertext: JSON.stringify(payload),
  };
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
    document.getElementById('read-address').value = data.address;
    document.getElementById('read-key-input').value = data.read_key;
  } catch (error) {
    window.alert(`Request failed: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = 'Create Another Inbox';
  }
}

function updateComposeAction(path) {
  const address = document.getElementById('compose-address-input')?.value.trim();
  const form = document.getElementById('compose-form');
  if (address && form) {
    form.action = `/${path}/mail/${encodeURIComponent(address)}/send`;
  }
}

async function submitComposeForm(path, event) {
  event.preventDefault();
  updateComposeAction(path);

  const form = document.getElementById('compose-form');
  const submitButton = form?.querySelector('button[type="submit"]');
  if (!form || !submitButton) {
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = 'Encrypting...';

  try {
    const encrypted = await buildEncryptedPayload();
    document.getElementById('compose-ciphertext').value = encrypted.ciphertext;

    const response = await fetch(form.action, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ ciphertext: encrypted.ciphertext }),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || 'Could not send message');
    }

    const status = document.getElementById('js-compose-status');
    if (status) {
      status.innerHTML = '<div class="success-box">✅ Message encrypted in-browser and sent.</div>';
    }
    const keptAddress = document.getElementById('compose-address-input')?.value || '';
    const keptKey = document.getElementById('compose-key')?.value || '';
    form.reset();
    document.getElementById('compose-address-input').value = keptAddress;
    document.getElementById('compose-key').value = keptKey;
  } catch (error) {
    window.alert(error.message);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Encrypt & Send';
  }
}

async function decryptInboxMessage(message, inboxKey) {
  if (!message.encrypted || !message.ciphertext) {
    return {
      sender: message.sender,
      subject: message.subject,
      body: message.body,
      decrypted: true,
    };
  }

  try {
    const payload = JSON.parse(message.ciphertext);
    if (payload.version !== 'shared-secret-v1') {
      throw new Error('Unsupported cipher payload');
    }

    const saltBytes = fromBase64(payload.salt);
    return {
      sender: await decryptText(inboxKey, saltBytes, payload.sender),
      subject: await decryptText(inboxKey, saltBytes, payload.subject),
      body: await decryptText(inboxKey, saltBytes, payload.body),
      decrypted: true,
    };
  } catch (error) {
    return {
      sender: message.sender,
      subject: message.subject,
      body: 'Unable to decrypt with the provided inbox key. Ciphertext is still stored safely.',
      decrypted: false,
      ciphertext: message.ciphertext,
    };
  }
}

function renderInbox(messages, address, readKey, path) {
  const container = document.getElementById('js-inbox-messages');
  if (!container) {
    return;
  }

  if (messages.length === 0) {
    container.innerHTML = '<p style="color:#888;margin-top:10px;">No messages in this inbox.</p>';
    return;
  }

  Promise.all(messages.map((message) => decryptInboxMessage(message, readKey)))
    .then((decryptedMessages) => {
      let html = `<h3 style="margin-top:20px;">Messages (${decryptedMessages.length})</h3>`;
      decryptedMessages.forEach((message, index) => {
        const original = messages[index];
        const ciphertextDetails = !message.decrypted && message.ciphertext
          ? `<details style="margin-top:10px;"><summary style="cursor:pointer;color:#888;">Show ciphertext</summary><div class="token-box">${escapeHtml(message.ciphertext)}</div></details>`
          : '';

        html += `
          <div class="msg-card">
            <div class="msg-meta">From: ${escapeHtml(message.sender)} &nbsp;|&nbsp; ${escapeHtml(original.timestamp)}</div>
            <div class="msg-subject">${escapeHtml(message.subject)}</div>
            <div class="msg-body">${escapeHtml(message.body)}</div>
            ${ciphertextDetails}
            <div class="msg-actions">
              <button class="danger js-delete-msg"
                      data-address="${escapeHtml(address)}"
                      data-msg-id="${escapeHtml(original.id)}"
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
          if (!window.confirm('Destroy inbox and ALL messages permanently?')) {
            return;
          }
          destroyMailbox(path, button.dataset.address, button.dataset.readKey);
        });
      });
    })
    .catch((error) => {
      container.innerHTML = `<div class="error-box">⚠️ ${escapeHtml(error.message)}</div>`;
    });
}

async function fetchInbox(path) {
  const address = document.getElementById('read-address')?.value.trim();
  const readKey = document.getElementById('read-key-input')?.value.trim();

  if (!address) {
    window.alert('Please enter your inbox username.');
    return;
  }
  if (!readKey) {
    window.alert('Please enter your inbox key.');
    return;
  }

  try {
    const response = await fetch(`/${path}/mail/${encodeURIComponent(address)}/inbox`, {
      headers: { Accept: 'application/json' },
    });
    if (response.status === 404) {
      throw new Error('Inbox not found');
    }

    const data = await response.json();
    renderInbox(data.messages, address, readKey, path);
    showMailSection('read');
    if (window.history?.replaceState) {
      window.history.replaceState({}, document.title, `/${path}/mail/${encodeURIComponent(address)}/inbox`);
    }
  } catch (error) {
    document.getElementById('js-inbox-messages').innerHTML =
      `<div class="error-box">⚠️ ${escapeHtml(error.message)}</div>`;
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
    window.alert(`Error: ${data.error || 'Could not delete'}`);
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
      '<div class="success-box">✅ Inbox destroyed.</div>';
  } else {
    window.alert(`Error: ${data.error || 'Could not destroy inbox'}`);
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
  document.getElementById('read-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    fetchInbox(path);
  });
  document.getElementById('compose-form')?.addEventListener('submit', (event) => submitComposeForm(path, event));
  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) {
        return;
      }
      const text = target.textContent || '';
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => window.alert('Copied!'));
      }
    });
  });
});
