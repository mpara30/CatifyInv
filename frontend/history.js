const API = "/api";

const searchInput = document.getElementById("searchInput");
const sourceFilter = document.getElementById("sourceFilter");
const tableBody = document.getElementById("historyTableBody");
const emptyState = document.getElementById("emptyState");
const tableWrap = document.querySelector(".history-table-wrap");

function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatWhen(isoString) {
  const d = new Date(isoString + "Z");
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

async function loadHistory() {
  const params = new URLSearchParams();
  if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
  if (sourceFilter.value) params.set("source", sourceFilter.value);

  const res = await fetch(`${API}/stock-history?${params.toString()}`);
  const entries = await res.json();
  renderTable(entries);
}

const SOURCE_LABELS = {
  create: "Added",
  edit: "Edited",
  adjust: "Quick +/-",
  delete: "Removed",
  feed: "Fed",
};

function renderTable(entries) {
  if (entries.length === 0) {
    tableWrap.classList.add("hidden");
    emptyState.classList.remove("hidden");
    return;
  }
  tableWrap.classList.remove("hidden");
  emptyState.classList.add("hidden");

  tableBody.innerHTML = entries
    .map((h) => {
      const sign = h.delta > 0 ? "+" : "";
      const qtyCls = h.delta > 0 ? "positive" : "negative";
      const label = SOURCE_LABELS[h.source] || h.source;
      return `
        <tr>
          <td class="cell-when">${formatWhen(h.created_at)}</td>
          <td class="cell-product">${escapeHtml(h.product_name)}</td>
          <td class="cell-brand">${escapeHtml(h.product_brand)}</td>
          <td class="cell-cat">${h.cat_name ? escapeHtml(h.cat_name) : "—"}</td>
          <td class="cell-change">${h.previous_qty} &rarr; ${h.new_qty}</td>
          <td class="cell-qty ${qtyCls}">${sign}${h.delta}</td>
          <td><span class="source-pill ${h.source}">${label}</span></td>
        </tr>`;
    })
    .join("");
}

searchInput.addEventListener("input", debounce(loadHistory, 250));
sourceFilter.addEventListener("change", loadHistory);

loadHistory();