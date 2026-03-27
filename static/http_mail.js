(function () {
  function getPath() {
    var body = document.body;
    return body ? body.getAttribute("data-path") || "" : "";
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function showSection(name) {
    ["create", "compose", "read"].forEach(function (section) {
      var el = byId(section + "-section");
      if (el) {
        el.style.display = section === name ? "block" : "none";
      }
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function copyTextFromElement(elementId) {
    var el = byId(elementId);
    if (!el) {
      return;
    }
    var text = el.textContent || "";

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () {});
      return;
    }

    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
    } catch (e) {}
    document.body.removeChild(ta);
  }

  function createMailbox() {
    var path = getPath();
    var btn = byId("create-btn");
    if (!btn || !path) {
      return;
    }

    btn.disabled = true;
    btn.textContent = "Creating...";

    fetch("/" + path + "/mail/new", {
      method: "POST",
      headers: { Accept: "application/json" }
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.success) {
          alert("Error: " + (data.error || "Unknown error"));
          return;
        }
        byId("result-address").textContent = data.address;
        byId("result-read-key").textContent = data.read_key;
        byId("result-send-url").textContent = window.location.origin + data.send_url;
        byId("new-mailbox-result").classList.remove("is-hidden");
      })
      .catch(function (err) {
        alert("Request failed: " + err);
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Create Another Mailbox";
      });
  }

  function renderInbox(messages, address, readKey) {
    var path = getPath();
    var container = byId("js-inbox-messages");
    if (!container || !path) {
      return;
    }

    if (!messages || messages.length === 0) {
      container.innerHTML = '<p class="muted mt-10">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="mt-20">Messages (' + messages.length + ")</h3>";
    messages.forEach(function (msg) {
      html +=
        '<div class="msg-card">' +
        '<div class="msg-meta">From: ' + escapeHtml(msg.sender) + " | " + escapeHtml(msg.timestamp) + "</div>" +
        '<div class="msg-subject">' + escapeHtml(msg.subject) + "</div>" +
        '<div class="msg-body">' + escapeHtml(msg.body) + "</div>" +
        '<div class="msg-actions">' +
        '<button type="button" class="danger js-delete-msg"' +
        ' data-address="' + escapeHtml(address) + '"' +
        ' data-msg-id="' + escapeHtml(msg.id) + '"' +
        ' data-read-key="' + escapeHtml(readKey) + '">' +
        "Delete</button></div></div>";
    });

    html +=
      '<div class="danger-zone">' +
      '<h3 class="danger-title">Danger Zone</h3>' +
      '<button type="button" class="danger js-destroy-mailbox"' +
      ' data-address="' + escapeHtml(address) + '"' +
      ' data-read-key="' + escapeHtml(readKey) + '">Destroy Mailbox</button></div>';

    container.innerHTML = html;

    container.querySelectorAll(".js-delete-msg").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!window.confirm("Delete this message?")) {
          return;
        }
        deleteMessage(btn.dataset.address, btn.dataset.msgId, btn.dataset.readKey);
      });
    });

    container.querySelectorAll(".js-destroy-mailbox").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!window.confirm("Destroy mailbox and all messages permanently?")) {
          return;
        }
        destroyMailbox(btn.dataset.address, btn.dataset.readKey);
      });
    });
  }

  function fetchInbox() {
    var path = getPath();
    var addressEl = byId("read-address");
    var keyEl = byId("read-key-input");
    var container = byId("js-inbox-messages");
    if (!path || !addressEl || !keyEl || !container) {
      return;
    }

    var address = addressEl.value.trim();
    var readKey = keyEl.value.trim();
    if (!address || !readKey) {
      return;
    }

    var url =
      "/" +
      path +
      "/mail/" +
      encodeURIComponent(address) +
      "/inbox?key=" +
      encodeURIComponent(readKey);

    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        if (r.status === 403) {
          throw new Error("Invalid read key - access denied");
        }
        if (r.status === 404) {
          throw new Error("Mailbox not found");
        }
        return r.json();
      })
      .then(function (data) {
        renderInbox(data.messages, address, readKey);
      })
      .catch(function (err) {
        container.innerHTML = '<div class="error-box">' + escapeHtml(err.message) + "</div>";
      });
  }

  function deleteMessage(address, msgId, readKey) {
    var path = getPath();
    if (!path) {
      return;
    }
    fetch(
      "/" +
        path +
        "/mail/" +
        encodeURIComponent(address) +
        "/delete/" +
        encodeURIComponent(msgId),
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ read_key: readKey })
      }
    )
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.success) {
          fetchInbox();
        } else {
          alert("Error: " + (data.error || "Could not delete"));
        }
      });
  }

  function destroyMailbox(address, readKey) {
    var path = getPath();
    var container = byId("js-inbox-messages");
    if (!path || !container) {
      return;
    }
    fetch("/" + path + "/mail/" + encodeURIComponent(address) + "/destroy", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.success) {
          container.innerHTML = '<div class="success-box">Mailbox destroyed.</div>';
          showSection("create");
        } else {
          alert("Error: " + (data.error || "Could not destroy mailbox"));
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var activeSection = document.body.getAttribute("data-active-section") || "create";
    showSection(activeSection);

    document.querySelectorAll(".js-show-section").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-section");
        showSection(target);
      });
    });

    var createBtn = byId("create-btn");
    if (createBtn) {
      createBtn.addEventListener("click", createMailbox);
    }

    var readForm = byId("read-form");
    if (readForm) {
      readForm.addEventListener("submit", function (event) {
        event.preventDefault();
        fetchInbox();
      });
    }

    document.querySelectorAll(".js-copy").forEach(function (btn) {
      btn.addEventListener("click", function () {
        copyTextFromElement(btn.getAttribute("data-target"));
      });
    });

    document.querySelectorAll(".js-confirm").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        var message = form.getAttribute("data-confirm") || "Are you sure?";
        if (!window.confirm(message)) {
          event.preventDefault();
        }
      });
    });
  });
})();
