// Simple E2E encryption using Web Crypto API (reviewable and minimal)
// room_id is read from the data-room-id attribute on <body>
const roomId = document.body.dataset.roomId;
let encryptionEnabled = false;
let encryptionKey = null;
let pollInterval = null;
let securityWarningAccepted = sessionStorage.getItem('securityWarningAccepted') === 'true';

// Encrypted message prefix (ASCII-safe, recognised by both client and server)
const ENC_PREFIX = 'ENC:';

// Show security warning on first load
function showSecurityWarning() {
    if (!securityWarningAccepted) {
        document.getElementById('securityWarning').style.display = 'block';
        document.getElementById('messageInput').disabled = true;
        document.getElementById('sendBtn').disabled = true;
    }
}

function acceptSecurityWarning() {
    securityWarningAccepted = true;
    sessionStorage.setItem('securityWarningAccepted', 'true');
    document.getElementById('securityWarning').style.display = 'none';
    document.getElementById('messageInput').disabled = false;
    document.getElementById('sendBtn').disabled = false;
    document.getElementById('messageInput').focus();
}

// Automated key exchange - fetch room's shared key
async function fetchRoomKey() {
    try {
        const response = await fetch(`/chat/room/${roomId}/key`);
        if (response.ok) {
            const data = await response.json();
            // Import the room's key
            const keyData = Uint8Array.from(atob(data.encryption_key), c => c.charCodeAt(0));
            encryptionKey = await importKey(Array.from(keyData));
            return true;
        }
    } catch (e) {
        console.error('Failed to fetch room key:', e);
    }
    return false;
}

// Simple encryption using AES-GCM with Web Crypto API
async function generateKey() {
    const key = await window.crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256
        },
        true,
        ["encrypt", "decrypt"]
    );
    return key;
}

async function exportKey(key) {
    const exported = await window.crypto.subtle.exportKey("raw", key);
    return Array.from(new Uint8Array(exported));
}

async function importKey(keyArray) {
    const key = await window.crypto.subtle.importKey(
        "raw",
        new Uint8Array(keyArray),
        {
            name: "AES-GCM",
            length: 256
        },
        true,
        ["encrypt", "decrypt"]
    );
    return key;
}

async function encryptMessage(message, key) {
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(message);

    const encrypted = await window.crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: iv
        },
        key,
        encoded
    );

    // Combine IV and encrypted data
    const combined = new Uint8Array(iv.length + encrypted.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(encrypted), iv.length);

    // Return as base64
    return btoa(String.fromCharCode(...combined));
}

async function decryptMessage(encryptedMessage, key) {
    try {
        // Decode from base64
        const combined = Uint8Array.from(atob(encryptedMessage), c => c.charCodeAt(0));

        // Extract IV and encrypted data
        const iv = combined.slice(0, 12);
        const data = combined.slice(12);

        const decrypted = await window.crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: iv
            },
            key,
            data
        );

        return new TextDecoder().decode(decrypted);
    } catch (e) {
        return "[Decryption failed]";
    }
}

function isEncrypted(message) {
    return message.startsWith(ENC_PREFIX);
}

// UI functions
function showStatus(message, duration = 3000) {
    const statusMsg = document.getElementById('statusMsg');
    statusMsg.textContent = message;
    setTimeout(() => {
        statusMsg.textContent = '';
    }, duration);
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    container.scrollTop = container.scrollHeight;
}

function formatDuration(seconds) {
    const clamped = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(clamped / 60);
    const remaining = clamped % 60;
    return `${minutes}m ${remaining}s`;
}

