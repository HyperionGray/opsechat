(() => {
    const createRoomBtn = document.getElementById("createRoomBtn");
    const statusDiv = document.getElementById("status");

    if (!createRoomBtn || !statusDiv) {
        return;
    }

    createRoomBtn.addEventListener("click", async () => {
        createRoomBtn.disabled = true;
        statusDiv.textContent = "Creating room...";

        try {
            const response = await fetch("/chat/create", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            });

            if (!response.ok) {
                throw new Error("Failed to create room");
            }

            const data = await response.json();
            if (!data.success || !data.room_url) {
                throw new Error("Invalid room creation response");
            }

            statusDiv.textContent = "Room created! Redirecting...";
            statusDiv.appendChild(document.createElement("br"));

            const roomLink = document.createElement("a");
            roomLink.href = data.room_url;
            roomLink.textContent = `${window.location.origin}${data.room_url}`;
            statusDiv.appendChild(roomLink);

            window.setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } catch (error) {
            statusDiv.textContent = `Error: ${error.message}`;
            createRoomBtn.disabled = false;
        }
    });
})();
