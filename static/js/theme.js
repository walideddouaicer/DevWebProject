/* Theme bootstrap (PLAN P5.7). Loaded synchronously in <head> to avoid a flash of the
   wrong theme. Signed-in users get data-theme from the server (their preference);
   anonymous visitors' choice lives in localStorage. "auto" follows the OS setting. */
(function () {
  var root = document.documentElement;
  if (root.dataset.themeSource === "server") return;
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark" || saved === "auto") root.dataset.theme = saved;
  } catch (e) { /* storage disabled: keep auto */ }
})();
