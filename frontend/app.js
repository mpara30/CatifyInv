const API = "/api";

// ---------- State ----------
let products = [];
let deleteTargetId = null;

// ---------- Elements ----------
const grid = document.getElementById("productGrid");
const emptyState = document.getElementById("emptyState");

const searchInput = document.getElementById("searchInput");
const categoryFilter = document.getElementById("categoryFilter");
const flavourFilter = document.getElementById("flavourFilter");
const stockFilter = document.getElementById("stockFilter");
const sortSelect = document.getElementById("sortSelect");

const modalBackdrop = document.getElementById("modalBackdrop");
const modalTitle = document.getElementById("modalTitle");
const productForm = document.getElementById("productForm");
const formError = document.getElementById("formError");

const deleteBackdrop = document.getElementById("deleteBackdrop");
const deleteCopy = document.getElementById("deleteCopy");

const toast = document.getElementById("toast");

// ---------- Helpers ----------
function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 2400);
}

function formatMoney(ron) {
  return `${ron.toFixed(2)} RON`;
}

function daysFromToday(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(isoDate + "T00:00:00");
  return Math.round((target - today) / (1000 * 60 * 60 * 24));
}

function expirationClass(isoDate) {
  if (!isoDate) return "expiration-ok";
  const days = daysFromToday(isoDate);
  if (days < 0) return "expiration-past";
  if (days <= 30) return "expiration-soon";
  return "expiration-ok";
}

function stockBadge(qty) {
  if (qty === 0) return { cls: "badge-out", label: "Need more" };
  if (qty <= 2) return { cls: "badge-low", label: "Running low" };
  return { cls: "badge-in", label: "Stocked" };
}

// ---------- API calls ----------
async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function apiSend(path, method, body) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `${method} ${path} failed`);
  }
  return data;
}

async function apiDelete(path) {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`DELETE ${path} failed`);
}

// ---------- Stats ----------
async function loadStats() {
  try {
    const stats = await apiGet("/stats");
    document.getElementById("statTotal").textContent = stats.total_skus;
    document.getElementById("statLow").textContent = stats.low_stock_count;
    document.getElementById("statExpiring").textContent = stats.expiring_soon_count;
    document.getElementById("statValue").textContent = formatMoney(stats.total_value_ron);
  } catch (e) {
    console.error(e);
  }
}

// ---------- Filters -> query string ----------
function buildQuery() {
  const params = new URLSearchParams();
  if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
  if (categoryFilter.value) params.set("category", categoryFilter.value);
  if (flavourFilter.value) params.set("flavour", flavourFilter.value);
  if (stockFilter.value) params.set("in_stock", stockFilter.value);

  const [sort, order] = sortSelect.value.split("-");
  params.set("sort", sort);
  params.set("order", order);

  return params.toString();
}

// ---------- Filter dropdown population ----------
function populateFilterOptions(items) {
  const categories = [...new Set(items.map((p) => p.category).filter(Boolean))].sort();
  const flavours = [...new Set(items.map((p) => p.flavour).filter(Boolean))].sort();

  const fill = (select, values) => {
    const current = select.value;
    select.querySelectorAll("option[data-dynamic]").forEach((o) => o.remove());
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      opt.dataset.dynamic = "true";
      select.appendChild(opt);
    });
    if (values.includes(current)) select.value = current;
  };

  fill(categoryFilter, categories);
  fill(flavourFilter, flavours);
}

