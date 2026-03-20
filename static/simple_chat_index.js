document.addEventListener("DOMContentLoaded", () => {
    const createRoomBtn = document.getElementById("createRoomBtn");
    const statusDiv = document.getElementById("status");

    if (!createRoomBtn || !statusDiv) {
        return;
    }

    createRoomBtn.addEventListener("click", async () => {
        statusDiv.textContent = "Creating room...";

        try {
            const response = await fetch("/chat/create", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            });

            let data = {};
            try {
                data = await response.json();
            } catch (error) {
                data = {};
            }

            if (!response.ok || !data.success || !data.room_url) {
                throw new Error(data.error || "Failed to create room");
            }

            statusDiv.textContent = "Room created! Redirecting...";
            statusDiv.appendChild(document.createElement("br"));

            const roomLink = document.createElement("a");
            roomLink.href = data.room_url;
            roomLink.textContent = `${window.location.origin}${data.room_url}`;
            statusDiv.appendChild(roomLink);

            setTimeout(() => {
                window.location.href = data.room_url;
            }, 1000);
        } catch (error) {
            statusDiv.textContent = `Error: ${error.message}`;
        }
    });
});
