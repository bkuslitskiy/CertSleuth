// Click-to-sort for any <table data-sortable> with explicit <thead>/<tbody>. Header cells
// opt in with data-sort="text|num|date" (the type controls comparison, not just labeling).
// A cell can override its sort value with data-sort-value (e.g. a tier rank or ISO date)
// so the sort doesn't have to re-parse whatever's rendered for display. Missing values
// always sort to the bottom regardless of direction — an unranked/unset fact isn't
// "smallest", it's unknown.
(function () {
  function cellValue(row, index, type) {
    var cell = row.cells[index];
    if (!cell) return null;
    var raw = cell.dataset.sortValue;
    if (raw === undefined) raw = cell.textContent.trim();
    if (raw === "" || raw === "—") return null;
    if (type === "num") {
      var n = parseFloat(String(raw).replace(/[^0-9.\-]/g, ""));
      return isNaN(n) ? null : n;
    }
    if (type === "date") {
      var t = Date.parse(raw);
      return isNaN(t) ? null : t;
    }
    return String(raw).toLowerCase();
  }

  function sortTable(table, th, index, type) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var dir = th.dataset.sort === "asc" ? "desc" : "asc";
    table.querySelectorAll("thead th[data-sort]").forEach(function (h) {
      h.dataset.sort = h === th ? dir : "";
    });
    var rows = Array.prototype.slice.call(tbody.rows);
    rows.sort(function (a, b) {
      var av = cellValue(a, index, type), bv = cellValue(b, index, type);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;             // unknown values always last
      if (bv === null) return -1;
      if (av < bv) return dir === "asc" ? -1 : 1;
      if (av > bv) return dir === "asc" ? 1 : -1;
      return 0;
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("table[data-sortable]").forEach(function (table) {
      var headers = table.querySelectorAll("thead th[data-sort]");
      headers.forEach(function (th, i) {
        var index = Array.prototype.indexOf.call(th.parentNode.children, th);
        th.setAttribute("role", "button");
        th.setAttribute("tabindex", "0");
        var type = th.dataset.sort;
        th.dataset.sort = "";           // reset the label attr to its "unsorted" state
        function activate() { sortTable(table, th, index, type); }
        th.addEventListener("click", activate);
        th.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); }
        });
      });
    });
  });
})();