async function renderMessages(messages) {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = '';

    for (const msg of messages) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message' + (msg.is_mine ? ' mine' : '');

        const usernameSpan = document.createElement('span');
        usernameSpan.className = 'username';
        usernameSpan.style.color = `rgb(${msg.color[0]}, ${msg.color[1]}, ${msg.color[2]})`;
        usernameSpan.textContent = msg.username + ':';

        const messageText = document.createElement('span');

        // Check if message is encrypted
        if (isEncrypted(msg.message)) {
            const lockIcon = document.createElement('span');
            lockIcon.className = 'lock-icon';
            lockIcon.textContent = '\uD83D\uDD12 ';
            messageText.appendChild(lockIcon);

            if (encryptionEnabled && encryptionKey) {
                const encryptedData = msg.message.substring(ENC_PREFIX.length);
                const decrypted = await decryptMessage(encryptedData, encryptionKey);
                messageText.appendChild(document.createTextNode(decrypted));
            } else {
                messageText.appendChild(document.createTextNode('[Encrypted - Enable encryption to view]'));
            }
        } else {
            messageText.textContent = msg.message;
        }

        messageDiv.appendChild(usernameSpan);
        messageDiv.appendChild(document.createTextNode(' '));
        messageDiv.appendChild(messageText);

        container.appendChild(messageDiv);
    }

    scrollToBottom();
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message) return;

    let messageToSend = message;

    // Encrypt if enabled
    if (encryptionEnabled && encryptionKey) {
        messageToSend = ENC_PREFIX + await encryptMessage(message, encryptionKey);
    }

    try {
        const response = await fetch(`/chat/room/${roomId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: messageToSend })
        });

        if (response.ok) {
            input.value = '';
            await pollMessages();
        } else {
            showStatus('Error sending message');
        }
    } catch (error) {
        showStatus('Error: ' + error.message);
    }
}

async function pollMessages() {
    try {
        const response = await fetch(`/chat/room/${roomId}/messages`);

        if (response.ok) {
            const data = await response.json();
            await renderMessages(data.messages);
            const userCount = Number(data.user_count) || 0;
            const expiresIn = formatDuration(data.room_expires_in_seconds);
            document.getElementById('userCount').textContent = `Users: ${userCount} | Room expires in: ${expiresIn}`;
        }
    } catch (error) {
        // Silently fail for polling errors
    }
}

// Event listeners
document.getElementById('sendBtn').addEventListener('click', sendMessage);

document.getElementById('messageInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

document.getElementById('encryptionToggle').addEventListener('change', async function(e) {
    encryptionEnabled = e.target.checked;
    const statusSpan = document.getElementById('encryptionStatus');

    if (encryptionEnabled) {
        if (!encryptionKey) {
            // Automatically fetch the room's shared key
            showStatus('Fetching room encryption key...', 2000);
            const success = await fetchRoomKey();

            if (success) {
                showStatus('Encryption enabled with automatic key exchange. All messages in this room use the same key.', 5000);
            } else {
                showStatus('Failed to enable encryption. Try again.', 3000);
                e.target.checked = false;
                encryptionEnabled = false;
                return;
            }
        }
        statusSpan.textContent = 'Encryption: ON';
        statusSpan.className = 'encryption-status enabled';
    } else {
        statusSpan.textContent = 'Encryption: OFF';
        statusSpan.className = 'encryption-status';
    }

    // Re-render messages with new encryption status
    await pollMessages();
});

// Check for existing key on load
window.addEventListener('load', async function() {
    // Show security warning first
    showSecurityWarning();

    // Auto-enable encryption with room key
    const keyFetched = await fetchRoomKey();
    if (keyFetched) {
        document.getElementById('encryptionToggle').checked = true;
        encryptionEnabled = true;
        document.getElementById('encryptionStatus').textContent = 'Encryption: ON';
        document.getElementById('encryptionStatus').className = 'encryption-status enabled';
    }

    // Start polling
    await pollMessages();
    pollInterval = setInterval(pollMessages, 2000);
});

// Cleanup on unload
window.addEventListener('beforeunload', function() {
    if (pollInterval) {
        clearInterval(pollInterval);
    }
});

// Expose acceptSecurityWarning for the HTML onclick attribute
window.acceptSecurityWarning = acceptSecurityWarning;
