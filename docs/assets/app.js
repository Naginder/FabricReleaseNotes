(() => {
  const qInput = document.getElementById("q");
  const statusSelect = document.getElementById("status");
  const historyCheckbox = document.getElementById("history");
  const reloadButton = document.getElementById("reload");
  const meta = document.getElementById("meta");
  const tableBody = document.getElementById("tableBody");
  const sortHeaders = Array.from(document.querySelectorAll("th.sortable[data-sort-key]"));

  let allItems = [];
  const sortState = {
    key: null,
    direction: "asc",
  };

  function escapeHtml(text) {
    return (text || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function badgeClass(status) {
    return status === "GA" ? "ga" : "preview";
  }

  function renderRows(items) {
    if (!items.length) {
      tableBody.innerHTML = "<tr><td colspan=\"6\">No matching rows.</td></tr>";
      return;
    }

    tableBody.innerHTML = items.map((item) => {
      const title = escapeHtml(item.title || "-");
      const link = item.learn_more_url
        ? `<a href="${escapeHtml(item.learn_more_url)}" target="_blank" rel="noreferrer">${title}</a>`
        : title;

      const stateLabel = item.is_active ? "Active" : "Superseded";
      const stateClass = item.is_active ? "state-active" : "state-superseded";

      return `
        <tr>
          <td><span class="badge ${badgeClass(item.status)}">${escapeHtml(item.status || "-")}</span></td>
          <td>${link}</td>
          <td>${escapeHtml(item.month_label || "-")}</td>
          <td>${escapeHtml(item.category || "-")}</td>
          <td>${escapeHtml(item.summary || "-")}</td>
          <td><span class="${stateClass}">${stateLabel}</span></td>
        </tr>
      `;
    }).join("");
  }

  function parseDateValue(value) {
    const clean = (value || "").trim();
    if (!clean || clean === "-") {
      return Number.POSITIVE_INFINITY;
    }

    const ts = Date.parse(`1 ${clean}`);
    if (!Number.isNaN(ts)) {
      return ts;
    }

    return clean.toLowerCase();
  }

  function compareItems(a, b, key, direction) {
    const dir = direction === "asc" ? 1 : -1;

    if (key === "title") {
      const aTitle = (a.title || "").toLowerCase();
      const bTitle = (b.title || "").toLowerCase();
      return aTitle.localeCompare(bTitle) * dir;
    }

    const aDate = parseDateValue(a.month_label || "");
    const bDate = parseDateValue(b.month_label || "");

    if (typeof aDate === "string" || typeof bDate === "string") {
      return String(aDate).localeCompare(String(bDate)) * dir;
    }

    return (aDate - bDate) * dir;
  }

  function updateSortIndicators() {
    sortHeaders.forEach((th) => {
      const indicator = th.querySelector(".sort-indicator");
      if (!indicator) {
        return;
      }
      if (th.dataset.sortKey !== sortState.key) {
        indicator.textContent = "";
        th.removeAttribute("aria-sort");
        return;
      }
      indicator.textContent = sortState.direction === "asc" ? "▲" : "▼";
      th.setAttribute("aria-sort", sortState.direction === "asc" ? "ascending" : "descending");
    });
  }

  function applyFilters() {
    const q = (qInput.value || "").trim().toLowerCase();
    const status = statusSelect.value;
    const includeHistory = historyCheckbox.checked;

    const filtered = allItems.filter((item) => {
      if (!includeHistory && !item.is_active) {
        return false;
      }

      if (status !== "All" && item.status !== status) {
        return false;
      }

      if (!q) {
        return true;
      }

      const blob = `${item.title || ""} ${item.summary || ""} ${item.category || ""}`.toLowerCase();
      return blob.includes(q);
    });

    if (sortState.key) {
      filtered.sort((a, b) => compareItems(a, b, sortState.key, sortState.direction));
    }

    renderRows(filtered);
    updateSortIndicators();
  }

  function formatUtc(value) {
    if (!value) {
      return "unknown";
    }

    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) {
      return value;
    }

    return dt.toLocaleString();
  }

  async function loadData() {
    meta.textContent = "Loading data...";

    try {
      const response = await fetch(`data/releases.json?t=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      allItems = Array.isArray(payload.items) ? payload.items : [];

      const stats = payload.stats || {};
      meta.innerHTML = `
        Last updated: <span class="mono">${escapeHtml(formatUtc(payload.last_updated_utc))}</span>
        | total ${Number(stats.total_items || 0)}
        | active ${Number(stats.active_items || 0)}
        | inserted ${Number(stats.inserted || 0)}
        | updated ${Number(stats.updated || 0)}
        | superseded ${Number(stats.superseded || 0)}
      `;

      applyFilters();
    } catch (error) {
      meta.textContent = `Could not load data: ${error.message}`;
      tableBody.innerHTML = "<tr><td colspan=\"6\">Data load failed.</td></tr>";
    }
  }

  function toggleSort(key) {
    if (!key) {
      return;
    }
    if (sortState.key === key) {
      sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
    } else {
      sortState.key = key;
      sortState.direction = "asc";
    }
    applyFilters();
  }

  sortHeaders.forEach((th) => {
    th.addEventListener("click", () => toggleSort(th.dataset.sortKey));
    th.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleSort(th.dataset.sortKey);
      }
    });
  });

  qInput.addEventListener("input", applyFilters);
  statusSelect.addEventListener("change", applyFilters);
  historyCheckbox.addEventListener("change", applyFilters);
  reloadButton.addEventListener("click", loadData);

  loadData();
})();
