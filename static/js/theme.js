// Theme: an explicit choice (localStorage) wins; otherwise follow the OS preference,
// falling back to dark (the brief's default, also set on <html>). Loaded non-deferred in
// <head> so the theme is set before first paint — no flash.
(function () {
  var saved = localStorage.getItem("theme");
  if (saved) {
    document.documentElement.dataset.theme = saved;
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    document.documentElement.dataset.theme = "light";
  }
  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("theme", next);
    });
  });
})();
