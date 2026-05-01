document.addEventListener('DOMContentLoaded', () => {
  const targetPath = document.body.dataset.redirectPath;
  if (!targetPath) {
    return;
  }

  window.setTimeout(() => {
    window.location.replace(`/${targetPath}/yesscript`);
  }, 300);
});
