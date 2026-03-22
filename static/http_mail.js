(function () {
  "use strict";

  var body = document.body;
  if (!body) {
    return;
  }

  var basePath = body.dataset.httpMailPath || "";
  var defaultSection = body.dataset.defaultSection || "create";

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function showSection(name) {
    ["create", "compose", "read"].forEach(function (section) {
      var el = document.getElementById(section + "-section");
      if (!el) {
        return;
      }
      if (section === name) {
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    });
  }

  function buildInboxUrl(address, readKey, query, sender, limit) {
    var url = "/" + basePath + "/mail/" + encodeURIComponent(address) +
      "/inbox?key=" + encodeURIComponent(readKey);
    if (query) {
      url += "&q=" + encodeURIComponent(query);
    }
    if (sender) {
      url += "&sender=" + encodeURIComponent(sender);
    }
    if (limit) {
      url += "&limit=" + encodeURIComponent(limit);
    }
    return url;
  }

  function updateComposeAction() {
    var addressInput = document.getElementById("compose-address-input");
    var composeForm = document.getElementById("compose-form");
    if (!addressInput || !composeForm) {
      return;
    }
    var address = addressInput.value.trim();
    if (address) {
      composeForm.action = "/" + basePath + "/mail/" + encodeURIComponent(address) + "/send";
    } else {
      composeForm.action = "/" + basePath + "/mail/send";
    }
  }

  function createMailbox() {
    var createBtn = document.getElementById("create-btn");
    if (!createBtn) {
      return;
    }

    createBtn.disabled = true;
    createBtn.textContent = "Creating...";

    fetch("/" + basePath + "/mail/new", {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data.success) {
          alert("Error: " + (data.error || "Unknown error"));
          return;
        }

        var mailboxResult = document.getElementById("new-mailbox-result");
        var addressEl = document.getElementById("result-address");
        var keyEl = document.getElementById("result-read-key");
        var sendUrlEl = document.getElementById("result-send-url");

        if (addressEl) {
          addressEl.textContent = data.address;
        }
        if (keyEl) {
          keyEl.textContent = data.read_key;
        }
        if (sendUrlEl) {
          sendUrlEl.textContent = window.location.origin + data.send_url;
        }
        if (mailboxResult) {
          mailboxResult.classList.remove("hidden");
        }
      })
      .catch(function (error) {
        alert("Request failed: " + error);
      })
      .finally(function () {
        createBtn.disabled = false;
        createBtn.textContent = "Create Another Mailbox";
      });
  }

  function renderInbox(messages, address, readKey) {
    var container = document.getElementById("js-inbox-messages");
    if (!container) {
      return;
    }

    if (!messages || messages.length === 0) {
      container.innerHTML = "<p class=\"muted mt-10\">No messages in this mailbox.</p>";
      return;
    }

    var html = "<h3 class=\"mt-20\">Messages (" + messages.length + ")</h3>";
    messages.forEach(function (msg) {
      html += "<div class=\"msg-card\">";
      html += "<div class=\"msg-meta\">From: " + esc(msg.sender) + " &nbsp;|&nbsp; " + esc(msg.timestamp) + "</div>";
      html += "<div class=\"msg-subject\">" + esc(msg.subject) + "</div>";
      html += "<div class=\"msg-body\">" + esc(msg.body) + "</div>";
      html += "<div class=\"msg-actions\">";
      html += "<button type=\"button\" class=\"danger js-delete-msg\" data-address=\"" +
        esc(address) + "\" data-msg-id=\"" + esc(msg.id) + "\" data-read-key=\"" + esc(readKey) +
        "\">🗑 Delete</button>";
      html += "</div></div>";
    });

    html += "<div class=\"danger-zone\">";
    html += "<h3 class=\"danger-title\">Danger Zone</h3>";
    html += "<button type=\"button\" class=\"danger js-destroy-mailbox\" data-address=\"" +
      esc(address) + "\" data-read-key=\"" + esc(readKey) + "\">💣 Destroy Mailbox</button>";
    html += "</div>";

    container.innerHTML = html;

    container.querySelectorAll(".js-delete-msg").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Delete this message?")) {
          return;
        }
        deleteMessage(btn.dataset.address, btn.dataset.msgId, btn.dataset.readKey);
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
    var keyInput = document.getElementById("read-key-input");
    var queryInput = document.getElementById("read-query");
    var senderInput = document.getElementById("read-sender");
    var limitInput = document.getElementById("read-limit");

    var address = addressInput ? addressInput.value.trim() : "";
    var readKey = keyInput ? keyInput.value.trim() : "";
    var query = queryInput ? queryInput.value.trim() : "";
    var sender = senderInput ? senderInput.value.trim() : "";
    var limit = limitInput ? limitInput.value.trim() : "";

    if (!address || !readKey) {
      alert("Please enter both mailbox address and read key.");
      return;
    }

    var url = buildInboxUrl(address, readKey, query, sender, limit);

    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (response.status === 400) {
          throw new Error("Invalid filter values");
        }
        if (response.status === 403) {
          throw new Error("Invalid read key — access denied");
        }
        if (response.status === 404) {
          throw new Error("Mailbox not found");
        }
        return response.json();
      })
      .then(function (data) {
        renderInbox(data.messages, address, readKey);
      })
      .catch(function (error) {
        var container = document.getElementById("js-inbox-messages");
        if (container) {
          container.innerHTML = "<div class=\"error-box\">⚠️ " + esc(error.message) + "</div>";
        }
      });
  }

  function deleteMessage(address, msgId, readKey) {
    fetch("/" + basePath + "/mail/" + encodeURIComponent(address) + "/delete/" + encodeURIComponent(msgId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ read_key: readKey }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data.success) {
          alert("Error: " + (data.error || "Could not delete message"));
          return;
        }
        fetchInbox();
      })
      .catch(function (error) {
        alert("Request failed: " + error);
      });
  }

  function destroyMailbox(address, readKey) {
    fetch("/" + basePath + "/mail/" + encodeURIComponent(address) + "/destroy", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ read_key: readKey }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data.success) {
          alert("Error: " + (data.error || "Could not destroy mailbox"));
          return;
        }
        var container = document.getElementById("js-inbox-messages");
        if (container) {
          container.innerHTML = "<div class=\"success-box\">✅ Mailbox destroyed.</div>";
        }
      })
      .catch(function (error) {
        alert("Request failed: " + error);
      });
  }

  function copyToken(elementId) {
    var source = document.getElementById(elementId);
    if (!source) {
      return;
    }

    var text = source.textContent || "";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        alert("Copied!");
      });
      return;
    }

    var fallback = document.createElement("textarea");
    fallback.value = text;
    fallback.className = "clipboard-buffer";
    document.body.appendChild(fallback);
    fallback.select();
    try {
      document.execCommand("copy");
      alert("Copied!");
    } catch (_error) {
      alert("Copy failed");
    }
    document.body.removeChild(fallback);
  }

  function bindServerRenderedConfirmations() {
    document.querySelectorAll(".confirm-delete-form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!confirm("Delete this message?")) {
          event.preventDefault();
        }
      });
    });

    document.querySelectorAll(".confirm-destroy-form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!confirm("Destroy mailbox and all messages permanently?")) {
          event.preventDefault();
        }
      });
    });
  }

  document.querySelectorAll(".section-button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      showSection(btn.dataset.sectionTarget || "create");
    });
  });

  var createButton = document.getElementById("create-btn");
  if (createButton) {
    createButton.addEventListener("click", createMailbox);
  }

  document.querySelectorAll(".copy-token").forEach(function (btn) {
    btn.addEventListener("click", function () {
      copyToken(btn.dataset.copyTarget || "");
    });
  });

  var openInboxBtn = document.getElementById("open-inbox-btn");
  if (openInboxBtn) {
    openInboxBtn.addEventListener("click", fetchInbox);
  }

  var composeAddressInput = document.getElementById("compose-address-input");
  if (composeAddressInput) {
    composeAddressInput.addEventListener("input", updateComposeAction);
    composeAddressInput.addEventListener("blur", updateComposeAction);
  }

  var composeForm = document.getElementById("compose-form");
  if (composeForm) {
    composeForm.addEventListener("submit", updateComposeAction);
  }

  bindServerRenderedConfirmations();
  updateComposeAction();
  showSection(defaultSection);
})();
