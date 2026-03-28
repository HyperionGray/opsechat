let createRoomCooldownUntil = 0;
let createRoomCooldownInterval = null;

function clearCreateRoomCooldownInterval() {
    if (createRoomCooldownInterval) {
        clearInterval(createRoomCooldownInterval);
        createRoomCooldownInterval = null;
    }
}

function parseRetryAfterSeconds(response, data) {
    const headerRetry = Number.parseInt(response.headers.get('Retry-After') || '', 10);
    const bodyRetry = Number.parseInt(data?.retry_after, 10);
    if (Number.isInteger(bodyRetry) && bodyRetry > 0) {
        return bodyRetry;
    }
    if (Number.isInteger(headerRetry) && headerRetry > 0) {
        return headerRetry;
    }
    return 1;
}

function setCreateRoomCooldown(seconds, statusDiv, button, message) {
    clearCreateRoomCooldownInterval();
    createRoomCooldownUntil = Date.now() + (seconds * 1000);
    button.disabled = true;

    const updateStatus = () => {
        const remaining = Math.max(0, Math.ceil((createRoomCooldownUntil - Date.now()) / 1000));
        statusDiv.textContent = `${message} Retry in ${remaining}s.`;
        if (remaining <= 0) {
            clearCreateRoomCooldownInterval();
            button.disabled = false;
            statusDiv.textContent = '';
        }
    };

    updateStatus();
    createRoomCooldownInterval = setInterval(updateStatus, 1000);
}

// Simple room creation with no external dependencies
document.getElementById('createRoomBtn').addEventListener('click', async function() {
    const button = document.getElementById('createRoomBtn');
    const statusDiv = document.getElementById('status');
    const remaining = Math.ceil((createRoomCooldownUntil - Date.now()) / 1000);
    if (remaining > 0) {
        statusDiv.textContent = `Rate limited. Retry in ${remaining}s.`;
        return;
    }

    statusDiv.textContent = 'Creating room...';
    button.disabled = true;

    try {
        const response = await fetch('/chat/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        let data = null;
        try {
            data = await response.json();
        } catch (err) {
            data = null;
        }

        if (!response.ok) {
            if (response.status === 429) {
                const retryAfter = parseRetryAfterSeconds(response, data);
                const message = data?.error || 'Rate limit exceeded.';
                setCreateRoomCooldown(retryAfter, statusDiv, button, message);
                return;
            }
            throw new Error(data?.error || 'Failed to create room');
        }

        if (data && data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else {
            statusDiv.textContent = 'Error creating room';
        }
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
    } finally {
        const retryRemaining = Math.ceil((createRoomCooldownUntil - Date.now()) / 1000);
        if (retryRemaining <= 0) {
            button.disabled = false;
        }
    }
});
