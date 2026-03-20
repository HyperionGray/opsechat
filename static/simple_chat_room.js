(function () {
    "use strict";

    let encryptionEnabled = false;
    let encryptionKey = null;
    let pollInterval = null;
    let securityWarningAccepted = sessionStorage.getItem("securityWarningAccepted") === "true";
    const lockPrefix = "🔒";

    function getRoomId() {
        return document.body.dataset.roomId;
    }

    function setUsernameColor() {
        const usernameEl = document.getElementById("myUsername");
        if (!usernameEl) {
            return;
        }

        const r = Number.parseInt(usernameEl.dataset.colorR || "0", 10);
        const g = Number.parseInt(usernameEl.dataset.colorG || "255", 10);
        const b = Number.parseInt(usernameEl.dataset.colorB || "0", 10);
        usernameEl.style.color = `rgb(${r}, ${g}, ${b})`;
    }

    function setWarningVisibility(visible) {
        const warning = document.getElementById("securityWarning");
        const messageInput = document.getElementById("messageInput");
        const sendBtn = document.getElementById("sendBtn");

        if (!warning || !messageInput || !sendBtn) {
            return;
        }

        warning.classList.toggle("is-hidden", !visible);
        messageInput.disabled = visible;
        sendBtn.disabled = visible;
    }

    function showSecurityWarning() {
        if (!securityWarningAccepted) {
            setWarningVisibility(true);
        }
    }

    function acceptSecurityWarning() {
        const messageInput = document.getElementById("messageInput");

        securityWarningAccepted = true;
        sessionStorage.setItem("securityWarningAccepted", "true");
        setWarningVisibility(false);

        if (messageInput) {
            messageInput.focus();
        }
    }

    async function importKey(keyArray) {
        return window.crypto.subtle.importKey(
            "raw",
            new Uint8Array(keyArray),
            {
                name: "AES-GCM",
                length: 256
            },
            true,
            ["encrypt", "decrypt"]
        );
    }

    async function fetchRoomKey() {
        const roomId = getRoomId();
        if (!roomId) {
            return false;
        }

        try {
            const response = await fetch(`/chat/room/${roomId}/key`);
            if (!response.ok) {
                return false;
            }

            const data = await response.json();
            const keyData = Uint8Array.from(atob(data.encryption_key), (c) => c.charCodeAt(0));
            encryptionKey = await importKey(Array.from(keyData));
            return true;
        } catch (error) {
            return false;
        }
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

        const combined = new Uint8Array(iv.length + encrypted.byteLength);
        combined.set(iv, 0);
        combined.set(new Uint8Array(encrypted), iv.length);
        return btoa(String.fromCharCode(...combined));
    }

    async function decryptMessage(encryptedMessage, key) {
        try {
            const combined = Uint8Array.from(atob(encryptedMessage), (c) => c.charCodeAt(0));
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
        } catch (error) {
            return "[Decryption failed]";
        }
    }

    function isEncrypted(message) {
        return typeof message === "string" && message.startsWith(lockPrefix);
    }

    function showStatus(message, duration = 3000) {
        const statusMsg = document.getElementById("statusMsg");
        if (!statusMsg) {
            return;
        }

        statusMsg.textContent = message;
        setTimeout(() => {
            statusMsg.textContent = "";
        }, duration);
    }

    function scrollToBottom() {
        const container = document.getElementById("messagesContainer");
        if (!container) {
            return;
        }

        container.scrollTop = container.scrollHeight;
    }

    async function renderMessages(messages) {
        const container = document.getElementById("messagesContainer");
        if (!container) {
            return;
        }

        container.innerHTML = "";

        for (const msg of messages) {
            const messageDiv = document.createElement("div");
            messageDiv.className = `message${msg.is_mine ? " mine" : ""}`;

            const usernameSpan = document.createElement("span");
            usernameSpan.className = "username";
            usernameSpan.style.color = `rgb(${msg.color[0]}, ${msg.color[1]}, ${msg.color[2]})`;
            usernameSpan.textContent = `${msg.username}:`;

            const messageText = document.createElement("span");

            if (isEncrypted(msg.message)) {
                const lockIcon = document.createElement("span");
                lockIcon.className = "lock-icon";
                lockIcon.textContent = `${lockPrefix} `;
                messageText.appendChild(lockIcon);

                if (encryptionEnabled && encryptionKey) {
                    const encryptedData = msg.message.substring(lockPrefix.length);
                    const decrypted = await decryptMessage(encryptedData, encryptionKey);
                    messageText.appendChild(document.createTextNode(decrypted));
                } else {
                    messageText.appendChild(document.createTextNode("[Encrypted - Enable encryption to view]"));
                }
            } else {
                messageText.textContent = msg.message;
            }

            messageDiv.appendChild(usernameSpan);
            messageDiv.appendChild(document.createTextNode(" "));
            messageDiv.appendChild(messageText);
            container.appendChild(messageDiv);
        }

        scrollToBottom();
    }

    async function sendMessage() {
        const roomId = getRoomId();
        const input = document.getElementById("messageInput");
        if (!roomId || !input) {
            return;
        }

        const message = input.value.trim();
        if (!message) {
            return;
        }

        let messageToSend = message;
        if (encryptionEnabled && encryptionKey) {
            messageToSend = `${lockPrefix}${await encryptMessage(message, encryptionKey)}`;
        }

        try {
            const response = await fetch(`/chat/room/${roomId}/messages`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ message: messageToSend })
            });

            if (response.ok) {
                input.value = "";
                await pollMessages();
                return;
            }

            let errorText = "Error sending message";
            try {
                const data = await response.json();
                if (data.error) {
                    errorText = data.error;
                }
            } catch (error) {
                errorText = "Error sending message";
            }
            showStatus(errorText);
        } catch (error) {
            showStatus(`Error: ${error.message}`);
        }
    }

    async function pollMessages() {
        const roomId = getRoomId();
        if (!roomId) {
            return;
        }

        try {
            const response = await fetch(`/chat/room/${roomId}/messages`);
            if (!response.ok) {
                return;
            }

            const data = await response.json();
            await renderMessages(data.messages);

            const userCount = document.getElementById("userCount");
            if (userCount) {
                userCount.textContent = `Users: ${data.user_count}`;
            }
        } catch (error) {
            // Ignore transient polling errors.
        }
    }

    async function handleEncryptionToggle(event) {
        const statusSpan = document.getElementById("encryptionStatus");
        if (!statusSpan) {
            return;
        }

        encryptionEnabled = event.target.checked;
        if (encryptionEnabled) {
            if (!encryptionKey) {
                showStatus("Fetching room encryption key...", 2000);
                const success = await fetchRoomKey();
                if (!success) {
                    showStatus("Failed to enable encryption. Try again.", 3000);
                    event.target.checked = false;
                    encryptionEnabled = false;
                    return;
                }

                showStatus("Encryption enabled with automatic key exchange.", 5000);
            }

            statusSpan.textContent = "Encryption: ON";
            statusSpan.className = "encryption-status enabled";
        } else {
            statusSpan.textContent = "Encryption: OFF";
            statusSpan.className = "encryption-status";
        }

        await pollMessages();
    }

    async function initialize() {
        setUsernameColor();
        showSecurityWarning();

        const sendBtn = document.getElementById("sendBtn");
        const messageInput = document.getElementById("messageInput");
        const encryptionToggle = document.getElementById("encryptionToggle");
        const securityWarningAcceptBtn = document.getElementById("securityWarningAcceptBtn");

        if (sendBtn) {
            sendBtn.addEventListener("click", sendMessage);
        }

        if (securityWarningAcceptBtn) {
            securityWarningAcceptBtn.addEventListener("click", acceptSecurityWarning);
        }

        if (messageInput) {
            messageInput.addEventListener("keypress", (event) => {
                if (event.key === "Enter") {
                    sendMessage();
                }
            });
        }

        if (encryptionToggle) {
            encryptionToggle.addEventListener("change", handleEncryptionToggle);
        }

        const keyFetched = await fetchRoomKey();
        if (keyFetched && encryptionToggle) {
            encryptionToggle.checked = true;
            encryptionEnabled = true;

            const encryptionStatus = document.getElementById("encryptionStatus");
            if (encryptionStatus) {
                encryptionStatus.textContent = "Encryption: ON";
                encryptionStatus.className = "encryption-status enabled";
            }
        }

        await pollMessages();
        pollInterval = window.setInterval(pollMessages, 2000);
    }

    window.addEventListener("load", initialize);
    window.addEventListener("beforeunload", () => {
        if (pollInterval) {
            clearInterval(pollInterval);
        }
    });
})();
