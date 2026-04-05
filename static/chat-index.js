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
                const payload = await response.json().catch(() => ({}));
                const wait = payload.retry_after_seconds || response.headers.get('Retry-After');
                throw new Error(`Rate limit exceeded. Try again in ${wait || '?'} seconds.`);
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
