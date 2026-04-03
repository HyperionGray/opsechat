const STORAGE_KEYS = {
  privateKey: "opsechat_private_key",
  publicKey: "opsechat_public_key",
};

function byId(id) {
  return document.getElementById(id);
}

function setStatus(message, isError = false) {
  const status = byId("statusMsg");
  status.textContent = message;
  status.classList.toggle("is-error", Boolean(isError));
  status.classList.toggle("is-ok", !isError);
}

function saveKeys(privateKey, publicKey) {
  localStorage.setItem(STORAGE_KEYS.privateKey, privateKey);
  localStorage.setItem(STORAGE_KEYS.publicKey, publicKey);
}

function loadKeys() {
  return {
    privateKey: localStorage.getItem(STORAGE_KEYS.privateKey),
    publicKey: localStorage.getItem(STORAGE_KEYS.publicKey),
  };
}

function clearKeys() {
  localStorage.removeItem(STORAGE_KEYS.privateKey);
  localStorage.removeItem(STORAGE_KEYS.publicKey);
}

function updateKeyStatusUI() {
  const keys = loadKeys();
  byId("hasPrivateKey").textContent = keys.privateKey
    ? "Private key: loaded"
    : "Private key: not loaded";
  byId("hasPublicKey").textContent = keys.publicKey
    ? "Public key: loaded"
    : "Public key: not loaded";
  byId("publicKeyPreview").value = keys.publicKey || "";
}

function downloadTextFile(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

function validateArmoredKey(text, expectedMarker) {
  if (!text || typeof text !== "string") {
    return false;
  }
  return text.includes(expectedMarker);
}

async function generateNewKeyPair() {
  const pair = await window.openpgp.generateKey({
    type: "ecc",
    curve: "ed25519",
    userIDs: [{ name: "OpSecChat User" }],
    format: "armored",
  });
  saveKeys(pair.privateKey, pair.publicKey);
  updateKeyStatusUI();
  setStatus("New key pair generated in browser storage.");
}

function importKey(kind) {
  const fileInput = byId("hiddenFileInput");
  fileInput.value = "";

  fileInput.onchange = async function onFileSelect() {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      return;
    }

    try {
      const text = await file.text();
      const marker = kind === "private" ? "BEGIN PGP PRIVATE KEY BLOCK" : "BEGIN PGP PUBLIC KEY BLOCK";
      if (!validateArmoredKey(text, marker)) {
        setStatus("Invalid key format for selected import type.", true);
        return;
      }

      const keys = loadKeys();
      if (kind === "private") {
        localStorage.setItem(STORAGE_KEYS.privateKey, text.trim());
      } else {
        localStorage.setItem(STORAGE_KEYS.publicKey, text.trim());
      }
      // keep counterpart untouched
      if (keys.privateKey && kind !== "private") {
        localStorage.setItem(STORAGE_KEYS.privateKey, keys.privateKey);
      }
      if (keys.publicKey && kind !== "public") {
        localStorage.setItem(STORAGE_KEYS.publicKey, keys.publicKey);
      }

      updateKeyStatusUI();
      setStatus(`${kind === "private" ? "Private" : "Public"} key imported.`);
    } catch (error) {
      setStatus(`Failed to import key: ${error.message}`, true);
    }
  };

  fileInput.click();
}

function exportKey(kind) {
  const keys = loadKeys();
  const keyText = kind === "private" ? keys.privateKey : keys.publicKey;
  if (!keyText) {
    setStatus(`No ${kind} key available to export.`, true);
    return;
  }

  const filename = kind === "private" ? "opsechat-private-key.asc" : "opsechat-public-key.asc";
  downloadTextFile(filename, keyText);
  setStatus(`${kind === "private" ? "Private" : "Public"} key exported.`);
}

function deleteLocalKeys() {
  const confirmed = window.confirm("Delete local keys from this browser?");
  if (!confirmed) {
    return;
  }
  clearKeys();
  updateKeyStatusUI();
  setStatus("Local keys deleted from browser storage.");
}

function initializeKeysPage() {
  if (!window.openpgp || typeof window.openpgp.generateKey !== "function") {
    setStatus("openpgp library is unavailable.", true);
    return;
  }

  byId("generateKeyBtn").addEventListener("click", function onGenerate() {
    generateNewKeyPair().catch((error) => {
      setStatus(`Key generation failed: ${error.message}`, true);
    });
  });

  byId("importPrivateBtn").addEventListener("click", function onImportPrivate() {
    importKey("private");
  });
  byId("importPublicBtn").addEventListener("click", function onImportPublic() {
    importKey("public");
  });
  byId("exportPrivateBtn").addEventListener("click", function onExportPrivate() {
    exportKey("private");
  });
  byId("exportPublicBtn").addEventListener("click", function onExportPublic() {
    exportKey("public");
  });
  byId("deleteKeysBtn").addEventListener("click", deleteLocalKeys);

  updateKeyStatusUI();
  setStatus("Ready. Keys stay in your browser unless you export them.");
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeKeysPage);
} else {
  initializeKeysPage();
}
