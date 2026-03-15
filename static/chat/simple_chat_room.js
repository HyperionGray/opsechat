(() => {
    const body = document.body;
    const roomId = body.dataset.roomId;
    const usernameColor = [
        Number(body.dataset.colorR || 0),
        Number(body.dataset.colorG || 255),
        Number(body.dataset.colorB || 0)
    ];

    const usernameDisplay = document.getElementById("usernameDisplay");
    const messagesContainer = document.getElementById("messagesContainer");
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const userCount = document.getElementById("userCount");
    const encryptionToggle = document.getElementById("encryptionToggle");
    const encryptionStatus = document.getElementById("encryptionStatus");
    const statusMsg = document.getElementById("statusMsg");
    const securityWarning = document.getElementById("securityWarning");
    const acceptSecurityWarningBtn = document.getElementById("acceptSecurityWarningBtn");

    if (!roomId || !messagesContainer || !messageInput || !sendBtn) {
        return;
    }

    if (usernameDisplay) {
        usernameDisplay.style.color = `rgb(${usernameColor[0]}, ${usernameColor[1]}, ${usernameColor[2]})`;
    }

    let encryptionEnabled = false;
    let encryptionKey = null;
    let pollInterval = null;
    let securityWarningAccepted = sessionStorage.getItem("securityWarningAccepted") === "true";
    const encryptedPrefix = "ENC:";

    function setComposerEnabled(enabled) {
        messageInput.disabled = !enabled;
        sendBtn.disabled = !enabled;
        if (enabled) {
            messageInput.focus();
        }
    }

    function showSecurityWarning() {
        if (!securityWarning || securityWarningAccepted) {
            return;
        }

        securityWarning.classList.remove("is-hidden");
        setComposerEnabled(false);
    }

    function acceptSecurityWarning() {
        securityWarningAccepted = true;
        sessionStorage.setItem("securityWarningAccepted", "true");
        if (securityWarning) {
            securityWarning.classList.add("is-hidden");
        }
        setComposerEnabled(true);
    }

    async function importKey(keyArray) {
        return window.crypto.subtle.importKey(
            "raw",
            new Uint8Array(keyArray),
            { name: "AES-GCM", length: 256 },
            true,
            ["encrypt", "decrypt"]
        );
    }

    async function fetchRoomKey() {
        try {
            const response = await fetch(`/chat/room/${roomId}/key`);
            if (!response.ok) {
                return false;
            }

            const data = await response.json();
            const keyData = Uint8Array.from(atob(data.encryption_key), (c) => c.charCodeAt(0));
            encryptionKey = await importKey(Array.from(keyData));
            return true;
        } catch (_error) {
            return false;
        }
    }

    async function encryptMessage(message, key) {
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const encoded = new TextEncoder().encode(message);
        const encrypted = await window.crypto.subtle.encrypt(
            { name: "AES-GCM", iv },
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
            const encryptedData = combined.slice(12);
            const decrypted = await window.crypto.subtle.decrypt(
                { name: "AES-GCM", iv },
                key,
                encryptedData
            );
            return new TextDecoder().decode(decrypted);
        } catch (_error) {
            return "[Decryption failed]";
        }
    }

    function isEncrypted(message) {
        return typeof message === "string" && message.startsWith(encryptedPrefix);
    }

    function showStatus(message, duration = 3000) {
        if (!statusMsg) {
            return;
        }

        statusMsg.textContent = message;
        window.setTimeout(() => {
            statusMsg.textContent = "";
        }, duration);
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    async function renderMessages(messages) {
        messagesContainer.innerHTML = "";

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
                lockIcon.textContent = "🔒 ";
                messageText.appendChild(lockIcon);

                if (encryptionEnabled && encryptionKey) {
                    const encryptedData = msg.message.substring(encryptedPrefix.length);
                    const decrypted = await decryptMessage(encryptedData, encryptionKey);
                    messageText.appendChild(document.createTextNode(decrypted));
                } else {
                    messageText.appendChild(
                        document.createTextNode("[Encrypted - Enable encryption to view]")
                    );
                }
            } else {
                messageText.textContent = msg.message;
            }

            messageDiv.appendChild(usernameSpan);
            messageDiv.appendChild(document.createTextNode(" "));
            messageDiv.appendChild(messageText);
            messagesContainer.appendChild(messageDiv);
        }

        scrollToBottom();
    }

    async function sendMessage() {
        if (!securityWarningAccepted) {
            showStatus("Accept the security notice before sending messages.");
            return;
        }

        const message = messageInput.value.trim();
        if (!message) {
            return;
        }

        let messageToSend = message;
        if (encryptionEnabled && encryptionKey) {
            messageToSend = `${encryptedPrefix}${await encryptMessage(message, encryptionKey)}`;
        }

        try {
            const response = await fetch(`/chat/room/${roomId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: messageToSend })
            });

            if (!response.ok) {
                showStatus("Error sending message");
                return;
            }

            messageInput.value = "";
            await pollMessages();
        } catch (error) {
            showStatus(`Error: ${error.message}`);
        }
    }

    async function pollMessages() {
        try {
            const response = await fetch(`/chat/room/${roomId}/messages`);
            if (!response.ok) {
                return;
            }

            const data = await response.json();
            await renderMessages(data.messages);
            if (userCount) {
                userCount.textContent = `Users: ${data.user_count}`;
            }
        } catch (_error) {
            // Ignore transient polling failures.
        }
    }

    sendBtn.addEventListener("click", sendMessage);
    messageInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            sendMessage();
        }
    });

    if (acceptSecurityWarningBtn) {
        acceptSecurityWarningBtn.addEventListener("click", acceptSecurityWarning);
    }

    if (encryptionToggle && encryptionStatus) {
        encryptionToggle.addEventListener("change", async (event) => {
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
                    showStatus(
                        "Encryption enabled with automatic key exchange.",
                        4000
                    );
                }

                encryptionStatus.textContent = "Encryption: ON";
                encryptionStatus.className = "encryption-status enabled";
            } else {
                encryptionStatus.textContent = "Encryption: OFF";
                encryptionStatus.className = "encryption-status";
            }

            await pollMessages();
        });
    }

    window.addEventListener("load", async () => {
        showSecurityWarning();
        if (securityWarningAccepted) {
            setComposerEnabled(true);
        }

        await pollMessages();
        pollInterval = window.setInterval(pollMessages, 2000);
    });

    window.addEventListener("beforeunload", () => {
        if (pollInterval) {
            window.clearInterval(pollInterval);
        }
    });
})();
