// Simple room creation with explicit backoff handling on 429 responses
const createRoomBtn = document.getElementById('createRoomBtn');
const statusDiv = document.getElementById('status');
let createCooldownTimer = null;

function setCreateButtonDisabled(disabled) {
    createRoomBtn.disabled = disabled;
}

function setCreateStatus(message) {
    statusDiv.textContent = message;
}

function startCreateCooldown(seconds) {
    const total = Math.max(1, Number.parseInt(seconds, 10) || 1);
    let remaining = total;

    setCreateButtonDisabled(true);
    setCreateStatus(`Rate limited. Try again in ${remaining}s.`);

    if (createCooldownTimer) {
        clearInterval(createCooldownTimer);
    }

    createCooldownTimer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(createCooldownTimer);
            createCooldownTimer = null;
            setCreateButtonDisabled(false);
            setCreateStatus('');
            return;
        }
        setCreateStatus(`Rate limited. Try again in ${remaining}s.`);
    }, 1000);
}

createRoomBtn.addEventListener('click', async function () {
    setCreateStatus('Creating room...');
    setCreateButtonDisabled(true);

    try {
        const response = await fetch('/chat/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 429) {
            const retryAfterHeader = Number.parseInt(response.headers.get('Retry-After') || '', 10);
            const retryAfterBody = Number.parseInt(data.retry_after || '', 10);
            const retryAfter = retryAfterBody || retryAfterHeader || 1;
            startCreateCooldown(retryAfter);
            return;
        }

        if (!response.ok) {
            throw new Error(data.error || 'Failed to create room');
        }

        if (data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else {
            setCreateStatus('Error creating room');
            setCreateButtonDisabled(false);
        }
    } catch (error) {
        setCreateStatus('Error: ' + error.message);
        setCreateButtonDisabled(false);
    }
});
