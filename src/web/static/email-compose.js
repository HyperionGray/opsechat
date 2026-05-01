function toggleComposeMode() {
  const selected = document.querySelector('input[name="compose-mode"]:checked');
  const standardForm = document.getElementById('standard-form');
  const rawForm = document.getElementById('raw-mode-form');

  if (!selected || !standardForm || !rawForm) {
    return;
  }

  if (selected.value === 'raw') {
    standardForm.classList.remove('active');
    rawForm.classList.add('active');
  } else {
    rawForm.classList.remove('active');
    standardForm.classList.add('active');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('input[name="compose-mode"]').forEach((input) => {
    input.addEventListener('change', toggleComposeMode);
  });
  toggleComposeMode();
});
