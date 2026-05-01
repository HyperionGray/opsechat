async function processLegacyMessage(message) {
  if (window.PGPManager && PGPManager.isPGPMessage(message)) {
    return PGPManager.decryptMessage(message);
  }
  return message;
}

function updateLegacyPGPStatus() {
  const indicator = document.getElementById('pgp-status-indicator');
  const privateStatus = document.getElementById('private-key-status');
  const publicStatus = document.getElementById('public-keys-status');
  const publicList = document.getElementById('public-keys-list');

  if (!window.PGPManager || !indicator) {
    return;
  }

  let status = '';
  if (PGPManager.canDecrypt()) {
    status += '🔓 Can decrypt | ';
  }
  if (PGPManager.canEncrypt()) {
    status += '🔒 Will encrypt';
  }
  if (!status) {
    status = '❌ PGP not configured';
  }
  indicator.textContent = status;

  if (privateStatus) {
    privateStatus.textContent = PGPManager.canDecrypt() ? '✓ Private key imported' : 'No private key';
  }
  if (publicStatus && publicList) {
    const keys = Object.keys(PGPManager.getPublicKeys());
    publicStatus.textContent = keys.length > 0 ? `✓ ${keys.length} public key(s) imported` : 'No public keys';
    publicList.innerHTML = keys.length > 0 ? `<b>Public keys:</b><br>${keys.join('<br>')}` : '';
  }
}

async function pollLegacyChat(path) {
  const response = await fetch(`/${path}/chatsjs`);
  if (!response.ok) {
    throw new Error('Failed to load chat messages');
  }

  const chatLines = await response.json();
  const container = document.getElementById('chatf');
  const peopleCount = document.getElementById('numpeeps');
  if (!container) {
    return;
  }

  container.innerHTML = '';
  for (const line of chatLines) {
    const row = document.createElement('div');
    const rendered = await processLegacyMessage(line.msg);
    const lockIcon = window.PGPManager && PGPManager.isPGPMessage(line.msg) ? '🔒 ' : '';
    row.className = 'legacy-chat-line';
    row.textContent = `${lockIcon}${line.username}: ${rendered}`;
    if (line.color) {
      row.style.color = `rgb(${line.color})`;
    }
    container.appendChild(row);
    if (peopleCount && line.num_people !== undefined) {
      peopleCount.textContent = line.num_people;
    }
  }
}

async function sendLegacyChatMessage(path) {
  const input = document.getElementById('messagearea');
  if (!input) {
    return;
  }
  let message = input.value.trim();
  if (!message) {
    return;
  }

  if (window.PGPManager && PGPManager.canEncrypt()) {
    message = await PGPManager.encryptMessage(message);
  }

  const response = await fetch(`/${path}/chatsjs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ message }),
  });

  if (response.ok) {
    input.value = '';
    await pollLegacyChat(path);
  }
}

function setupLegacyPgpModal() {
  const modal = document.getElementById('pgp-modal');
  const openLink = document.getElementById('pgp-settings-link');
  const closeButton = document.querySelector('.pgp-close');

  if (!modal || !openLink || !closeButton || !window.PGPManager || !window.openpgp) {
    return;
  }

  openLink.addEventListener('click', (event) => {
    event.preventDefault();
    modal.style.display = 'block';
    updateLegacyPGPStatus();
  });

  closeButton.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  window.addEventListener('click', (event) => {
    if (event.target === modal) {
      modal.style.display = 'none';
    }
  });

  document.getElementById('import-private-key-btn')?.addEventListener('click', async () => {
    const key = document.getElementById('private-key-input')?.value.trim();
    const passphrase = document.getElementById('passphrase-input')?.value || '';
    if (!key) {
      alert('Please enter a private key');
      return;
    }

    try {
      const privateKey = await openpgp.readPrivateKey({ armoredKey: key });
      if (passphrase) {
        await openpgp.decryptKey({ privateKey, passphrase });
        PGPManager.setPassphrase(passphrase);
      }
      PGPManager.setPrivateKey(key);
      document.getElementById('private-key-input').value = '';
      document.getElementById('passphrase-input').value = '';
      updateLegacyPGPStatus();
      alert('Private key imported successfully');
    } catch (error) {
      alert(`Error importing private key: ${error.message}`);
    }
  });

  document.getElementById('clear-private-key-btn')?.addEventListener('click', () => {
    if (window.confirm('Are you sure you want to remove your private key?')) {
      PGPManager.clearPrivateKey();
      updateLegacyPGPStatus();
    }
  });

  document.getElementById('add-public-key-btn')?.addEventListener('click', async () => {
    const key = document.getElementById('public-key-input')?.value.trim();
    const usernameField = document.getElementById('username-input');
    const username = usernameField?.value.trim() || `user-${Date.now()}`;

    if (!key) {
      alert('Please enter a public key');
      return;
    }

    try {
      await openpgp.readKey({ armoredKey: key });
      PGPManager.addPublicKey(username, key);
      document.getElementById('public-key-input').value = '';
      if (usernameField) {
        usernameField.value = '';
      }
      updateLegacyPGPStatus();
      alert(`Public key added for: ${username}`);
    } catch (error) {
      alert(`Error adding public key: ${error.message}`);
    }
  });

  document.getElementById('clear-public-keys-btn')?.addEventListener('click', () => {
    if (window.confirm('Are you sure you want to remove all public keys?')) {
      PGPManager.clearAllPublicKeys();
      updateLegacyPGPStatus();
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const path = document.body.dataset.path;
  const scriptEnabled = document.body.dataset.scriptEnabled === 'true';
  if (!scriptEnabled || !path) {
    return;
  }

  setupLegacyPgpModal();
  updateLegacyPGPStatus();
  await pollLegacyChat(path);
  setInterval(() => {
    pollLegacyChat(path).catch(() => {});
  }, 3000);

  const input = document.getElementById('messagearea');
  input?.addEventListener('keypress', async (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      await sendLegacyChatMessage(path);
    }
  });
});
