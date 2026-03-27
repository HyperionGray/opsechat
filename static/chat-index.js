const statusDiv = document.getElementById('status');
const roomIdInput = document.getElementById('roomIdInput');
const createRoomBtn = document.getElementById('createRoomBtn');
const joinRoomBtn = document.getElementById('joinRoomBtn');

function normalizeRoomId(rawValue) {
    if (!rawValue) {
        return '';
    }

    const trimmed = rawValue.trim();
    if (!trimmed) {
        return '';
    }

    // Accept full URLs and extract the room ID segment.
    const roomMatch = trimmed.match(/\/chat\/room\/([^/?#]+)/);
    if (roomMatch && roomMatch[1]) {
        return roomMatch[1];
    }

    return trimmed;
}

function renderStatus(text) {
    statusDiv.textContent = text;
}

async function createRoom() {
    renderStatus('Creating room...');

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
            statusDiv.innerHTML = `Room created! Redirecting...<br><a href="${data.room_url}">${window.location.origin}${data.room_url}</a>`;
            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } else {
            renderStatus('Error creating room');
        }
    } catch (error) {
        renderStatus('Error: ' + error.message);
    }
}

async function joinRoom() {
    const roomId = normalizeRoomId(roomIdInput.value);
    if (!roomId) {
        renderStatus('Enter a room ID or room URL first.');
        roomIdInput.focus();
        return;
    }

    renderStatus('Checking room...');

    try {
        const response = await fetch(`/chat/room/exists/${encodeURIComponent(roomId)}`);
        if (!response.ok) {
            throw new Error('Unable to verify room');
        }

        const data = await response.json();
        if (!data.exists) {
            renderStatus('Room not found or expired. Check the ID and try again.');
            return;
        }

        renderStatus('Room found. Redirecting...');
        window.location.href = `/chat/room/${encodeURIComponent(roomId)}`;
    } catch (error) {
        renderStatus('Error: ' + error.message);
    }
}

createRoomBtn.addEventListener('click', createRoom);
joinRoomBtn.addEventListener('click', joinRoom);

roomIdInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        joinRoom();
    }
});
