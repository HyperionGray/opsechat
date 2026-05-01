(() => {
  const createRoomBtn = document.getElementById('createRoomBtn');
  if (createRoomBtn) {
    createRoomBtn.addEventListener('click', async () => {
      const status = document.getElementById('createRoomStatus');
      try {
        const response = await fetch('/chat/create', { method: 'POST' });
        if (!response.ok) {
          throw new Error(`room creation failed (${response.status})`);
        }
        const data = await response.json();
        if (data && data.room_url) {
          window.location.href = data.room_url;
          return;
        }
        throw new Error('room URL missing in response');
      } catch (error) {
        if (status) {
          status.textContent = 'Unable to create room. Please retry.';
        }
      }
    });
  }

  const acceptSecurityWarningBtn = document.getElementById('acceptSecurityWarningBtn');
  if (acceptSecurityWarningBtn) {
    acceptSecurityWarningBtn.addEventListener('click', () => {
      const securityWarning = document.getElementById('securityWarning');
      if (securityWarning) {
        securityWarning.style.display = 'none';
      }
    });
  }
})();
