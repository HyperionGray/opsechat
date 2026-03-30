// Simple room creation with no external dependencies
const createRoomBtn = document.getElementById('createRoomBtn');
const statusDiv = document.getElementById('status');

function setCreateState(isBusy, label = null) {
    createRoomBtn.disabled = isBusy;
    if (label) {
        createRoomBtn.textContent = label;
    } else {
        createRoomBtn.textContent = 'Create New Chat Room';
    }
}

function formatRetryMessage(seconds) {
    const safeSeconds = Math.max(parseInt(seconds || 0, 10), 1);
    if (safeSeconds === 1) {
        return 'Rate limit reached. Please wait 1 second and try again.';
    }
    return `Rate limit reached. Please wait ${safeSeconds} seconds and try again.`;
}

createRoomBtn.addEventListener('click', async function() {
    setCreateState(true, 'Creating...');
    statusDiv.textContent = 'Creating room...';

    try {
        const response = await fetch('/chat/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            let errorPayload = null;
            try {
                errorPayload = await response.json();
            } catch (_) {
                errorPayload = null;
            }

            if (response.status === 429) {
                const retryAfterHeader = parseInt(response.headers.get('Retry-After') || '0', 10);
                const retryAfterBody = errorPayload && errorPayload.retry_after_seconds;
                const retrySeconds = retryAfterHeader || retryAfterBody || 1;
                statusDiv.textContent = formatRetryMessage(retrySeconds);
                setCreateState(true, `Retry in ${retrySeconds}s`);

                setTimeout(function() {
                    setCreateState(false);
                }, retrySeconds * 1000);
                return;
            }

            throw new Error((errorPayload && errorPayload.error) || 'Failed to create room');
        }

        const data = await response.json();

        if (data.success) {
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else {
            statusDiv.textContent = 'Error creating room';
            setCreateState(false);
        }
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
        setCreateState(false);
    }
});
