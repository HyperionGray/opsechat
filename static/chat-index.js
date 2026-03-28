// Simple room creation with no external dependencies
document.getElementById('createRoomBtn').addEventListener('click', async function() {
    const statusDiv = document.getElementById('status');
    const passphraseInput = document.getElementById('roomPassphrase');
    const roomPassphrase = passphraseInput ? passphraseInput.value.trim() : '';
    statusDiv.textContent = 'Creating room...';

    try {
        const payload = {};
        if (roomPassphrase) {
            payload.room_passphrase = roomPassphrase;
        }

        const response = await fetch('/chat/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to create room');
        }

        if (data.success) {
            const lockLabel = data.protected ? 'Protected room created!' : 'Room created!';
            statusDiv.innerHTML = `${lockLabel} Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
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
