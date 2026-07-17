// Dark is default (brief); light available. Persisted client-side only.
(function () {
  var saved = localStorage.getItem("theme");
  if (saved) document.documentElement.dataset.theme = saved;
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
