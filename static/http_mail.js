(function () {
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  }

  function copyTextFromElementId(elementId) {
    var el = document.getElementById(elementId);
    if (!el) {
      return;
    }
    var text = el.textContent || '';
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
    } catch (e) {
      // Ignore clipboard fallback errors; UI remains usable.
    }
    document.body.removeChild(ta);
  }

  function getBootstrapConfig() {
    var bootstrap = document.getElementById('http-mail-bootstrap');
    if (!bootstrap) {
      return { path: '', initialSection: 'create' };
    }
    return {
      path: bootstrap.getAttribute('data-path') || '',
      initialSection: bootstrap.getAttribute('data-initial-section') || 'create',
    };
  }

  function showSection(name) {
    ['create', 'compose', 'read'].forEach(function (s) {
      var el = document.getElementById(s + '-section');
      if (el) {
        el.style.display = (s === name) ? 'block' : 'none';
      }
    });
  }

  function bindDeleteAndDestroyButtons(container, path, refetchInbox) {
    container.querySelectorAll('.js-delete-msg').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!window.confirm('Delete this message?')) {
          return;
        }
        fetch('/' + path + '/mail/' + encodeURIComponent(btn.dataset.address) +
              '/delete/' + encodeURIComponent(btn.dataset.msgId), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({ read_key: btn.dataset.readKey }),
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d.success) {
              refetchInbox();
            } else {
              alert('Error: ' + (d.error || 'Could not delete message.'));
            }
          });
      });
    });

    container.querySelectorAll('.js-destroy-mailbox').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!window.confirm('Destroy mailbox and all messages permanently?')) {
          return;
        }
        fetch('/' + path + '/mail/' + encodeURIComponent(btn.dataset.address) + '/destroy', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({ read_key: btn.dataset.readKey }),
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d.success) {
              container.innerHTML = '<div class="success-box">Success: Mailbox destroyed.</div>';
            } else {
              alert('Error: ' + (d.error || 'Could not destroy mailbox.'));
            }
          });
      });
    });
  }

  function renderInbox(messages, address, readKey, path, refetchInbox) {
    var container = document.getElementById('js-inbox-messages');
    if (!container) {
      return;
    }

    if (!Array.isArray(messages) || messages.length === 0) {
      container.innerHTML = '<p class="empty-inbox">No messages in this mailbox.</p>';
      return;
    }

    var html = '<h3 class="server-messages">Messages (' + messages.length + ')</h3>';
    messages.forEach(function (msg) {
      html += (
        '<div class="msg-card">' +
          '<div class="msg-meta">From: ' + esc(msg.sender) + ' &nbsp;|&nbsp; ' + esc(msg.timestamp) + '</div>' +
          '<div class="msg-subject">' + esc(msg.subject) + '</div>' +
          '<div class="msg-body">' + esc(msg.body) + '</div>' +
          '<div class="msg-actions">' +
            '<button type="button" class="danger js-delete-msg"' +
            ' data-address="' + esc(address) + '"' +
            ' data-msg-id="' + esc(msg.id) + '"' +
            ' data-read-key="' + esc(readKey) + '">Delete</button>' +
          '</div>' +
        '</div>'
      );
    });

    html += (
      '<div class="danger-zone">' +
        '<h3 class="danger-zone-title">Danger Zone</h3>' +
        '<button type="button" class="danger js-destroy-mailbox"' +
        ' data-address="' + esc(address) + '"' +
        ' data-read-key="' + esc(readKey) + '">Destroy Mailbox</button>' +
      '</div>'
    );

    container.innerHTML = html;
    bindDeleteAndDestroyButtons(container, path, refetchInbox);
  }

  function bindServerConfirmButtons() {
    document.querySelectorAll('[data-confirm-message]').forEach(function (btn) {
      btn.addEventListener('click', function (evt) {
        var msg = btn.getAttribute('data-confirm-message');
        if (msg && !window.confirm(msg)) {
          evt.preventDefault();
        }
      });
    });
  }

  function init() {
    var cfg = getBootstrapConfig();
    var path = cfg.path;

    var readAddress = document.getElementById('read-address');
    var readKeyInput = document.getElementById('read-key-input');
    var composeAddressInput = document.getElementById('compose-address-input');
    var createBtn = document.getElementById('create-btn');

    function fetchInbox() {
      var address = readAddress ? readAddress.value.trim() : '';
      var readKey = readKeyInput ? readKeyInput.value.trim() : '';
      var container = document.getElementById('js-inbox-messages');

      if (!address || !readKey) {
        if (container) {
          container.innerHTML = '<div class="error-box">Warning: mailbox address and read key are required.</div>';
        }
        return;
      }

      var url = '/' + path + '/mail/' + encodeURIComponent(address) +
                '/inbox?key=' + encodeURIComponent(readKey);
      fetch(url, { headers: { 'Accept': 'application/json' } })
        .then(function (r) {
          if (r.status === 403) {
            throw new Error('Invalid read key - access denied.');
          }
          if (r.status === 404) {
            throw new Error('Mailbox not found.');
          }
          return r.json();
        })
        .then(function (data) {
          renderInbox(data.messages, address, readKey, path, fetchInbox);
        })
        .catch(function (err) {
          if (container) {
            container.innerHTML = '<div class="error-box">Warning: ' + esc(err.message) + '</div>';
          }
        });
    }

    function createMailbox() {
      if (!createBtn) {
        return;
      }
      createBtn.disabled = true;
      createBtn.textContent = 'Creating...';

      fetch('/' + path + '/mail/new', {
        method: 'POST',
        headers: { 'Accept': 'application/json' },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.success) {
            throw new Error(data.error || 'Mailbox creation failed.');
          }
          var address = document.getElementById('result-address');
          var readKey = document.getElementById('result-read-key');
          var sendUrl = document.getElementById('result-send-url');
          var result = document.getElementById('new-mailbox-result');
          if (address) {
            address.textContent = data.address || '';
          }
          if (readKey) {
            readKey.textContent = data.read_key || '';
          }
          if (sendUrl) {
            sendUrl.textContent = window.location.origin + (data.send_url || '');
          }
          if (result) {
            result.style.display = 'block';
          }
          if (composeAddressInput && data.address) {
            composeAddressInput.value = data.address;
          }
          if (readAddress && data.address) {
            readAddress.value = data.address;
          }
          if (readKeyInput && data.read_key) {
            readKeyInput.value = data.read_key;
          }
        })
        .catch(function (err) {
          alert('Error: ' + err.message);
        })
        .finally(function () {
          createBtn.disabled = false;
          createBtn.textContent = 'Create Mailbox';
        });
    }

    var showCreateBtn = document.getElementById('show-create-btn');
    var showComposeBtn = document.getElementById('show-compose-btn');
    var showReadBtn = document.getElementById('show-read-btn');
    var openInboxBtn = document.getElementById('open-inbox-btn');

    if (showCreateBtn) {
      showCreateBtn.addEventListener('click', function () { showSection('create'); });
    }
    if (showComposeBtn) {
      showComposeBtn.addEventListener('click', function () { showSection('compose'); });
    }
    if (showReadBtn) {
      showReadBtn.addEventListener('click', function () { showSection('read'); });
    }
    if (openInboxBtn) {
      openInboxBtn.addEventListener('click', fetchInbox);
    }
    if (createBtn) {
      createBtn.addEventListener('click', createMailbox);
    }

    document.querySelectorAll('[data-copy-target]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        copyTextFromElementId(btn.getAttribute('data-copy-target'));
      });
    });

    bindServerConfirmButtons();
    showSection(cfg.initialSection);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
