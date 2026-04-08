function byId(id) {
    return document.getElementById(id);
}

function setElementStatus(id, message, isError) {
    const el = byId(id);
    if (!el) {
        return;
    }
    el.className = isError ? "status status-error" : "status status-ok";
    el.textContent = message;
}

function setGlobalStatus(message, isError) {
    setElementStatus("globalStatus", message, !!isError);
}

function sanitizeLabel(value) {
    const trimmed = value.trim();
    if (!trimmed) {
        return "";
    }
    return trimmed.slice(0, 200);
}

function triggerDownload(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
}

async function generateKeyPair(event) {
    event.preventDefault();

    const nameValue = byId("nameInput").value.trim();
    const emailValue = byId("emailInput").value.trim();
    const passphraseValue = byId("generatePassphraseInput").value;

    if (!nameValue || !emailValue) {
        setGlobalStatus("Name and email are required.", true);
        return;
    }

    setGlobalStatus("Generating key pair. This may take a few seconds.", false);

    try {
        const generated = await openpgp.generateKey({
            type: "ecc",
            curve: "curve25519",
            userIDs: [{ name: nameValue, email: emailValue }],
            format: "armored",
            passphrase: passphraseValue || undefined
        });

        const selfLabel = sanitizeLabel(emailValue) || "self";
        PGPManager.setPrivateKey(generated.privateKey);
        PGPManager.setPassphrase(passphraseValue || "");
        PGPManager.addPublicKey(selfLabel, generated.publicKey);

        byId("generatedPublicKey").value = generated.publicKey;
        byId("generatedPrivateKey").value = generated.privateKey;
        byId("privateKeyInput").value = generated.privateKey;
        byId("privatePassphraseInput").value = passphraseValue;

        updatePrivateStatus();
        renderPublicKeys();
        setGlobalStatus("New key pair generated and saved to local browser storage.", false);
    } catch (error) {
        setGlobalStatus(`Key generation failed: ${error.message}`, true);
    }
}

async function importPrivateKey() {
    const armored = byId("privateKeyInput").value.trim();
    const passphraseValue = byId("privatePassphraseInput").value;

    if (!armored) {
        setGlobalStatus("Paste a private key first.", true);
        return;
    }

    try {
        const privateKey = await openpgp.readPrivateKey({ armoredKey: armored });
        if (passphraseValue) {
            await openpgp.decryptKey({
                privateKey: privateKey,
                passphrase: passphraseValue
            });
        }
        PGPManager.setPrivateKey(armored);
        PGPManager.setPassphrase(passphraseValue || "");
        updatePrivateStatus();
        setGlobalStatus("Private key imported.", false);
    } catch (error) {
        setGlobalStatus(`Private key import failed: ${error.message}`, true);
    }
}

function exportPrivateKey() {
    const key = PGPManager.getPrivateKey();
    if (!key) {
        setGlobalStatus("No private key to export.", true);
        return;
    }
    triggerDownload(`opsechat-private-key-${Date.now()}.asc`, key, "text/plain");
    setGlobalStatus("Private key exported.", false);
}

function clearPrivateKey() {
    if (!window.confirm("Delete private key from this browser?")) {
        return;
    }
    PGPManager.clearPrivateKey();
    byId("privateKeyInput").value = "";
    byId("privatePassphraseInput").value = "";
    updatePrivateStatus();
    setGlobalStatus("Private key deleted from browser storage.", false);
}

async function importPublicKey() {
    const armored = byId("publicKeyInput").value.trim();
    const rawLabel = byId("publicLabelInput").value;
    const label = sanitizeLabel(rawLabel) || `key-${Date.now()}`;

    if (!armored) {
        setGlobalStatus("Paste a public key first.", true);
        return;
    }

    try {
        await openpgp.readKey({ armoredKey: armored });
        PGPManager.addPublicKey(label, armored);
        byId("publicLabelInput").value = "";
        byId("publicKeyInput").value = "";
        renderPublicKeys();
        setGlobalStatus(`Public key stored as '${label}'.`, false);
    } catch (error) {
        setGlobalStatus(`Public key import failed: ${error.message}`, true);
    }
}

function exportPublicKeys() {
    const keys = PGPManager.getPublicKeys();
    const labels = Object.keys(keys);
    if (labels.length === 0) {
        setGlobalStatus("No public keys to export.", true);
        return;
    }
    const payload = {
        exported_at: new Date().toISOString(),
        public_keys: keys
    };
    triggerDownload(
        `opsechat-public-keys-${Date.now()}.json`,
        JSON.stringify(payload, null, 2),
        "application/json"
    );
    setGlobalStatus("Public keys exported.", false);
}

function clearPublicKeys() {
    if (!window.confirm("Delete all public keys from this browser?")) {
        return;
    }
    PGPManager.clearAllPublicKeys();
    renderPublicKeys();
    setGlobalStatus("All public keys deleted from browser storage.", false);
}

function removePublicKey(label) {
    PGPManager.removePublicKey(label);
    renderPublicKeys();
    setGlobalStatus(`Removed '${label}'.`, false);
}

function updatePrivateStatus() {
    const privateKey = PGPManager.getPrivateKey();
    if (privateKey) {
        setElementStatus("privateStatus", "Private key is configured.", false);
    } else {
        setElementStatus("privateStatus", "No private key imported.", false);
    }
}

function renderPublicKeys() {
    const container = byId("publicKeyList");
    const publicKeys = PGPManager.getPublicKeys();
    const labels = Object.keys(publicKeys).sort();

    container.innerHTML = "";
    if (labels.length === 0) {
        setElementStatus("publicStatus", "No public keys imported.", false);
        return;
    }

    setElementStatus("publicStatus", `${labels.length} public key(s) imported.`, false);

    const table = document.createElement("table");
    const headerRow = document.createElement("tr");

    ["Label", "Action"].forEach((columnName) => {
        const th = document.createElement("th");
        th.textContent = columnName;
        headerRow.appendChild(th);
    });
    table.appendChild(headerRow);

    labels.forEach((label) => {
        const row = document.createElement("tr");

        const labelCell = document.createElement("td");
        labelCell.textContent = label;
        row.appendChild(labelCell);

        const actionCell = document.createElement("td");
        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "danger";
        removeButton.textContent = "Delete";
        removeButton.addEventListener("click", () => removePublicKey(label));
        actionCell.appendChild(removeButton);
        row.appendChild(actionCell);

        table.appendChild(row);
    });

    container.appendChild(table);
}

function bindHandlers() {
    byId("generateForm").addEventListener("submit", generateKeyPair);
    byId("importPrivateBtn").addEventListener("click", importPrivateKey);
    byId("exportPrivateBtn").addEventListener("click", exportPrivateKey);
    byId("clearPrivateBtn").addEventListener("click", clearPrivateKey);
    byId("importPublicBtn").addEventListener("click", importPublicKey);
    byId("exportPublicBtn").addEventListener("click", exportPublicKeys);
    byId("clearPublicBtn").addEventListener("click", clearPublicKeys);
}

window.addEventListener("load", () => {
    bindHandlers();
    updatePrivateStatus();
    renderPublicKeys();
    setGlobalStatus("Ready. Keys remain local to this browser.", false);
});
