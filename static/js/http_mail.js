(function () {
  "use strict";

  function getPath() {
    return document.body.getAttribute("data-mail-path") || "";
  }

  function showSection(name) {
    ["create", "compose", "read"].forEach(function (section) {
      var el = document.getElementById(section + "-section");
      if (el) {
        el.style.display = section === name ? "block" : "none";
      }
    });
  }

  function copyText(elementId) {
    var el = document.getElementById(elementId);
    if (!el) {
      return;
    }
    var text = el.textContent || "";
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        alert("Copied.");
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
      alert("Copied.");
    } catch (err) {
      alert("Copy failed.");
    }
    document.body.removeChild(ta);
  }

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function createMailbox() {
    var path = getPath();
    var btn = document.getElementById("create-btn");
    if (!btn || !path) {
      return;
    }

    btn.disabled = true;
    btn.textContent = "Creating...";

    fetch("/" + path + "/mail/new", {
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

        document.getElementById("result-address").textContent = data.address;
        document.getElementById("result-read-key").textContent = data.read_key;
        document.getElementById("result-send-url").textContent =
          window.location.origin + data.send_url;
        document.getElementById("new-mailbox-result").style.display = "block";
      })
      .catch(function (err) {
        alert("Request failed: " + err);
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Create Another Mailbox";
      });
  }

  function fetchInbox() {
    var path = getPath();
    var address = (document.getElementById("read-address") || {}).value || "";
    var readKey = (document.getElementById("read-key-input") || {}).value || "";
    address = address.trim();
    readKey = readKey.trim();

    if (!address || !readKey) {
      alert("Please enter both mailbox address and read key.");
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
      .then(function (response) {
        if (response.status === 403) {
          throw new Error("Invalid read key - access denied");
        }
        if (response.status === 404) {
          throw new Error("Mailbox not found");
        }
        if (!response.ok) {
          throw new Error("Inbox request failed");
        }
        return response.json();
      })
      .then(function (data) {
        renderInbox(data.messages, address, readKey);
      })
      .catch(function (err) {
        var container = document.getElementById("js-inbox-messages");
        if (container) {
          container.innerHTML = '<div class="error-box">Warning: ' + esc(err.message) + "</div>";
        }
      });
  }

  function renderInbox(messages, address, readKey) {
    var container = document.getElementById("js-inbox-messages");
    if (!container) {
      return;
    }

    if (!messages || messages.length === 0) {
      container.innerHTML =
        '<p class="subtle no-messages">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="messages-container">Messages (' + messages.length + ")</h3>";
    messages.forEach(function (msg) {
      html +=
        '<div class="msg-card">' +
        '<div class="msg-meta">From: ' +
        esc(msg.sender) +
        " &nbsp;|&nbsp; " +
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
        '">Delete</button>' +
        "</div></div>";
    });

    html +=
      '<div class="danger-zone">' +
      '<h3 class="danger-title">Danger Zone</h3>' +
      '<button type="button" class="danger js-destroy-mailbox"' +
      ' data-address="' +
      esc(address) +
      '"' +
      ' data-read-key="' +
      esc(readKey) +
      '">Destroy Mailbox</button>' +
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
        if (!confirm("Destroy mailbox and all messages permanently?")) {
          return;
        }
        destroyMailbox(btn.dataset.address, btn.dataset.readKey);
      });
    });
  }

  function deleteMsg(address, msgId, readKey) {
    var path = getPath();
    fetch(
      "/" +
        path +
        "/mail/" +
        encodeURIComponent(address) +
        "/delete/" +
        encodeURIComponent(msgId),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ read_key: readKey }),
      }
    )
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.success) {
          fetchInbox();
          return;
        }
        alert("Error: " + (data.error || "Could not delete"));
      })
      .catch(function () {
        alert("Delete request failed.");
      });
  }

  function destroyMailbox(address, readKey) {
    var path = getPath();
    fetch("/" + path + "/mail/" + encodeURIComponent(address) + "/destroy", {
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
        if (data.success) {
          var container = document.getElementById("js-inbox-messages");
          if (container) {
            container.innerHTML = '<div class="success-box">Success: Mailbox destroyed.</div>';
          }
          return;
        }
        alert("Error: " + (data.error || "Could not destroy mailbox"));
      })
      .catch(function () {
        alert("Destroy request failed.");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var defaultSection = document.body.getAttribute("data-default-section") || "create";
    showSection(defaultSection);

    document.querySelectorAll(".js-show-section").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showSection(btn.getAttribute("data-section"));
      });
    });

    var createBtn = document.getElementById("create-btn");
    if (createBtn) {
      createBtn.addEventListener("click", createMailbox);
    }

    document.querySelectorAll(".js-copy-target").forEach(function (btn) {
      btn.addEventListener("click", function () {
        copyText(btn.getAttribute("data-target"));
      });
    });

    var readForm = document.getElementById("read-form");
    if (readForm) {
      readForm.addEventListener("submit", function (event) {
        event.preventDefault();
        fetchInbox();
      });
    }

    document.querySelectorAll(".js-confirm-delete").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        if (!confirm("Delete this message?")) {
          event.preventDefault();
        }
      });
    });

    document.querySelectorAll(".js-confirm-destroy").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        if (!confirm("Destroy mailbox and all messages permanently?")) {
          event.preventDefault();
        }
      });
    });
  });
})();
