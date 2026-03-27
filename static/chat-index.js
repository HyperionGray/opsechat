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
            throw new Error('Failed to create room');
        }

        const data = await response.json();

        if (data.success) {
            const roomUrl = new URL(data.room_url, window.location.origin);
            statusDiv.replaceChildren(
                document.createTextNode('Room created! Redirecting...'),
                document.createElement('br'),
                Object.assign(document.createElement('a'), {
                    href: roomUrl.pathname,
                    textContent: roomUrl.toString()
                })
            );
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
