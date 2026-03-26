// HTTP Mail front-end behavior.
(function () {
  'use strict';

  var body = document.body;
  var path = body ? body.getAttribute('data-path') || '' : '';
  var initialSection = body ? body.getAttribute('data-initial-section') || 'create' : 'create';

  function byId(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  }

  function pathPrefix() {
    return '/' + encodeURIComponent(path);
  }

  function showSection(name) {
    ['create', 'compose', 'read'].forEach(function (section) {
      var el = byId(section + '-section');
      if (el) {
        el.style.display = section === name ? 'block' : 'none';
      }
    });
  }

  function copyTextFromElement(elementId) {
    var target = byId(elementId);
    if (!target) {
      return;
    }
    var text = target.textContent || '';
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        alert('Copied.');
      });
      return;
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      alert('Copied.');
    } catch (_err) {
      // no-op
    }
    document.body.removeChild(ta);
  }

  function createMailbox() {
    var btn = byId('create-btn');
    var resultBox = byId('new-mailbox-result');
    if (!btn || !resultBox) {
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Creating...';

    fetch(pathPrefix() + '/mail/new', {
      method: 'POST',
      headers: { Accept: 'application/json' }
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.success) {
          throw new Error(data.error || 'Unknown error');
        }
        byId('result-address').textContent = data.address;
        byId('result-read-key').textContent = data.read_key;
        byId('result-send-url').textContent = window.location.origin + data.send_url;
        resultBox.style.display = 'block';
        btn.textContent = 'Create Another Mailbox';
      })
      .catch(function (err) {
        alert('Error: ' + err.message);
        btn.textContent = 'Create Mailbox';
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  function updateComposeAction() {
    var addressInput = byId('compose-address-input');
    var form = byId('compose-form');
    if (!addressInput || !form) {
      return;
    }
    var address = addressInput.value.trim();
    if (address) {
      form.action = pathPrefix() + '/mail/' + encodeURIComponent(address) + '/send';
    } else {
      form.action = pathPrefix() + '/mail/send';
    }
  }

  function fetchInbox() {
    var addressInput = byId('read-address');
    var keyInput = byId('read-key-input');
    var out = byId('js-inbox-messages');
    var rotateAddressInput = byId('rotate-address');
    var rotateKeyInput = byId('rotate-read-key');
    if (!addressInput || !keyInput || !out) {
      return;
    }

    var address = addressInput.value.trim();
    var readKey = keyInput.value.trim();
    if (!address || !readKey) {
      alert('Please enter both mailbox address and read key.');
      return;
    }

    fetch(pathPrefix() + '/mail/' + encodeURIComponent(address) + '/inbox?key=' + encodeURIComponent(readKey), {
      headers: { Accept: 'application/json' }
    })
      .then(function (r) {
        if (r.status === 403) {
          throw new Error('Invalid read key - access denied');
        }
        if (r.status === 404) {
          throw new Error('Mailbox not found');
        }
        return r.json();
      })
      .then(function (data) {
        if (rotateAddressInput) {
          rotateAddressInput.value = address;
        }
        if (rotateKeyInput) {
          rotateKeyInput.value = readKey;
        }
        renderInbox(data.messages, address, readKey);
      })
      .catch(function (err) {
        out.innerHTML = '<div class="error-box">Warning: ' + esc(err.message) + '</div>';
      });
  }

  function deleteMessage(address, msgId, readKey) {
    fetch(pathPrefix() + '/mail/' + encodeURIComponent(address) + '/delete/' + encodeURIComponent(msgId), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.success) {
          throw new Error(data.error || 'Could not delete message');
        }
        fetchInbox();
      })
      .catch(function (err) {
        alert('Error: ' + err.message);
      });
  }

  function destroyMailbox(address, readKey) {
    fetch(pathPrefix() + '/mail/' + encodeURIComponent(address) + '/destroy', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.success) {
          throw new Error(data.error || 'Could not destroy mailbox');
        }
        var out = byId('js-inbox-messages');
        if (out) {
          out.innerHTML = '<div class="success-box">Mailbox destroyed.</div>';
        }
      })
      .catch(function (err) {
        alert('Error: ' + err.message);
      });
  }

  function renderInbox(messages, address, readKey) {
    var out = byId('js-inbox-messages');
    if (!out) {
      return;
    }

    if (!Array.isArray(messages) || messages.length === 0) {
      out.innerHTML = '<p class="muted-text mt-10">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="mt-20">Messages (' + messages.length + ')</h3>';
    messages.forEach(function (msg) {
      html +=
        '<div class="msg-card">' +
        '<div class="msg-meta">From: ' + esc(msg.sender) + ' | ' + esc(msg.timestamp) + '</div>' +
        '<div class="msg-subject">' + esc(msg.subject) + '</div>' +
        '<div class="msg-body">' + esc(msg.body) + '</div>' +
        '<div class="msg-actions">' +
        '<button type="button" class="danger js-delete-msg" data-address="' + esc(address) +
        '" data-msg-id="' + esc(msg.id) + '" data-read-key="' + esc(readKey) + '">Delete</button>' +
        '</div></div>';
    });

    html +=
      '<div class="danger-zone">' +
      '<h3 class="danger-title">Danger Zone</h3>' +
      '<button type="button" class="danger js-destroy-mailbox" data-address="' + esc(address) +
      '" data-read-key="' + esc(readKey) + '">Destroy Mailbox</button>' +
      '</div>';

    out.innerHTML = html;

    out.querySelectorAll('.js-delete-msg').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!confirm('Delete this message?')) {
          return;
        }
        deleteMessage(btn.dataset.address, btn.dataset.msgId, btn.dataset.readKey);
      });
    });

    out.querySelectorAll('.js-destroy-mailbox').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!confirm('Destroy mailbox and all messages permanently?')) {
          return;
        }
        destroyMailbox(btn.dataset.address, btn.dataset.readKey);
      });
    });
  }

  function rotateReadKey() {
    var addressInput = byId('rotate-address');
    var keyInput = byId('rotate-read-key');
    var status = byId('rotate-key-status');
    var readKeyInput = byId('read-key-input');
    if (!addressInput || !keyInput || !status) {
      return;
    }

    var address = addressInput.value.trim();
    var readKey = keyInput.value.trim();
    if (!address || !readKey) {
      status.innerHTML = '<div class="error-box">Address and current read key are required.</div>';
      return;
    }

    fetch(pathPrefix() + '/mail/' + encodeURIComponent(address) + '/rotate-key', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify({ read_key: readKey })
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { status: r.status, data: data };
        });
      })
      .then(function (result) {
        if (result.status !== 200 || !result.data.success) {
          throw new Error(result.data.error || 'Could not rotate key');
        }
        var newReadKey = result.data.new_read_key;
        keyInput.value = newReadKey;
        if (readKeyInput) {
          readKeyInput.value = newReadKey;
        }
        status.innerHTML = '<div class="success-box">Read key rotated. Save the new key now.</div>';
      })
      .catch(function (err) {
        status.innerHTML = '<div class="error-box">Error: ' + esc(err.message) + '</div>';
      });
  }

  function bindStaticHandlers() {
    var composeAddress = byId('compose-address-input');
    var createBtn = byId('create-btn');
    var openInboxBtn = byId('open-inbox-btn');
    var rotateBtn = byId('rotate-key-btn');
    var toggleCreate = byId('toggle-create');
    var toggleCompose = byId('toggle-compose');
    var toggleRead = byId('toggle-read');

    if (composeAddress) {
      composeAddress.addEventListener('input', updateComposeAction);
      updateComposeAction();
    }
    if (createBtn) {
      createBtn.addEventListener('click', createMailbox);
    }
    if (openInboxBtn) {
      openInboxBtn.addEventListener('click', fetchInbox);
    }
    if (rotateBtn) {
      rotateBtn.addEventListener('click', rotateReadKey);
    }
    if (toggleCreate) {
      toggleCreate.addEventListener('click', function () {
        showSection('create');
      });
    }
    if (toggleCompose) {
      toggleCompose.addEventListener('click', function () {
        showSection('compose');
      });
    }
    if (toggleRead) {
      toggleRead.addEventListener('click', function () {
        showSection('read');
      });
    }

    document.querySelectorAll('.copy-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var targetId = btn.getAttribute('data-copy-target');
        if (targetId) {
          copyTextFromElement(targetId);
        }
      });
    });

    document.querySelectorAll('.js-confirm-delete').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!confirm('Delete this message?')) {
          event.preventDefault();
        }
      });
    });
    document.querySelectorAll('.js-confirm-destroy').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!confirm('Destroy mailbox and all messages permanently?')) {
          event.preventDefault();
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindStaticHandlers();
    if (initialSection === 'read') {
      showSection('read');
    } else if (initialSection === 'compose') {
      showSection('compose');
    } else {
      showSection('create');
    }
  });
})();
