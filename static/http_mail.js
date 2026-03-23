(function () {
  "use strict";

  var appPath = document.body.dataset.httpMailPath || "";
  var defaultSection = document.body.dataset.defaultSection || "create";

  function route(path) {
    return "/" + appPath + path;
  }

  function showSection(name) {
    ["create", "compose", "read"].forEach(function (sectionName) {
      var el = document.getElementById(sectionName + "-section");
      if (el) {
        el.style.display = sectionName === name ? "block" : "none";
      }
    });
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function copyText(elementId) {
    var textEl = document.getElementById(elementId);
    if (!textEl) {
      return;
    }

    var text = textEl.textContent;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        alert("Copied!");
      });
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
      alert("Copied!");
    } catch (e) {
      // Ignore clipboard failures in legacy browsers.
    }
    document.body.removeChild(ta);
  }

  function createMailbox() {
    var btn = document.getElementById("create-btn");
    if (!btn) {
      return;
    }

    btn.disabled = true;
    btn.textContent = "Creating...";

    fetch(route("/mail/new"), {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.success) {
          document.getElementById("result-address").textContent = data.address;
          document.getElementById("result-read-key").textContent = data.read_key;
          document.getElementById("result-send-url").textContent =
            window.location.origin + data.send_url;
          document.getElementById("new-mailbox-result").style.display = "block";
        } else {
          alert("Error: " + (data.error || "Unknown error"));
        }
        btn.disabled = false;
        btn.textContent = "Create Another Mailbox";
      })
      .catch(function (err) {
        alert("Request failed: " + err);
        btn.disabled = false;
        btn.textContent = "Create Mailbox";
      });
  }

  function updateComposeAction() {
    var addrInput = document.getElementById("compose-address-input");
    var form = document.getElementById("compose-form");
    if (!addrInput || !form) {
      return;
    }

    var addr = addrInput.value.trim();
    form.action = addr ? route("/mail/" + encodeURIComponent(addr) + "/send") : route("/mail/send");
  }

  function renderMailboxStats(stats) {
    var container = document.getElementById("mailbox-stats");
    if (!container) {
      return;
    }

    container.innerHTML =
      '<div class="info">' +
      "<strong>Mailbox Stats</strong><br>" +
      "Messages: " + esc(stats.message_count) + "<br>" +
      "Created: " + esc(stats.created_at) + "<br>" +
      "Oldest Message: " + esc(stats.oldest_message_at || "n/a") + "<br>" +
      "Newest Message: " + esc(stats.newest_message_at || "n/a") + "<br>" +
      "Retention: " + esc(stats.expiry_hours) + " hours" +
      "</div>";
  }

  function fetchMailboxStats() {
    var address = document.getElementById("read-address").value.trim();
    var readKey = document.getElementById("read-key-input").value.trim();
    var container = document.getElementById("mailbox-stats");

    if (!address || !readKey) {
      if (container) {
        container.innerHTML = '<div class="error-box">⚠️ Enter address and read key first.</div>';
      }
      return;
    }

    var url = route("/mail/" + encodeURIComponent(address) + "/stats?key=" + encodeURIComponent(readKey));
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
      .then(renderMailboxStats)
      .catch(function (err) {
        if (container) {
          container.innerHTML = '<div class="error-box">⚠️ ' + esc(err.message) + "</div>";
        }
      });
  }

  function deleteMsg(address, msgId, readKey) {
    fetch(route("/mail/" + encodeURIComponent(address) + "/delete/" + encodeURIComponent(msgId)), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ read_key: readKey }),
    })
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
    fetch(route("/mail/" + encodeURIComponent(address) + "/destroy"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ read_key: readKey }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.success) {
          document.getElementById("js-inbox-messages").innerHTML =
            '<div class="success-box">✅ Mailbox destroyed.</div>';
          document.getElementById("mailbox-stats").innerHTML = "";
        } else {
          alert("Error: " + (data.error || "Could not destroy mailbox"));
        }
      });
  }

  function renderInbox(messages, address, readKey) {
    var container = document.getElementById("js-inbox-messages");
    if (!container) {
      return;
    }

    if (!messages.length) {
      container.innerHTML = '<p class="no-messages">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="inbox-wrap">Messages (' + messages.length + ")</h3>";
    messages.forEach(function (msg) {
      html +=
        '<div class="msg-card">' +
        '<div class="msg-meta">From: ' + esc(msg.sender) + " &nbsp;|&nbsp; " + esc(msg.timestamp) + "</div>" +
        '<div class="msg-subject">' + esc(msg.subject) + "</div>" +
        '<div class="msg-body">' + esc(msg.body) + "</div>" +
        '<div class="msg-actions">' +
        '<button class="danger js-delete-msg" data-address="' + esc(address) +
        '" data-msg-id="' + esc(msg.id) +
        '" data-read-key="' + esc(readKey) +
        '">🗑 Delete</button>' +
        "</div>" +
        "</div>";
    });

    html +=
      '<div class="danger-zone">' +
      '<h3 class="danger-title">Danger Zone</h3>' +
      '<button class="danger js-destroy-mailbox" data-address="' + esc(address) +
      '" data-read-key="' + esc(readKey) + '">💣 Destroy Mailbox</button>' +
      "</div>";

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
    var address = document.getElementById("read-address").value.trim();
    var readKey = document.getElementById("read-key-input").value.trim();

    if (!address || !readKey) {
      alert("Please enter both mailbox address and read key.");
      return;
    }

    var url = route("/mail/" + encodeURIComponent(address) + "/inbox?key=" + encodeURIComponent(readKey));

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
        renderInbox(data.messages, address, readKey);
        fetchMailboxStats();
      })
      .catch(function (err) {
        document.getElementById("js-inbox-messages").innerHTML =
          '<div class="error-box">⚠️ ' + esc(err.message) + "</div>";
      });
  }

  document.querySelectorAll("[data-section]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      showSection(btn.dataset.section);
    });
  });

  var createBtn = document.getElementById("create-btn");
  if (createBtn) {
    createBtn.addEventListener("click", createMailbox);
  }

  document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      copyText(btn.dataset.copyTarget);
    });
  });

  var composeAddressInput = document.getElementById("compose-address-input");
  if (composeAddressInput) {
    composeAddressInput.addEventListener("input", updateComposeAction);
    composeAddressInput.addEventListener("change", updateComposeAction);
  }
  updateComposeAction();

  var readForm = document.getElementById("read-form");
  if (readForm) {
    readForm.addEventListener("submit", function (e) {
      e.preventDefault();
      fetchInbox();
    });
  }

  var openInboxBtn = document.getElementById("open-inbox-btn");
  if (openInboxBtn) {
    openInboxBtn.addEventListener("click", fetchInbox);
  }

  var statsBtn = document.getElementById("fetch-stats-btn");
  if (statsBtn) {
    statsBtn.addEventListener("click", fetchMailboxStats);
  }

  document.querySelectorAll(".js-confirm-delete").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!confirm("Delete this message?")) {
        e.preventDefault();
      }
    });
  });

  document.querySelectorAll(".js-confirm-destroy").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!confirm("Destroy mailbox and all messages permanently?")) {
        e.preventDefault();
      }
    });
  });

  showSection(defaultSection);
})();
