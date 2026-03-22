(function () {
  "use strict";

  var appPath = document.body.dataset.path || "";
  var defaultSection = document.body.dataset.defaultSection || "create";

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function showSection(name) {
    ["create", "compose", "read"].forEach(function (sectionName) {
      var el = document.getElementById(sectionName + "-section");
      if (el) {
        el.classList.toggle("is-hidden", sectionName !== name);
      }
    });
  }

  function copyText(elementId) {
    var source = document.getElementById(elementId);
    if (!source) {
      return;
    }

    var text = source.textContent;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        alert("Copied!");
      });
      return;
    }
    window.prompt("Copy this value:", text);
  }

  function createMailbox() {
    var btn = document.getElementById("create-btn");
    if (!btn) {
      return;
    }

    btn.disabled = true;
    btn.textContent = "Creating...";

    fetch("/" + appPath + "/mail/new", {
      method: "POST",
      headers: { Accept: "application/json" }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) {
          throw new Error(data.error || "Unknown error");
        }

        document.getElementById("result-address").textContent = data.address;
        document.getElementById("result-read-key").textContent = data.read_key;
        document.getElementById("result-send-url").textContent =
          window.location.origin + data.send_url;
        document.getElementById("new-mailbox-result").classList.remove("is-hidden");
        btn.textContent = "Create Another Mailbox";
      })
      .catch(function (err) {
        alert("Request failed: " + err.message);
        btn.textContent = "Create Mailbox";
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  function renderInbox(messages, address, readKey) {
    var container = document.getElementById("js-inbox-messages");
    if (!container) {
      return;
    }

    if (messages.length === 0) {
      container.innerHTML = '<p class="empty-state">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="inbox-heading">Messages (' + messages.length + ")</h3>";
    messages.forEach(function (msg) {
      html += '<div class="msg-card">' +
        '<div class="msg-meta">From: ' + esc(msg.sender) + " &nbsp;|&nbsp; " + esc(msg.timestamp) + "</div>" +
        '<div class="msg-subject">' + esc(msg.subject) + "</div>" +
        '<div class="msg-body">' + esc(msg.body) + "</div>" +
        '<div class="msg-actions">' +
          '<button type="button" class="danger js-delete-msg"' +
            ' data-address="' + esc(address) + '"' +
            ' data-msg-id="' + esc(msg.id) + '"' +
            ' data-read-key="' + esc(readKey) + '">🗑 Delete</button>' +
        "</div></div>";
    });

    html += '<div class="danger-zone">' +
      '<h3 class="danger-heading">Danger Zone</h3>' +
      '<button type="button" class="danger js-destroy-mailbox"' +
        ' data-address="' + esc(address) + '"' +
        ' data-read-key="' + esc(readKey) + '">💣 Destroy Mailbox</button></div>';

    container.innerHTML = html;

    container.querySelectorAll(".js-delete-msg").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Delete this message?")) {
          return;
        }
        deleteMsg(btn.dataset.address, btn.dataset.msgId, btn.dataset.readKey);
      });
    });

    container.querySelectorAll(".js-destroy-mailbox").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Destroy mailbox and ALL messages permanently?")) {
          return;
        }
        destroyMailbox(btn.dataset.address, btn.dataset.readKey);
      });
    });
  }

  function fetchInbox() {
    var addressInput = document.getElementById("read-address");
    var readKeyInput = document.getElementById("read-key-input");
    if (!addressInput || !readKeyInput) {
      return;
    }

    var address = addressInput.value.trim();
    var readKey = readKeyInput.value.trim();

    if (!address || !readKey) {
      alert("Please enter both mailbox address and read key.");
      return;
    }

    var url = "/" + appPath + "/mail/" + encodeURIComponent(address) +
      "/inbox?key=" + encodeURIComponent(readKey);

    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        if (r.status === 403) {
          throw new Error("Invalid read key — access denied");
        }
        if (r.status === 404) {
          throw new Error("Mailbox not found");
        }
        return r.json();
      })
      .then(function (data) {
        renderInbox(data.messages || [], address, readKey);
      })
      .catch(function (err) {
        var container = document.getElementById("js-inbox-messages");
        if (container) {
          container.innerHTML = '<div class="error-box">⚠️ ' + esc(err.message) + "</div>";
        }
      });
  }

  function deleteMsg(address, msgId, readKey) {
    fetch("/" + appPath + "/mail/" + encodeURIComponent(address) + "/delete/" + encodeURIComponent(msgId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.success) {
          throw new Error(d.error || "Could not delete");
        }
        fetchInbox();
      })
      .catch(function (err) {
        alert("Error: " + err.message);
      });
  }

  function destroyMailbox(address, readKey) {
    fetch("/" + appPath + "/mail/" + encodeURIComponent(address) + "/destroy", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.success) {
          throw new Error(d.error || "Could not destroy mailbox");
        }
        var container = document.getElementById("js-inbox-messages");
        if (container) {
          container.innerHTML = '<div class="success-box">✅ Mailbox destroyed.</div>';
        }
      })
      .catch(function (err) {
        alert("Error: " + err.message);
      });
  }

  function bindSectionButtons() {
    document.querySelectorAll(".section-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showSection(btn.dataset.section);
      });
    });
  }

  function bindCopyButtons() {
    document.querySelectorAll(".copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        copyText(btn.dataset.copyTarget);
      });
    });
  }

  function bindConfirmationForms() {
    document.querySelectorAll('form[action*="/mail/"][action*="/delete/"], form[action*="/mail/"][action*="/destroy"]').forEach(function (form) {
      form.addEventListener("submit", function (event) {
        var isDestroy = form.action.indexOf("/destroy") !== -1;
        var question = isDestroy
          ? "Destroy mailbox and all messages permanently?"
          : "Delete this message?";
        if (!confirm(question)) {
          event.preventDefault();
        }
      });
    });
  }

  function init() {
    bindSectionButtons();
    bindCopyButtons();
    bindConfirmationForms();

    var createButton = document.getElementById("create-btn");
    if (createButton) {
      createButton.addEventListener("click", createMailbox);
    }

    var readButton = document.getElementById("open-inbox-btn");
    if (readButton) {
      readButton.addEventListener("click", fetchInbox);
    }

    showSection(defaultSection);
  }

  init();
})();
