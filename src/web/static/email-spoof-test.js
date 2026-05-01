function showSpoofTestTab(tabName, clickedButton) {
  document.querySelectorAll('.tab-content').forEach((tab) => {
    tab.classList.remove('active');
  });
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.classList.remove('active');
  });

  const targetTab = document.getElementById(`${tabName}-tab`);
  if (targetTab) {
    targetTab.classList.add('active');
  }
  if (clickedButton) {
    clickedButton.classList.add('active');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab-button[data-tab-target]').forEach((button) => {
    button.addEventListener('click', () => {
      showSpoofTestTab(button.dataset.tabTarget, button);
    });
  });
});
