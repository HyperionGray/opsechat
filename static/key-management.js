// Browser-side PGP key management for /keys.
(function () {
    "use strict";

    const OWN_PUBLIC_STORAGE_KEY = "pgp_own_public_key";

    const elements = {
        status: document.getElementById("key-status"),
        generateName: document.getElementById("generate-name"),
        generateEmail: document.getElementById("generate-email"),
        generatePassphrase: document.getElementById("generate-passphrase"),
        generateButton: document.getElementById("generate-key-btn"),
        ownPublicKey: document.getElementById("own-public-key"),
        ownPrivateKey: document.getElementById("own-private-key"),
        downloadPublicButton: document.getElementById("download-public-key-btn"),
        downloadPrivateButton: document.getElementById("download-private-key-btn"),
        importPrivateText: document.getElementById("import-private-key-text"),
        importPrivatePassphrase: document.getElementById("import-private-passphrase"),
        importPrivateButton: document.getElementById("import-private-key-btn"),
        clearPrivateButton: document.getElementById("clear-private-key-btn"),
        publicKeyLabel: document.getElementById("public-key-label"),
        publicKeyText: document.getElementById("public-key-text"),
        addPublicButton: document.getElementById("add-public-key-btn"),
        clearPublicButton: document.getElementById("clear-public-keys-btn"),
        publicKeysList: document.getElementById("public-keys-list")
    };

    function setStatus(message, isError) {
        elements.status.textContent = message;
        elements.status.style.color = isError ? "#b00020" : "#006400";
    }

    function getOwnPublicKey() {
        return localStorage.getItem(OWN_PUBLIC_STORAGE_KEY) || "";
    }

    function setOwnPublicKey(armoredKey) {
        localStorage.setItem(OWN_PUBLIC_STORAGE_KEY, armoredKey);
    }

    function clearOwnPublicKey() {
        localStorage.removeItem(OWN_PUBLIC_STORAGE_KEY);
    }

    function downloadText(filename, content) {
        const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    function renderPublicKeys() {
        const keys = PGPManager.getPublicKeys();
        const labels = Object.keys(keys).sort();

        elements.publicKeysList.textContent = "";
        if (labels.length === 0) {
            const emptyItem = document.createElement("li");
            emptyItem.textContent = "No recipient public keys configured.";
            elements.publicKeysList.appendChild(emptyItem);
            return;
        }

        labels.forEach(function (label) {
            const listItem = document.createElement("li");
            const labelText = document.createElement("span");
            labelText.textContent = label;

            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.textContent = "Remove";
            removeButton.addEventListener("click", function () {
                PGPManager.removePublicKey(label);
                renderPublicKeys();
                setStatus("Removed public key: " + label, false);
            });

            listItem.appendChild(labelText);
            listItem.appendChild(document.createTextNode(" "));
            listItem.appendChild(removeButton);
            elements.publicKeysList.appendChild(listItem);
        });
    }

    function refreshView() {
        elements.ownPrivateKey.value = PGPManager.getPrivateKey() || "";
        elements.ownPublicKey.value = getOwnPublicKey();
        renderPublicKeys();
    }

    async function onGenerateKeyPair() {
        const name = elements.generateName.value.trim() || "OpSecChat User";
        const email = elements.generateEmail.value.trim() || "user@local";
        const passphrase = elements.generatePassphrase.value;

        setStatus("Generating key pair. This can take a moment...", false);

        try {
            const generated = await openpgp.generateKey({
                type: "rsa",
                rsaBits: 2048,
                userIDs: [{ name: name, email: email }],
                passphrase: passphrase
            });

            PGPManager.setPrivateKey(generated.privateKey);
            PGPManager.setPassphrase(passphrase);
            setOwnPublicKey(generated.publicKey);

            refreshView();
            setStatus("Key pair generated and stored in browser storage.", false);
        } catch (error) {
            setStatus("Failed to generate key pair: " + error.message, true);
        }
    }

    async function onImportPrivateKey() {
        const armored = elements.importPrivateText.value.trim();
        const passphrase = elements.importPrivatePassphrase.value;

        if (!armored) {
            setStatus("Private key is required for import.", true);
            return;
        }

        try {
            await openpgp.readPrivateKey({ armoredKey: armored });
            PGPManager.setPrivateKey(armored);
            PGPManager.setPassphrase(passphrase);
            elements.importPrivateText.value = "";
            elements.importPrivatePassphrase.value = "";
            refreshView();
            setStatus("Private key imported.", false);
        } catch (error) {
            setStatus("Failed to import private key: " + error.message, true);
        }
    }

    function onClearPrivateKey() {
        PGPManager.clearPrivateKey();
        clearOwnPublicKey();
        refreshView();
        setStatus("Private key cleared.", false);
    }

    async function onAddPublicKey() {
        const label = elements.publicKeyLabel.value.trim() || ("key-" + Date.now());
        const armored = elements.publicKeyText.value.trim();

        if (!armored) {
            setStatus("Public key is required.", true);
            return;
        }

        try {
            await openpgp.readKey({ armoredKey: armored });
            PGPManager.addPublicKey(label, armored);
            elements.publicKeyLabel.value = "";
            elements.publicKeyText.value = "";
            renderPublicKeys();
            setStatus("Public key added: " + label, false);
        } catch (error) {
            setStatus("Failed to add public key: " + error.message, true);
        }
    }

    function onClearPublicKeys() {
        PGPManager.clearAllPublicKeys();
        renderPublicKeys();
        setStatus("All recipient public keys cleared.", false);
    }

    function onDownloadPublicKey() {
        const publicKey = getOwnPublicKey();
        if (!publicKey) {
            setStatus("No public key available to download.", true);
            return;
        }
        downloadText("opsechat-public-key.asc", publicKey);
        setStatus("Public key downloaded.", false);
    }

    function onDownloadPrivateKey() {
        const privateKey = PGPManager.getPrivateKey();
        if (!privateKey) {
            setStatus("No private key available to download.", true);
            return;
        }
        downloadText("opsechat-private-key.asc", privateKey);
        setStatus("Private key downloaded. Store it securely.", false);
    }

    function init() {
        elements.generateButton.addEventListener("click", onGenerateKeyPair);
        elements.importPrivateButton.addEventListener("click", onImportPrivateKey);
        elements.clearPrivateButton.addEventListener("click", onClearPrivateKey);
        elements.addPublicButton.addEventListener("click", onAddPublicKey);
        elements.clearPublicButton.addEventListener("click", onClearPublicKeys);
        elements.downloadPublicButton.addEventListener("click", onDownloadPublicKey);
        elements.downloadPrivateButton.addEventListener("click", onDownloadPrivateKey);

        refreshView();
        setStatus("Ready.", false);
    }

    document.addEventListener("DOMContentLoaded", init);
})();
