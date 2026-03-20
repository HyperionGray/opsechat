(function () {
    "use strict";

    const privateKeyStatusEl = document.getElementById("privateKeyStatus");
    const publicKeyCountEl = document.getElementById("publicKeyCount");
    const privateFingerprintEl = document.getElementById("privateFingerprint");
    const statusMessageEl = document.getElementById("statusMessage");
    const publicKeyListEl = document.getElementById("publicKeyList");

    const generateKeyForm = document.getElementById("generateKeyForm");
    const nameInput = document.getElementById("nameInput");
    const emailInput = document.getElementById("emailInput");
    const passphraseInput = document.getElementById("passphraseInput");

    const privateKeyInput = document.getElementById("privateKeyInput");
    const importPrivateKeyBtn = document.getElementById("importPrivateKeyBtn");
    const exportPrivateKeyBtn = document.getElementById("exportPrivateKeyBtn");
    const deletePrivateKeyBtn = document.getElementById("deletePrivateKeyBtn");

    const contactNameInput = document.getElementById("contactNameInput");
    const publicKeyInput = document.getElementById("publicKeyInput");
    const addPublicKeyBtn = document.getElementById("addPublicKeyBtn");
    const clearPublicKeysBtn = document.getElementById("clearPublicKeysBtn");

    function setStatus(message, isError) {
        statusMessageEl.textContent = message;
        statusMessageEl.className = isError ? "status-message error" : "status-message success";
    }

    function downloadTextFile(filename, content) {
        const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    async function refreshStatus() {
        const privateKey = PGPManager.getPrivateKey();
        const publicKeys = PGPManager.getPublicKeys();

        privateKeyStatusEl.textContent = privateKey ? "Present" : "Not set";
        publicKeyCountEl.textContent = String(Object.keys(publicKeys).length);
        exportPrivateKeyBtn.disabled = !privateKey;
        deletePrivateKeyBtn.disabled = !privateKey;

        if (privateKey) {
            try {
                const privateKeyObject = await openpgp.readPrivateKey({ armoredKey: privateKey });
                privateFingerprintEl.textContent = privateKeyObject.getFingerprint();
            } catch (error) {
                privateFingerprintEl.textContent = "Invalid key data";
            }
        } else {
            privateFingerprintEl.textContent = "N/A";
        }

        renderPublicKeyList(publicKeys);
    }

    function renderPublicKeyList(publicKeys) {
        publicKeyListEl.textContent = "";
        const entries = Object.entries(publicKeys);
        if (!entries.length) {
            const emptyItem = document.createElement("li");
            emptyItem.textContent = "No public keys saved";
            publicKeyListEl.appendChild(emptyItem);
            return;
        }

        for (const [label] of entries) {
            const li = document.createElement("li");
            li.textContent = label;

            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "small-btn danger";
            removeBtn.textContent = "Remove";
            removeBtn.addEventListener("click", function () {
                PGPManager.removePublicKey(label);
                setStatus("Removed public key: " + label, false);
                refreshStatus();
            });

            li.appendChild(removeBtn);
            publicKeyListEl.appendChild(li);
        }
    }

    generateKeyForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const name = nameInput.value.trim();
        const email = emailInput.value.trim();
        const passphrase = passphraseInput.value;

        if (!name) {
            setStatus("Name is required to generate a key.", true);
            return;
        }

        try {
            const generated = await openpgp.generateKey({
                type: "ecc",
                curve: "ed25519",
                userIDs: [{ name: name, email: email || undefined }],
                passphrase: passphrase || undefined,
            });

            PGPManager.setPrivateKey(generated.privateKey);
            PGPManager.setPassphrase(passphrase || "");
            privateKeyInput.value = "";
            passphraseInput.value = "";

            setStatus("New private key generated and saved locally.", false);
            await refreshStatus();
        } catch (error) {
            setStatus("Failed to generate key: " + error.message, true);
        }
    });

    importPrivateKeyBtn.addEventListener("click", async function () {
        const armoredKey = privateKeyInput.value.trim();
        if (!armoredKey) {
            setStatus("Paste a private key before importing.", true);
            return;
        }

        try {
            await openpgp.readPrivateKey({ armoredKey: armoredKey });
            PGPManager.setPrivateKey(armoredKey);
            setStatus("Private key imported successfully.", false);
            privateKeyInput.value = "";
            await refreshStatus();
        } catch (error) {
            setStatus("Invalid private key: " + error.message, true);
        }
    });

    exportPrivateKeyBtn.addEventListener("click", function () {
        const privateKey = PGPManager.getPrivateKey();
        if (!privateKey) {
            setStatus("No private key available to export.", true);
            return;
        }
        downloadTextFile("opsechat-private-key.asc", privateKey);
        setStatus("Private key exported.", false);
    });

    deletePrivateKeyBtn.addEventListener("click", async function () {
        const confirmed = window.confirm("Delete the locally stored private key?");
        if (!confirmed) {
            return;
        }
        PGPManager.clearPrivateKey();
        setStatus("Private key deleted from this browser.", false);
        await refreshStatus();
    });

    addPublicKeyBtn.addEventListener("click", async function () {
        const label = contactNameInput.value.trim();
        const armoredKey = publicKeyInput.value.trim();

        if (!label || !armoredKey) {
            setStatus("Contact label and public key are both required.", true);
            return;
        }

        try {
            await openpgp.readKey({ armoredKey: armoredKey });
            PGPManager.addPublicKey(label, armoredKey);
            contactNameInput.value = "";
            publicKeyInput.value = "";
            setStatus("Saved public key for: " + label, false);
            await refreshStatus();
        } catch (error) {
            setStatus("Invalid public key: " + error.message, true);
        }
    });

    clearPublicKeysBtn.addEventListener("click", async function () {
        const confirmed = window.confirm("Remove all saved public keys?");
        if (!confirmed) {
            return;
        }
        PGPManager.clearAllPublicKeys();
        setStatus("All public keys removed.", false);
        await refreshStatus();
    });

    refreshStatus();
})();
