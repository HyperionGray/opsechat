"use strict";

(function () {
  function setStatus(message, isError) {
    const statusNode = document.getElementById("statusMessage");
    statusNode.textContent = message;
    statusNode.style.color = isError ? "#f66" : "#0f0";
  }

  function downloadTextFile(filename, content) {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  function getPublicKeyAliases() {
    const publicKeys = PGPManager.getPublicKeys();
    return Object.keys(publicKeys).sort();
  }

  function renderPublicKeyList() {
    const listNode = document.getElementById("publicKeyList");
    listNode.innerHTML = "";
    const aliases = getPublicKeyAliases();

    if (aliases.length === 0) {
      const item = document.createElement("li");
      item.textContent = "No public keys stored.";
      listNode.appendChild(item);
      return;
    }

    aliases.forEach(function (alias) {
      const item = document.createElement("li");
      item.textContent = alias;

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.textContent = "Delete";
      removeButton.addEventListener("click", function () {
        PGPManager.removePublicKey(alias);
        renderPublicKeyList();
        updateStatusSummary();
        setStatus("Deleted public key: " + alias, false);
      });

      item.appendChild(removeButton);
      listNode.appendChild(item);
    });
  }

  function updateStatusSummary() {
    const canDecrypt = PGPManager.canDecrypt();
    const aliases = getPublicKeyAliases();
    const parts = [];

    if (canDecrypt) {
      parts.push("Private key configured");
    } else {
      parts.push("No private key configured");
    }
    parts.push("Public keys: " + aliases.length);
    setStatus(parts.join(" | "), false);
  }

  async function handleGenerateKeyPair() {
    const name = document.getElementById("genName").value.trim() || "OpSec User";
    const email = document.getElementById("genEmail").value.trim() || "user@local.invalid";
    const passphrase = document.getElementById("genPassphrase").value;

    setStatus("Generating key pair...", false);
    try {
      const result = await openpgp.generateKey({
        type: "ecc",
        curve: "curve25519",
        userIDs: [{ name: name, email: email }],
        passphrase: passphrase
      });

      PGPManager.setPrivateKey(result.privateKey);
      if (passphrase) {
        PGPManager.setPassphrase(passphrase);
      } else {
        PGPManager.setPassphrase("");
      }
      PGPManager.addPublicKey("self-" + Date.now(), result.publicKey);

      renderPublicKeyList();
      updateStatusSummary();
      setStatus("Generated a new key pair and stored it locally.", false);
    } catch (error) {
      setStatus("Failed to generate key pair: " + error.message, true);
    }
  }

  async function handleImportPrivateKey() {
    const privateKey = document.getElementById("privateKeyInput").value.trim();
    const passphrase = document.getElementById("privatePassphraseInput").value;

    if (!privateKey) {
      setStatus("Private key input is empty.", true);
      return;
    }

    try {
      const parsedKey = await openpgp.readPrivateKey({ armoredKey: privateKey });
      if (passphrase) {
        await openpgp.decryptKey({
          privateKey: parsedKey,
          passphrase: passphrase
        });
      }
      PGPManager.setPrivateKey(privateKey);
      PGPManager.setPassphrase(passphrase || "");
      document.getElementById("privateKeyInput").value = "";
      document.getElementById("privatePassphraseInput").value = "";
      updateStatusSummary();
      setStatus("Private key imported successfully.", false);
    } catch (error) {
      setStatus("Failed to import private key: " + error.message, true);
    }
  }

  function handleExportPrivateKey() {
    const privateKey = PGPManager.getPrivateKey();
    if (!privateKey) {
      setStatus("No private key available to export.", true);
      return;
    }
    downloadTextFile("opsechat-private-key.asc", privateKey);
    setStatus("Private key exported.", false);
  }

  function handleDeletePrivateKey() {
    if (!PGPManager.getPrivateKey()) {
      setStatus("No private key to delete.", true);
      return;
    }
    if (!window.confirm("Delete private key from browser storage?")) {
      return;
    }
    PGPManager.clearPrivateKey();
    updateStatusSummary();
    setStatus("Private key deleted.", false);
  }

  async function handleAddPublicKey() {
    const aliasInput = document.getElementById("publicAliasInput");
    const keyInput = document.getElementById("publicKeyInput");
    const alias = aliasInput.value.trim() || ("key-" + Date.now());
    const publicKey = keyInput.value.trim();

    if (!publicKey) {
      setStatus("Public key input is empty.", true);
      return;
    }

    try {
      await openpgp.readKey({ armoredKey: publicKey });
      PGPManager.addPublicKey(alias, publicKey);
      aliasInput.value = "";
      keyInput.value = "";
      renderPublicKeyList();
      updateStatusSummary();
      setStatus("Added public key: " + alias, false);
    } catch (error) {
      setStatus("Failed to add public key: " + error.message, true);
    }
  }

  function handleDeleteAllPublicKeys() {
    if (!window.confirm("Delete all stored public keys?")) {
      return;
    }
    PGPManager.clearAllPublicKeys();
    renderPublicKeyList();
    updateStatusSummary();
    setStatus("Deleted all public keys.", false);
  }

  function bindEvents() {
    document.getElementById("generateKeyBtn").addEventListener("click", handleGenerateKeyPair);
    document.getElementById("importPrivateBtn").addEventListener("click", handleImportPrivateKey);
    document.getElementById("exportPrivateBtn").addEventListener("click", handleExportPrivateKey);
    document.getElementById("removePrivateBtn").addEventListener("click", handleDeletePrivateKey);
    document.getElementById("addPublicBtn").addEventListener("click", handleAddPublicKey);
    document.getElementById("clearPublicBtn").addEventListener("click", handleDeleteAllPublicKeys);
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindEvents();
    renderPublicKeyList();
    updateStatusSummary();
  });
})();
