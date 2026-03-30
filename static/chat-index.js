// Simple room creation with no external dependencies
function parseRetryAfterSeconds(response, data) {
    const headerValue = response.headers.get('Retry-After') || response.headers.get('X-RateLimit-Retry-After');
    if (headerValue) {
        const parsed = parseInt(headerValue, 10);
        if (!Number.isNaN(parsed) && parsed > 0) {
            return parsed;
        }
    }

    if (data && typeof data.retry_after === 'number' && data.retry_after > 0) {
        return Math.ceil(data.retry_after);
    }

    return null;
}

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

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            if (response.status === 429) {
                const retryAfter = parseRetryAfterSeconds(response, data);
                if (retryAfter) {
                    throw new Error(`Rate limited. Try again in ${retryAfter}s.`);
                }
                throw new Error('Rate limited. Try again shortly.');
            }

            throw new Error(data.error || 'Failed to create room');
        }

        if (data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
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
