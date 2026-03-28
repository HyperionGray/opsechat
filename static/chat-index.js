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
            let message = 'Failed to create room';
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                if (retryAfter) {
                    message = `Rate limited. Retry in ${retryAfter}s.`;
                } else {
                    message = 'Rate limited. Please retry shortly.';
                }
            } else {
                try {
                    const errorData = await response.json();
                    if (errorData && errorData.error) {
                        message = errorData.error;
                    }
                } catch (_) {
                    // Keep fallback message when response body is not JSON.
                }
            }
            throw new Error(message);
        }

        const data = await response.json();

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
