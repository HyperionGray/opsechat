(function () {
  "use strict";

  var body = document.body;
  var appPath = body ? body.dataset.path : "";
  if (!appPath) {
    return;
  }

  var basePath = "/" + appPath + "/mail";

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function showSection(name) {
    ["create", "compose", "read"].forEach(function (section) {
      var el = document.getElementById(section + "-section");
      if (el) {
        el.style.display = section === name ? "block" : "none";
      }
    });
  }

  function createMailbox() {
    var btn = document.getElementById("create-btn");
    if (!btn) {
      return;
    }
    btn.disabled = true;
    btn.textContent = "Creating...";

    fetch(basePath + "/new", {
      method: "POST",
      headers: { Accept: "application/json" }
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.success) {
          var addressEl = document.getElementById("result-address");
          var readKeyEl = document.getElementById("result-read-key");
          var sendUrlEl = document.getElementById("result-send-url");
          var resultBlock = document.getElementById("new-mailbox-result");

          if (addressEl) {
            addressEl.textContent = data.address;
          }
          if (readKeyEl) {
            readKeyEl.textContent = data.read_key;
          }
          if (sendUrlEl) {
            sendUrlEl.textContent = window.location.origin + data.send_url;
          }
          if (resultBlock) {
            resultBlock.style.display = "block";
          }
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

    var url = (
      basePath +
      "/" +
      encodeURIComponent(address) +
      "/inbox?key=" +
      encodeURIComponent(readKey)
    );

    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (response.status === 403) {
          throw new Error("Invalid read key - access denied");
        }
        if (response.status === 404) {
          throw new Error("Mailbox not found");
        }
        return response.json();
      })
      .then(function (data) {
        renderInbox(data.messages, address, readKey);
      })
      .catch(function (err) {
        var container = document.getElementById("js-inbox-messages");
        if (container) {
          container.innerHTML = '<div class="error-box">' + esc(err.message) + "</div>";
        }
      });
  }

  function deleteMsg(address, msgId, readKey) {
    fetch(
      basePath + "/" + encodeURIComponent(address) + "/delete/" + encodeURIComponent(msgId),
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ read_key: readKey })
      }
    )
      .then(function (response) {
        return response.json();
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
    fetch(basePath + "/" + encodeURIComponent(address) + "/destroy", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        var container = document.getElementById("js-inbox-messages");
        if (!container) {
          return;
        }
        if (data.success) {
          container.innerHTML = '<div class="success-box">Mailbox destroyed.</div>';
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

    if (!messages || messages.length === 0) {
      container.innerHTML = '<p class="subtle empty-message">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="messages-heading">Messages (' + messages.length + ")</h3>";
    messages.forEach(function (msg) {
      html +=
        '<div class="msg-card">' +
        '<div class="msg-meta">From: ' +
        esc(msg.sender) +
        " | " +
        esc(msg.timestamp) +
        "</div>" +
        '<div class="msg-subject">' +
        esc(msg.subject) +
        "</div>" +
        '<div class="msg-body">' +
        esc(msg.body) +
        "</div>" +
        '<div class="msg-actions">' +
        '<button type="button" class="danger js-delete-msg"' +
        ' data-address="' +
        esc(address) +
        '"' +
        ' data-msg-id="' +
        esc(msg.id) +
        '"' +
        ' data-read-key="' +
        esc(readKey) +
        '">' +
        "Delete</button>" +
        "</div></div>";
    });
    html +=
      '<div class="danger-zone">' +
      '<h3 class="danger-heading">Danger Zone</h3>' +
      '<button type="button" class="danger js-destroy-mailbox"' +
      ' data-address="' +
      esc(address) +
      '"' +
      ' data-read-key="' +
      esc(readKey) +
      '">' +
      "Destroy Mailbox</button>" +
      "</div>";
    container.innerHTML = html;

    container.querySelectorAll(".js-delete-msg").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!window.confirm("Delete this message?")) {
          return;
        }
        deleteMsg(btn.dataset.address, btn.dataset.msgId, btn.dataset.readKey);
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

  function copyText(elementId) {
    var el = document.getElementById(elementId);
    if (!el) {
      return;
    }
    var text = el.textContent || "";
    if (!text) {
      return;
    }

    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        alert("Copied.");
      });
      return;
    }

    var ta = document.createElement("textarea");
    ta.value = text;
    ta.className = "copy-buffer";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      alert("Copied.");
    } catch (err) {
      alert("Copy failed.");
    }
    document.body.removeChild(ta);
  }

  function onComposeSubmit(event) {
    var addressInput = document.getElementById("compose-address-input");
    if (!addressInput || addressInput.value.trim()) {
      return;
    }
    event.preventDefault();
    alert("Recipient mailbox address is required.");
  }

  function bindEventHandlers() {
    document.querySelectorAll(".section-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showSection(btn.dataset.section);
      });
    });

    var createBtn = document.getElementById("create-btn");
    if (createBtn) {
      createBtn.addEventListener("click", createMailbox);
    }

    document.querySelectorAll(".copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        copyText(btn.dataset.target);
      });
    });

    var openInboxBtn = document.getElementById("open-inbox-btn");
    if (openInboxBtn) {
      openInboxBtn.addEventListener("click", fetchInbox);
    }

    document.querySelectorAll(".delete-message-form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!window.confirm("Delete this message?")) {
          event.preventDefault();
        }
      });
    });

    var destroyForm = document.getElementById("destroy-mailbox-form");
    if (destroyForm) {
      destroyForm.addEventListener("submit", function (event) {
        if (!window.confirm("Destroy mailbox and all messages permanently?")) {
          event.preventDefault();
        }
      });
    }

    var composeForm = document.getElementById("compose-form");
    if (composeForm) {
      composeForm.addEventListener("submit", onComposeSubmit);
    }
  }

  bindEventHandlers();
  showSection(body.dataset.openSection || "create");
})();
