document.addEventListener('DOMContentLoaded', () => {
  const scriptEnabled = document.body.dataset.scriptEnabled === 'true';
  if (!scriptEnabled) {
    return;
  }

  setTimeout(() => {
    window.location.reload();
  }, 30000);
});
