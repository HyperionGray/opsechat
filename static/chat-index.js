function disableCreateButton(seconds) {
    const createBtn = document.getElementById('createRoomBtn');
    const statusDiv = document.getElementById('status');
    const safeSeconds = Math.max(1, Number(seconds) || 1);

    createBtn.disabled = true;

    let remaining = safeSeconds;
    statusDiv.textContent = `Rate limited. Try creating a room again in ${remaining}s.`;

    const timer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(timer);
            createBtn.disabled = false;
            statusDiv.textContent = 'Ready. You can create a room now.';
            return;
        }
        statusDiv.textContent = `Rate limited. Try creating a room again in ${remaining}s.`;
    }, 1000);
}

// Simple room creation with no external dependencies
document.getElementById('createRoomBtn').addEventListener('click', async function () {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = 'Creating room...';

    try {
        const response = await fetch('/chat/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            if (response.status === 429) {
                const retryHeader = Number(response.headers.get('Retry-After'));
                const retryBody = Number(data.retry_after_seconds);
                const retryAfter = Number.isFinite(retryHeader) && retryHeader > 0
                    ? retryHeader
                    : (Number.isFinite(retryBody) && retryBody > 0 ? retryBody : 1);
                disableCreateButton(retryAfter);
                return;
            }

            throw new Error(data.error || 'Failed to create room');
        }

        if (data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else {
            statusDiv.textContent = data.error || 'Error creating room';
        }
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
    }
});
