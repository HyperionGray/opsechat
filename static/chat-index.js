function getRetryAfterSeconds(response, data) {
    const headerValue = response.headers.get('Retry-After');
    const headerSeconds = headerValue ? parseInt(headerValue, 10) : NaN;
    if (!Number.isNaN(headerSeconds) && headerSeconds > 0) {
        return headerSeconds;
    }

    const bodySeconds = Number(data?.retry_after_seconds);
    if (!Number.isNaN(bodySeconds) && bodySeconds > 0) {
        return bodySeconds;
    }

    return 0;
}

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

        const data = await response.json();

        if (response.ok && data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else if (response.status === 429) {
            const retryAfter = getRetryAfterSeconds(response, data);
            if (retryAfter > 0) {
                statusDiv.textContent = `Rate limit reached. Please wait ${retryAfter} second(s) and try again.`;
            } else {
                statusDiv.textContent = 'Rate limit reached. Please wait and try again.';
            }
        } else {
            statusDiv.textContent = data?.error || 'Error creating room';
        }
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
    }
});
