function copyTextToClipboard(text) {
  if (navigator.clipboard) {
    return navigator.clipboard.writeText(text);
  }

  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.left = '-999999px';
  document.body.appendChild(textArea);
  textArea.select();
  document.execCommand('copy');
  document.body.removeChild(textArea);
  return Promise.resolve();
}

function updateCountdowns() {
  document.querySelectorAll('.time-remaining[data-seconds]').forEach((element) => {
    let seconds = parseInt(element.dataset.seconds || '0', 10);
    if (seconds > 0) {
      seconds -= 1;
      element.dataset.seconds = `${seconds}`;

      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = seconds % 60;
      let timeStr = `${secs}s`;

      if (hours > 0) {
        timeStr = `${hours}h ${minutes}m`;
      } else if (minutes > 0) {
        timeStr = `${minutes}m ${secs}s`;
      }

      const countdownSpan = element.querySelector('.countdown');
      if (countdownSpan) {
        countdownSpan.textContent = timeStr;
      }

      const card = element.closest('.burner-card');
      if (seconds < 3600) {
        element.classList.add('expiring');
        if (card) {
          card.classList.add('expiring-soon');
        }
      }
      if (seconds < 300) {
        element.classList.add('expired');
      }
    } else {
      const countdownSpan = element.querySelector('.countdown');
      if (countdownSpan) {
        countdownSpan.textContent = 'Expired';
      }
      element.classList.add('expired');
      const card = element.closest('.burner-card');
      if (card) {
        card.classList.add('expired');
      }
    }
  });
}

async function refreshBurnerList(path) {
  try {
    await fetch(`/${path}/email/burner/list`, {
      headers: { Accept: 'application/json' },
    });
  } catch (error) {
    console.error('Error refreshing burners:', error);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const path = document.body.dataset.path;
  const scriptEnabled = document.body.dataset.scriptEnabled === 'true';

  document.querySelectorAll('[data-copy-email]').forEach((button) => {
    button.addEventListener('click', async () => {
      await copyTextToClipboard(button.dataset.copyEmail || '');
      alert('Email address copied to clipboard.');
    });
  });

  if (!scriptEnabled || !path) {
    return;
  }

  setInterval(updateCountdowns, 1000);
  setInterval(() => refreshBurnerList(path), 30000);
});
