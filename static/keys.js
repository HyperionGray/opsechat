const keyStatusEl = document.getElementById("keyStatus");
const exportOutputEl = document.getElementById("exportOutput");
const importInputEl = document.getElementById("importKeyInput");

function formatStatus(payload) {
  if (!payload || !payload.has_key) {
    return "No key is currently loaded for this session.";
  }

  return [
    "Key loaded",
    `key_id: ${payload.key_id}`,
    `fingerprint: ${payload.fingerprint}`,
    `source: ${payload.source}`,
    `created_at: ${payload.created_at}`,
    `algorithm: ${payload.algorithm}`,
    `key_bytes: ${payload.key_bytes}`,
  ].join("\n");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorText = payload.error || `Request failed (${response.status})`;
    throw new Error(errorText);
  }

  return payload;
}

async function refreshStatus() {
  try {
    const payload = await requestJson("/api/keys/status");
    keyStatusEl.textContent = formatStatus(payload);
  } catch (error) {
    keyStatusEl.textContent = `Error loading status: ${error.message}`;
  }
}

async function generateKey() {
  try {
    const payload = await requestJson("/api/keys/generate", { method: "POST" });
    keyStatusEl.textContent = formatStatus(payload);
    exportOutputEl.textContent = "New key generated.";
  } catch (error) {
    exportOutputEl.textContent = `Generate failed: ${error.message}`;
  }
}

async function importKey() {
  const key = importInputEl.value.trim();
  if (!key) {
    exportOutputEl.textContent = "Provide a base64 key before importing.";
    return;
  }

  try {
    const payload = await requestJson("/api/keys/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    keyStatusEl.textContent = formatStatus(payload);
    exportOutputEl.textContent = "Key imported successfully.";
  } catch (error) {
    exportOutputEl.textContent = `Import failed: ${error.message}`;
  }
}

async function exportKey() {
  try {
    const payload = await requestJson("/api/keys/export");
    exportOutputEl.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    exportOutputEl.textContent = `Export failed: ${error.message}`;
  }
}

async function deleteKey() {
  try {
    await requestJson("/api/keys", { method: "DELETE" });
    exportOutputEl.textContent = "Key deleted.";
    await refreshStatus();
  } catch (error) {
    exportOutputEl.textContent = `Delete failed: ${error.message}`;
  }
}

document.getElementById("generateKeyBtn").addEventListener("click", generateKey);
document.getElementById("importKeyBtn").addEventListener("click", importKey);
document.getElementById("exportKeyBtn").addEventListener("click", exportKey);
document.getElementById("deleteKeyBtn").addEventListener("click", deleteKey);

refreshStatus();
