document.addEventListener('DOMContentLoaded', () => {
  const targetPath = document.body.dataset.redirectPath;
  if (!targetPath) {
    return;
  }

  window.location.replace(`/${targetPath}/yesscript`);
});
