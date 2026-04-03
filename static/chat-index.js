// Simple room creation with no external dependencies
document.getElementById('createRoomBtn').addEventListener('click', async function() {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = 'Creating room...';

    try {
        const response = await fetch('/chat/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            if (response.status === 429) {
                let retryAfter = Number.parseInt(response.headers.get('Retry-After'), 10);
                let message = 'Rate limit exceeded. Please wait before trying again.';
                try {
                    const payload = await response.json();
                    if (payload && typeof payload.error === 'string' && payload.error.trim()) {
                        message = payload.error;
                    }
                    if (
                        payload
                        && Number.isFinite(payload.retry_after_seconds)
                        && payload.retry_after_seconds > 0
                    ) {
                        retryAfter = Math.ceil(payload.retry_after_seconds);
                    }
                } catch (error) {
                    // Keep default message when the response body isn't JSON.
                }
                if (Number.isFinite(retryAfter) && retryAfter > 0) {
                    statusDiv.textContent = `${message} Retry in ${retryAfter}s.`;
                } else {
                    statusDiv.textContent = message;
                }
                return;
            }
            throw new Error('Failed to create room');
        }

        const data = await response.json();

        if (data.success) {
            statusDiv.textContent = 'Room created! Redirecting...';
            const br = document.createElement('br');
            const link = document.createElement('a');
            link.href = data.room_url;
            link.textContent = `${window.location.origin}${data.room_url}`;
            statusDiv.appendChild(br);
            statusDiv.appendChild(link);
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else {
            statusDiv.textContent = 'Error creating room';
        }
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
    }
});
