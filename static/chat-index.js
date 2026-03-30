const createRoomBtn = document.getElementById('createRoomBtn');
const statusDiv = document.getElementById('status');

let createCooldownTimer = null;

function stopCreateCooldown() {
    if (createCooldownTimer) {
        clearInterval(createCooldownTimer);
        createCooldownTimer = null;
    }
}

function startCreateCooldown(seconds) {
    stopCreateCooldown();
    let remaining = Math.max(parseInt(seconds, 10) || 1, 1);
    createRoomBtn.disabled = true;
    createRoomBtn.setAttribute('aria-disabled', 'true');
    statusDiv.textContent = `Rate limited. Try again in ${remaining}s.`;

    createCooldownTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            stopCreateCooldown();
            createRoomBtn.disabled = false;
            createRoomBtn.removeAttribute('aria-disabled');
            statusDiv.textContent = 'You can create a new room now.';
            return;
        }
        statusDiv.textContent = `Rate limited. Try again in ${remaining}s.`;
    }, 1000);
}

function extractRetryAfter(response, body) {
    const headerValue = response.headers.get('Retry-After');
    if (headerValue && !Number.isNaN(parseInt(headerValue, 10))) {
        return parseInt(headerValue, 10);
    }
    if (body && typeof body.retry_after === 'number') {
        return body.retry_after;
    }
    return 60;
}

// Simple room creation with no external dependencies
createRoomBtn.addEventListener('click', async function() {
    createRoomBtn.disabled = true;
    statusDiv.textContent = 'Creating room...';

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
        } catch (e) {
            data = null;
        }

        if (response.status === 429) {
            const retryAfter = extractRetryAfter(response, data);
            startCreateCooldown(retryAfter);
            return;
        }

        if (!response.ok) {
            throw new Error((data && data.error) || 'Failed to create room');
        }

        if (data && data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
            return;
        }

        throw new Error('Error creating room');
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
    } finally {
        // Re-enable only when not in cooldown mode.
        if (!createCooldownTimer) {
            createRoomBtn.disabled = false;
            createRoomBtn.removeAttribute('aria-disabled');
        }
    }
});
