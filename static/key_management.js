/* global openpgp, PGPManager */
(function () {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function setMessage(id, text, isError) {
    var el = byId(id);
    if (!el) {
      return;
    }
    el.textContent = text;
    el.className = isError ? "result error" : "result ok";
  }

  function downloadText(filename, text) {
    var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function refreshStatus() {
    var hasPrivate = !!PGPManager.getPrivateKey();
    var publicKeys = PGPManager.getPublicKeys();
    var labels = Object.keys(publicKeys);
    var statusLine = byId("status-line");
    var list = byId("public-key-list");

    if (statusLine) {
      statusLine.textContent =
        "Private key: " + (hasPrivate ? "configured" : "not configured") +
        " | Public keys: " + labels.length;
    }

    if (!list) {
      return;
    }

    list.innerHTML = "";
    labels.forEach(function (label) {
      var item = document.createElement("li");
      var remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.dataset.label = label;
      remove.className = "danger key-remove-btn";
      item.textContent = label;
      item.appendChild(remove);
      list.appendChild(item);
    });
  }

  async function onGenerateKey(event) {
    event.preventDefault();

    var name = byId("gen-name").value.trim();
    var email = byId("gen-email").value.trim();
    var passphrase = byId("gen-passphrase").value;

    if (passphrase.length < 8) {
      setMessage("generate-result", "Passphrase must be at least 8 characters.", true);
      return;
    }

    setMessage("generate-result", "Generating key pair, this may take a moment...", false);

    try {
      var keyPair = await openpgp.generateKey({
        type: "rsa",
        rsaBits: 3072,
        userIDs: [{ name: name || "OpSecChat User", email: email || "" }],
        passphrase: passphrase
      });

      var label = (name || "my-key").toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
      PGPManager.setPrivateKey(keyPair.privateKey);
      PGPManager.setPassphrase(passphrase);
      PGPManager.addPublicKey(label, keyPair.publicKey);
      setMessage("generate-result", "Key pair generated and stored locally.", false);
      event.target.reset();
      refreshStatus();
    } catch (error) {
      setMessage("generate-result", "Failed to generate key: " + error.message, true);
    }
  }

  async function onImportPrivate(event) {
    event.preventDefault();

    var privateKey = byId("private-key-input").value.trim();
    var passphrase = byId("private-passphrase-input").value;

    try {
      var parsed = await openpgp.readPrivateKey({ armoredKey: privateKey });
      await openpgp.decryptKey({
        privateKey: parsed,
        passphrase: passphrase
      });

      PGPManager.setPrivateKey(privateKey);
      PGPManager.setPassphrase(passphrase);
      setMessage("private-result", "Private key imported.", false);
      event.target.reset();
      refreshStatus();
    } catch (error) {
      setMessage("private-result", "Invalid private key or passphrase.", true);
    }
  }

  async function onImportPublic(event) {
    event.preventDefault();

    var label = byId("public-username-input").value.trim();
    var publicKey = byId("public-key-input").value.trim();

    if (!label) {
      setMessage("public-result", "Label is required.", true);
      return;
    }

    try {
      await openpgp.readKey({ armoredKey: publicKey });
      PGPManager.addPublicKey(label, publicKey);
      setMessage("public-result", "Public key imported.", false);
      event.target.reset();
      refreshStatus();
    } catch (error) {
      setMessage("public-result", "Invalid public key format.", true);
    }
  }

  function bindActions() {
    byId("generate-key-form").addEventListener("submit", onGenerateKey);
    byId("import-private-form").addEventListener("submit", onImportPrivate);
    byId("import-public-form").addEventListener("submit", onImportPublic);

    byId("public-key-list").addEventListener("click", function (event) {
      var label = event.target.dataset.label;
      if (!label) {
        return;
      }
      PGPManager.removePublicKey(label);
      setMessage("action-result", "Removed public key: " + label, false);
      refreshStatus();
    });

    byId("export-private-btn").addEventListener("click", function () {
      var privateKey = PGPManager.getPrivateKey();
      if (!privateKey) {
        setMessage("action-result", "No private key available to export.", true);
        return;
      }
      downloadText("opsechat-private-key.asc", privateKey);
      setMessage("action-result", "Private key exported.", false);
    });

    byId("export-public-btn").addEventListener("click", function () {
      var publicKeys = PGPManager.getPublicKeys();
      if (Object.keys(publicKeys).length === 0) {
        setMessage("action-result", "No public keys available to export.", true);
        return;
      }
      downloadText("opsechat-public-keys.json", JSON.stringify(publicKeys, null, 2));
      setMessage("action-result", "Public keys exported.", false);
    });

    byId("clear-private-btn").addEventListener("click", function () {
      if (!window.confirm("Delete the stored private key from this browser?")) {
        return;
      }
      PGPManager.clearPrivateKey();
      setMessage("action-result", "Private key deleted from local storage.", false);
      refreshStatus();
    });

    byId("clear-public-btn").addEventListener("click", function () {
      if (!window.confirm("Delete all stored public keys from this browser?")) {
        return;
      }
      PGPManager.clearAllPublicKeys();
      setMessage("action-result", "All public keys deleted.", false);
      refreshStatus();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindActions();
    refreshStatus();
  });
})();
