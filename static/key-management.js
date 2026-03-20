(function () {
    "use strict";

    function byId(id) {
        return document.getElementById(id);
    }

    function setStatus(message, isError) {
        const banner = byId("statusBanner");
        banner.textContent = message;
        banner.style.color = isError ? "#ff8f8f" : "#7ce47c";
    }

    function triggerDownload(filename, content) {
        const blob = new Blob([content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    function refreshStatus() {
        const privateKey = PGPManager.getPrivateKey();
        const publicKeys = PGPManager.getPublicKeys();
        const labels = Object.keys(publicKeys);

        byId("privateKeyState").textContent = privateKey ? "Configured" : "Not configured";
        byId("publicKeyCount").textContent = String(labels.length);

        const list = byId("publicKeyList");
        list.innerHTML = "";
        if (labels.length === 0) {
            const li = document.createElement("li");
            li.textContent = "No public keys stored";
            list.appendChild(li);
            return;
        }

        labels.forEach((label) => {
            const li = document.createElement("li");
            li.textContent = label;
            list.appendChild(li);
        });
    }

    async function handleGenerate(event) {
        event.preventDefault();
        const name = byId("keyName").value.trim();
        const passphrase = byId("passphrase").value;

        if (!name) {
            setStatus("A key label is required.", true);
            return;
        }

        try {
            setStatus("Generating key pair...");
            const generated = await openpgp.generateKey({
                type: "ecc",
                curve: "curve25519",
                userIDs: [{ name: name }],
                passphrase: passphrase || undefined,
                format: "armored",
            });

            PGPManager.setPrivateKey(generated.privateKey);
            if (passphrase) {
                PGPManager.setPassphrase(passphrase);
            }
            PGPManager.addPublicKey(name, generated.publicKey);

            refreshStatus();
            setStatus("New key pair generated and stored locally.");
            byId("generateForm").reset();
        } catch (error) {
            setStatus("Key generation failed: " + error.message, true);
        }
    }

    async function handleImportPrivate(event) {
        event.preventDefault();
        const armored = byId("privateKeyInput").value.trim();
        const passphrase = byId("privateKeyPassphrase").value;

        try {
            const privateKey = await openpgp.readPrivateKey({ armoredKey: armored });
            if (passphrase) {
                await openpgp.decryptKey({ privateKey: privateKey, passphrase: passphrase });
                PGPManager.setPassphrase(passphrase);
            }

            PGPManager.setPrivateKey(armored);
            refreshStatus();
            setStatus("Private key imported.");
            byId("importPrivateForm").reset();
        } catch (error) {
            setStatus("Private key import failed: " + error.message, true);
        }
    }

    async function handleImportPublic(event) {
        event.preventDefault();
        const label = byId("publicKeyLabel").value.trim();
        const armored = byId("publicKeyInput").value.trim();

        if (!label) {
            setStatus("A public key label is required.", true);
            return;
        }

        try {
            await openpgp.readKey({ armoredKey: armored });
            PGPManager.addPublicKey(label, armored);
            refreshStatus();
            setStatus("Public key imported.");
            byId("importPublicForm").reset();
        } catch (error) {
            setStatus("Public key import failed: " + error.message, true);
        }
    }

    function handleExportPrivate() {
        const privateKey = PGPManager.getPrivateKey();
        if (!privateKey) {
            setStatus("No private key available to export.", true);
            return;
        }

        triggerDownload("opsechat-private-key.asc", privateKey);
        setStatus("Private key exported.");
    }

    function handleDeletePrivate() {
        const privateKey = PGPManager.getPrivateKey();
        if (!privateKey) {
            setStatus("No private key to delete.", true);
            return;
        }

        if (!window.confirm("Delete your private key from this browser? This cannot be undone.")) {
            return;
        }

        PGPManager.clearPrivateKey();
        refreshStatus();
        setStatus("Private key deleted.");
    }

    function handleClearPublic() {
        const publicKeys = PGPManager.getPublicKeys();
        if (Object.keys(publicKeys).length === 0) {
            setStatus("No public keys to delete.", true);
            return;
        }

        if (!window.confirm("Delete all stored public keys?")) {
            return;
        }

        PGPManager.clearAllPublicKeys();
        refreshStatus();
        setStatus("All public keys deleted.");
    }

    function bootstrap() {
        byId("generateForm").addEventListener("submit", handleGenerate);
        byId("importPrivateForm").addEventListener("submit", handleImportPrivate);
        byId("importPublicForm").addEventListener("submit", handleImportPublic);
        byId("exportPrivateBtn").addEventListener("click", handleExportPrivate);
        byId("deletePrivateBtn").addEventListener("click", handleDeletePrivate);
        byId("clearPublicBtn").addEventListener("click", handleClearPublic);

        refreshStatus();
        setStatus("Key manager loaded.");
    }

    document.addEventListener("DOMContentLoaded", bootstrap);
})();
