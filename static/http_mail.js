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

function getPathPrefix() {
  return document.body.dataset.path || "";
}

function updateComposeAction() {
  var addrInput = document.getElementById("compose-address-input");
  var form = document.getElementById("compose-form");
  if (!addrInput || !form) {
    return;
  }
  var addr = addrInput.value.trim();
  if (!addr) {
    return;
  }
  form.action = "/" + getPathPrefix() + "/mail/" + encodeURIComponent(addr) + "/send";
}

function createMailbox() {
  var btn = document.getElementById("create-btn");
  if (!btn) {
    return;
  }
  btn.disabled = true;
  btn.textContent = "Creating...";

  fetch("/" + getPathPrefix() + "/mail/new", {
    method: "POST",
    headers: { Accept: "application/json" }
  })
    .then(function (response) { return response.json(); })
    .then(function (data) {
      if (!data.success) {
        alert("Error: " + (data.error || "Unknown error"));
        return;
      }
      document.getElementById("result-address").textContent = data.address;
      document.getElementById("result-read-key").textContent = data.read_key;
      document.getElementById("result-send-url").textContent = window.location.origin + data.send_url;
      document.getElementById("new-mailbox-result").classList.remove("hidden");
    })
    .catch(function (err) {
      alert("Request failed: " + err);
    })
    .finally(function () {
      btn.disabled = false;
      btn.textContent = "Create mailbox";
    });
}

function getFilterValue(id) {
  var el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

function getInboxRequestParams(readKey) {
  var params = new URLSearchParams();
  params.set("key", readKey);

  var sender = getFilterValue("read-filter-sender");
  var subject = getFilterValue("read-filter-subject");
  var since = getFilterValue("read-filter-since");
  var limit = getFilterValue("read-filter-limit");
  var offset = getFilterValue("read-filter-offset");
  var order = getFilterValue("read-filter-order") || "desc";

  if (sender) {
    params.set("sender", sender);
  }
  if (subject) {
    params.set("subject", subject);
  }
  if (since) {
    params.set("since", since);
  }
  if (limit) {
    params.set("limit", limit);
  }
  if (offset) {
    params.set("offset", offset);
  }
  if (order) {
    params.set("order", order);
  }

  return params;
}

function fetchInbox() {
  var address = getFilterValue("read-address");
  var readKey = getFilterValue("read-key-input");

  if (!address || !readKey) {
    alert("Please enter both mailbox address and read key.");
    return;
  }

  var params = getInboxRequestParams(readKey);
  var url = "/" + getPathPrefix() + "/mail/" + encodeURIComponent(address) + "/inbox?" + params.toString();

  fetch(url, { headers: { Accept: "application/json" } })
    .then(function (response) {
      if (response.status === 403) {
        throw new Error("Invalid read key - access denied");
      }
      if (response.status === 404) {
        throw new Error("Mailbox not found");
      }
      if (response.status === 400) {
        return response.json().then(function (body) {
          throw new Error(body.error || "Invalid request");
        });
      }
      return response.json();
    })
    .then(function (data) {
      renderInbox(data, address, readKey);
    })
    .catch(function (err) {
      var container = document.getElementById("js-inbox-messages");
      container.innerHTML = "<div class=\"error-box\">" + esc(err.message) + "</div>";
    });
}

function renderInbox(data, address, readKey) {
  var messages = data.messages || [];
  var container = document.getElementById("js-inbox-messages");
  if (!container) {
    return;
  }

  if (!messages.length) {
    container.innerHTML = "<p class=\"muted top-gap\">No messages in this mailbox.</p>";
    return;
  }

  var total = Number(data.total_messages || messages.length);
  var returned = Number(data.returned_messages || messages.length);
  var html = "<h3 class=\"top-gap\">Messages (" + returned + " shown / " + total + " total)</h3>";

  messages.forEach(function (msg) {
    html +=
      "<div class=\"msg-card\">" +
        "<div class=\"msg-meta\">From: " + esc(msg.sender) + " | " + esc(msg.timestamp) + "</div>" +
        "<div class=\"msg-subject\">" + esc(msg.subject) + "</div>" +
        "<div class=\"msg-body\">" + esc(msg.body) + "</div>" +
        "<div class=\"msg-actions\">" +
          "<button type=\"button\" class=\"danger js-delete-msg\"" +
              " data-address=\"" + esc(address) + "\"" +
              " data-msg-id=\"" + esc(msg.id) + "\"" +
              " data-read-key=\"" + esc(readKey) + "\">Delete</button>" +
        "</div>" +
      "</div>";
  });

  html +=
    "<div class=\"danger-zone\">" +
      "<h3 class=\"danger-title\">Danger zone</h3>" +
      "<button type=\"button\" class=\"danger js-destroy-mailbox\"" +
        " data-address=\"" + esc(address) + "\"" +
        " data-read-key=\"" + esc(readKey) + "\">Destroy mailbox</button>" +
    "</div>";

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

function deleteMessage(address, msgId, readKey) {
  fetch("/" + getPathPrefix() + "/mail/" + encodeURIComponent(address) + "/delete/" + encodeURIComponent(msgId), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: JSON.stringify({ read_key: readKey })
  })
    .then(function (response) { return response.json(); })
    .then(function (body) {
      if (!body.success) {
        throw new Error(body.error || "Could not delete message");
      }
      fetchInbox();
    })
    .catch(function (err) {
      alert(err.message);
    });
}

function destroyMailbox(address, readKey) {
  fetch("/" + getPathPrefix() + "/mail/" + encodeURIComponent(address) + "/destroy", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: JSON.stringify({ read_key: readKey })
  })
    .then(function (response) { return response.json(); })
    .then(function (body) {
      if (!body.success) {
        throw new Error(body.error || "Could not destroy mailbox");
      }
      var container = document.getElementById("js-inbox-messages");
      container.innerHTML = "<div class=\"success-box\">Mailbox destroyed.</div>";
    })
    .catch(function (err) {
      alert(err.message);
    });
}

function copyText(targetId) {
  var source = document.getElementById(targetId);
  if (!source) {
    return;
  }
  var text = source.textContent || "";
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () {
      alert("Copied");
    });
    return;
  }

  var ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "readonly");
  ta.className = "hidden";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  alert("Copied");
}

function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".section-button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      showSection(btn.dataset.section);
    });
  });

  var composeAddress = document.getElementById("compose-address-input");
  if (composeAddress) {
    composeAddress.addEventListener("input", updateComposeAction);
    updateComposeAction();
  }

  var createBtn = document.getElementById("create-btn");
  if (createBtn) {
    createBtn.addEventListener("click", createMailbox);
  }

  var readBtn = document.getElementById("open-inbox-btn");
  if (readBtn) {
    readBtn.addEventListener("click", fetchInbox);
  }

  document.querySelectorAll(".copy-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      copyText(btn.dataset.copyTarget);
    });
  });

  document.querySelectorAll(".confirm-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm("Delete this message?")) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll(".confirm-destroy-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm("Destroy mailbox and all messages permanently?")) {
        event.preventDefault();
      }
    });
  });

  if (document.body.dataset.hasMessages === "1") {
    showSection("read");
  } else if (document.body.dataset.hasCompose === "1") {
    showSection("compose");
  } else {
    showSection("create");
  }
});
