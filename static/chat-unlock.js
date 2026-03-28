const roomId = document.body.dataset.roomId;
const passphraseInput = document.getElementById("passphraseInput");
const unlockBtn = document.getElementById("unlockBtn");
const statusEl = document.getElementById("status");

function showStatus(message) {
    statusEl.textContent = message;
}

async function unlockRoom() {
    const passphrase = passphraseInput.value.trim();
    if (!passphrase) {
        showStatus("Passphrase is required.");
        return;
    }

    unlockBtn.disabled = true;
    showStatus("Unlocking room...");

    try {
        const response = await fetch(`/chat/room/${roomId}/unlock`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ passphrase }),
        });

        const data = await response.json();
        if (!response.ok) {
            showStatus(data.error || "Failed to unlock room.");
            unlockBtn.disabled = false;
            return;
        }

        showStatus("Unlocked. Redirecting...");
        window.location.href = `/chat/room/${roomId}`;
    } catch (error) {
        showStatus(`Error: ${error.message}`);
        unlockBtn.disabled = false;
    }
}

unlockBtn.addEventListener("click", unlockRoom);
passphraseInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        unlockRoom();
    }
});