// ---------- Rendering ----------
function renderProducts(items) {
  grid.innerHTML = "";

  if (items.length === 0) {
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  items.forEach((p) => {
    const badge = stockBadge(p.stock_qty);
    const expClass = expirationClass(p.expiration_date);

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-top">
        <span class="badge ${badge.cls}">${badge.label}</span>
      </div>
      <h3 class="card-name">${escapeHtml(p.name)}</h3>
      <p class="card-brand">${escapeHtml(p.brand)}</p>
      <div class="card-tags">
        ${p.category ? `<span class="tag">${escapeHtml(p.category)}</span>` : ""}
        ${p.flavour ? `<span class="tag">${escapeHtml(p.flavour)}</span>` : ""}
        ${p.weight ? `<span class="tag">${p.weight}g</span>` : ""}
      </div>
      <div class="card-row">
        <span class="card-row-label">Price</span>
        <span class="card-row-value">${formatMoney(p.price_ron)}</span>
      </div>
      <div class="card-row">
        <span class="card-row-label">You have</span>
        <span class="card-row-value">
          <div class="stock-adjust">
            <button class="stock-btn" data-action="dec" data-id="${p.id}" ${p.stock_qty === 0 ? "disabled" : ""}>–</button>
            <span>${p.stock_qty}</span>
            <button class="stock-btn" data-action="inc" data-id="${p.id}">+</button>
          </div>
        </span>
      </div>
      <div class="card-row">
        <span class="card-row-label">Use by</span>
        <span class="card-row-value ${expClass}">${p.expiration_date || "—"}</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-ghost" data-action="edit" data-id="${p.id}">Edit</button>
        <button class="btn btn-ghost" data-action="delete" data-id="${p.id}">Delete</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------- Load + refresh ----------
async function loadProducts() {
  const query = buildQuery();
  products = await apiGet(`/products?${query}`);
  renderProducts(products);
}

async function loadAll() {
  await Promise.all([loadProducts(), loadStats()]);
  // populate filter dropdowns from the *unfiltered* catalog once
  if (!loadAll._populated) {
    const all = await apiGet("/products");
    populateFilterOptions(all);
    loadAll._populated = true;
  }
}

// ---------- Grid click delegation (edit / delete / stock adjust) ----------
grid.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const action = btn.dataset.action;

  if (action === "edit") {
    openEditModal(id);
  } else if (action === "delete") {
    openDeleteModal(id);
  } else if (action === "inc" || action === "dec") {
    const delta = action === "inc" ? 1 : -1;
    btn.disabled = true;
    try {
      await apiSend(`/products/${id}/adjust-stock`, "POST", { delta });
      await loadAll();
    } catch (err) {
      showToast(err.message);
    }
  }
});

// ---------- Filters wiring ----------
searchInput.addEventListener("input", debounce(loadProducts, 250));
[categoryFilter, flavourFilter, stockFilter, sortSelect].forEach((el) =>
  el.addEventListener("change", loadProducts)
);

// ---------- Add / Edit modal ----------
const openAddBtn = document.getElementById("openAddBtn");
const closeModalBtn = document.getElementById("closeModalBtn");
const cancelBtn = document.getElementById("cancelBtn");

function openAddModal() {
  productForm.reset();
  document.getElementById("productId").value = "";
  document.getElementById("fStock").value = 0;
  modalTitle.textContent = "Add product";
  formError.classList.add("hidden");
  document.getElementById("historySection").classList.add("hidden");
  modalBackdrop.classList.remove("hidden");
  document.getElementById("fName").focus();
}

async function openEditModal(id) {
  const p = products.find((x) => x.id === id);
  if (!p) return;
  document.getElementById("productId").value = p.id;
  document.getElementById("fName").value = p.name;
  document.getElementById("fBrand").value = p.brand;
  document.getElementById("fCategory").value = p.category || "";
  document.getElementById("fFlavour").value = p.flavour || "";
  document.getElementById("fWeight").value = p.weight || 0;
  document.getElementById("fPrice").value = p.price_ron;
  document.getElementById("fStock").value = p.stock_qty;
  document.getElementById("fExpiration").value = p.expiration_date || "";
  modalTitle.textContent = "Edit product";
  formError.classList.add("hidden");
  modalBackdrop.classList.remove("hidden");
  document.getElementById("fName").focus();

  const historySection = document.getElementById("historySection");
  const historyList = document.getElementById("historyList");
  historySection.classList.remove("hidden");
  historyList.innerHTML = `<li class="history-empty">Loading…</li>`;
  try {
    const history = await apiGet(`/products/${id}/history`);
    renderHistory(history);
  } catch (e) {
    historyList.innerHTML = `<li class="history-empty">Couldn't load history.</li>`;
  }
}

function renderHistory(entries) {
  const historyList = document.getElementById("historyList");
  if (entries.length === 0) {
    historyList.innerHTML = `<li class="history-empty">No stock changes yet.</li>`;
    return;
  }
  historyList.innerHTML = entries
    .slice(0, 10)
    .map((h) => {
      const sign = h.delta > 0 ? "+" : "";
      const cls = h.delta > 0 ? "positive" : "negative";
      const when = new Date(h.created_at + "Z").toLocaleString(undefined, {
        month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
      });
      return `
        <li class="history-row">
          <span>${h.previous_qty} → ${h.new_qty} <span class="history-change ${cls}">(${sign}${h.delta})</span></span>
          <span class="history-meta">${h.source} · ${when}</span>
        </li>`;
    })
    .join("");
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
}

openAddBtn.addEventListener("click", openAddModal);
closeModalBtn.addEventListener("click", closeModal);
cancelBtn.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (e) => {
  if (e.target === modalBackdrop) closeModal();
});

productForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.classList.add("hidden");

  const id = document.getElementById("productId").value;
  const priceRon = parseFloat(document.getElementById("fPrice").value || "0");

  const payload = {
    name: document.getElementById("fName").value.trim(),
    brand: document.getElementById("fBrand").value.trim(),
    category: document.getElementById("fCategory").value.trim(),
    flavour: document.getElementById("fFlavour").value.trim(),
    weight: parseFloat(document.getElementById("fWeight").value || "0"),
    price: Math.round(priceRon * 100),
    stock_qty: parseInt(document.getElementById("fStock").value || "0", 10),
    expiration_date: document.getElementById("fExpiration").value || null,
  };

  try {
    if (id) {
      await apiSend(`/products/${id}`, "PUT", payload);
      showToast("Product updated");
    } else {
      await apiSend("/products", "POST", payload);
      showToast("Product added");
    }
    closeModal();
    await loadAll();
  } catch (err) {
    formError.textContent = err.message;
    formError.classList.remove("hidden");
  }
});

// ---------- Delete modal ----------
const closeDeleteBtn = document.getElementById("closeDeleteBtn");
const cancelDeleteBtn = document.getElementById("cancelDeleteBtn");
const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

function openDeleteModal(id) {
  const p = products.find((x) => x.id === id);
  if (!p) return;
  deleteTargetId = id;
  deleteCopy.textContent = `“${p.name}” (${p.brand}) will be permanently removed.`;
  deleteBackdrop.classList.remove("hidden");
}

function closeDeleteModal() {
  deleteBackdrop.classList.add("hidden");
  deleteTargetId = null;
}

closeDeleteBtn.addEventListener("click", closeDeleteModal);
cancelDeleteBtn.addEventListener("click", closeDeleteModal);
deleteBackdrop.addEventListener("click", (e) => {
  if (e.target === deleteBackdrop) closeDeleteModal();
});

confirmDeleteBtn.addEventListener("click", async () => {
  if (deleteTargetId == null) return;
  try {
    await apiDelete(`/products/${deleteTargetId}`);
    showToast("Product deleted");
    closeDeleteModal();
    await loadAll();
  } catch (err) {
    showToast(err.message);
  }
});

// ---------- Init ----------
loadAll();