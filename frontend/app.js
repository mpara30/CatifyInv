const API = "/api";

// ---------- State ----------
let products = [];
let deleteTargetId = null;
let cats = [];
let catDeleteTargetId = null;

// ---------- Elements ----------
const grid = document.getElementById("productGrid");
const emptyState = document.getElementById("emptyState");

const searchInput = document.getElementById("searchInput");
const catFilter = document.getElementById("catFilter");
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
  return `${ron.toFixed(2)} lei`;
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
  if (catFilter.value) params.set("cat_id", catFilter.value);
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

// ---------- Cats ----------
async function loadCats() {
  cats = await apiGet("/cats");
  populateCatFilter();
  renderCatCheckboxes();
}

function populateCatFilter() {
  const current = catFilter.value;
  catFilter.querySelectorAll("option[data-dynamic]").forEach((o) => o.remove());
  cats.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    opt.dataset.dynamic = "true";
    catFilter.appendChild(opt);
  });
  if (cats.some((c) => String(c.id) === current)) catFilter.value = current;
}

function renderCatCheckboxes(selectedIds) {
  const selected = new Set(selectedIds || []);
  const container = document.getElementById("catCheckboxes");
  if (cats.length === 0) {
    container.innerHTML = `<span class="history-empty">No cats added yet — use the 🐱 Cats button to add one.</span>`;
    return;
  }
  container.innerHTML = cats
    .map(
      (c) => `
      <label class="cat-checkbox-label">
        <input type="checkbox" class="cat-checkbox" value="${c.id}" ${selected.has(c.id) ? "checked" : ""}>
        ${escapeHtml(c.name)}
      </label>`
    )
    .join("");
}

function getSelectedCatIds() {
  return Array.from(document.querySelectorAll(".cat-checkbox:checked")).map((cb) => Number(cb.value));
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
      ${p.cats && p.cats.length ? `<p class="card-cats">For: ${p.cats.map((c) => escapeHtml(c.name)).join(", ")}</p>` : ""}
      <div class="card-tags">
        ${p.category ? `<span class="tag">${escapeHtml(p.category)}</span>` : ""}
        ${p.flavour ? `<span class="tag">${escapeHtml(p.flavour)}</span>` : ""}
        ${p.weight ? `<span class="tag">${p.weight}g</span>` : ""}
        ${p.units_per_box ? `<span class="tag">box of ${p.units_per_box}</span>` : ""}
      </div>
      <div class="card-row">
        <span class="card-row-label">Price per unit</span>
        <span class="card-row-value">${formatMoney(p.price_ron)}</span>
      </div>
      ${p.units_per_box ? `
      <div class="card-row card-row-sub">
        <span class="card-row-label">Box price</span>
        <span class="units-hint">≈ ${formatMoney(p.price_ron * p.units_per_box)}</span>
      </div>` : ""}
      <div class="card-row">
        <span class="card-row-label">You have</span>
        <span class="card-row-value">${p.stock_qty}</span>
      </div>
      <div class="card-row">
        <span class="card-row-label">Use by</span>
        <span class="card-row-value ${expClass}">${p.expiration_date || "—"}</span>
      </div>
      <button class="btn btn-feed" data-action="feed" data-id="${p.id}" ${p.stock_qty === 0 ? "disabled" : ""}>🐾 Feed</button>
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
  await Promise.all([loadProducts(), loadStats(), loadCats()]);
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
  } else if (action === "feed") {
    const product = products.find((x) => x.id === id);
    handleFeedClick(product, btn);
  }
});

// ---------- Feed: pick which cat, when it matters ----------
async function feedProduct(id, catId, btn) {
  if (btn) btn.disabled = true;
  try {
    const body = { delta: -1 };
    if (catId != null) body.cat_id = catId;
    await apiSend(`/products/${id}/adjust-stock`, "POST", body);
    const cat = catId != null ? cats.find((c) => c.id === catId) : null;
    showToast(cat ? `Fed ${cat.name}! 🐾` : "Fed! 🐾");
    await loadAll();
  } catch (err) {
    showToast(err.message);
  }
}

function handleFeedClick(product, btn) {
  // Eligible cats: whoever this product is tagged to, or every cat if it's
  // an "all cats" product. No cats registered at all -> just feed, no ask.
  const eligible = product.cat_ids && product.cat_ids.length
    ? product.cats
    : cats;

  if (eligible.length <= 1) {
    feedProduct(product.id, eligible.length === 1 ? eligible[0].id : null, btn);
    return;
  }
  openFeedModal(product, eligible);
}

// ---------- Filters wiring ----------
searchInput.addEventListener("input", debounce(loadProducts, 250));
[catFilter, categoryFilter, flavourFilter, stockFilter, sortSelect].forEach((el) =>
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
  document.getElementById("fUnitsPerBox").value = "";
  document.getElementById("fBoxesToAdd").value = "";
  document.getElementById("fIsBox").checked = false;
  setBoxMode(false);
  document.getElementById("boxSection").classList.remove("hidden");
  renderCatCheckboxes();
  modalTitle.textContent = "Add food";
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
  // units_per_box isn't user-editable here — box options only apply when adding —
  // but we keep its current value so editing other fields doesn't clear it.
  document.getElementById("fUnitsPerBox").value = p.units_per_box || "";
  document.getElementById("fBoxesToAdd").value = "";
  document.getElementById("fIsBox").checked = false;
  document.getElementById("boxSection").classList.add("hidden");
  document.getElementById("individualQtyRow").classList.remove("hidden");
  document.getElementById("fPriceLabel").textContent = "Price per unit (RON)";
  document.getElementById("fPrice").placeholder = "9.99 per unit";
  document.getElementById("pricePerUnitHint").classList.add("hidden");
  document.getElementById("fStock").value = p.stock_qty;
  document.getElementById("fExpiration").value = p.expiration_date || "";
  renderCatCheckboxes(p.cat_ids);
  modalTitle.textContent = "Edit food";
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

const HISTORY_SOURCE_LABELS = {
  create: "added", edit: "edited", adjust: "adjusted", delete: "removed", feed: "fed",
};

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
      const label = HISTORY_SOURCE_LABELS[h.source] || h.source;
      const catPart = h.cat_name ? ` · ${escapeHtml(h.cat_name)}` : "";
      return `
        <li class="history-row">
          <span>${h.previous_qty} → ${h.new_qty} <span class="history-change ${cls}">(${sign}${h.delta})</span></span>
          <span class="history-meta">${label}${catPart} · ${when}</span>
        </li>`;
    })
    .join("");
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
}

openAddBtn.addEventListener("click", openAddModal);
closeModalBtn.addEventListener("click", closeModal);

// Box mode is all-or-nothing: checked shows only box fields and hides the
// raw quantity field entirely; unchecked is the plain single-item flow.
function setBoxMode(isBox) {
  const boxDetails = document.getElementById("boxDetails");
  const individualRow = document.getElementById("individualQtyRow");
  const unitsInput = document.getElementById("fUnitsPerBox");
  const boxesInput = document.getElementById("fBoxesToAdd");
  const priceLabel = document.getElementById("fPriceLabel");
  const priceInput = document.getElementById("fPrice");
  const priceHint = document.getElementById("pricePerUnitHint");

  if (isBox) {
    boxDetails.classList.remove("hidden");
    individualRow.classList.add("hidden");
    unitsInput.required = true;
    boxesInput.required = true;
    priceLabel.textContent = "Price per box (RON)";
    priceInput.placeholder = "114.99 for the whole box";
  } else {
    boxDetails.classList.add("hidden");
    individualRow.classList.remove("hidden");
    unitsInput.required = false;
    boxesInput.required = false;
    priceLabel.textContent = "Price per unit (RON)";
    priceInput.placeholder = "9.99 per unit";
    priceHint.classList.add("hidden");
  }
  updatePriceHint();
}
document.getElementById("fIsBox").addEventListener("change", (e) => setBoxMode(e.target.checked));

// While in box mode, show what the entered box price works out to per unit —
// that per-unit figure is what actually gets saved.
function updatePriceHint() {
  const isBox = document.getElementById("fIsBox").checked;
  const priceHint = document.getElementById("pricePerUnitHint");
  if (!isBox) {
    priceHint.classList.add("hidden");
    return;
  }
  const boxPrice = parseFloat(document.getElementById("fPrice").value);
  const unitsPerBox = parseInt(document.getElementById("fUnitsPerBox").value, 10);
  if (boxPrice > 0 && unitsPerBox > 0) {
    priceHint.textContent = `= ${(boxPrice / unitsPerBox).toFixed(2)} lei per unit`;
    priceHint.classList.remove("hidden");
  } else {
    priceHint.classList.add("hidden");
  }
}
document.getElementById("fPrice").addEventListener("input", updatePriceHint);
document.getElementById("fUnitsPerBox").addEventListener("input", updatePriceHint);

// Whenever units-per-box and boxes-you-have both have values, compute the
// total individual units into the (hidden, but still submitted) quantity field.
function recalcStockFromBoxes() {
  const unitsPerBox = parseInt(document.getElementById("fUnitsPerBox").value, 10);
  const boxes = parseInt(document.getElementById("fBoxesToAdd").value, 10);
  if (unitsPerBox > 0 && boxes > 0) {
    document.getElementById("fStock").value = unitsPerBox * boxes;
  }
}
document.getElementById("fUnitsPerBox").addEventListener("input", recalcStockFromBoxes);
document.getElementById("fBoxesToAdd").addEventListener("input", recalcStockFromBoxes);
cancelBtn.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", (e) => {
  if (e.target === modalBackdrop) closeModal();
});

productForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.classList.add("hidden");

  const id = document.getElementById("productId").value;
  const priceEnteredRon = parseFloat(document.getElementById("fPrice").value || "0");

  let unitsPerBox;
  let pricePerUnitRon;
  if (id) {
    // Editing: box options aren't shown, so just preserve whatever value
    // was loaded from the product (don't let this silently wipe it out),
    // and the price field is always per-unit here.
    const raw = document.getElementById("fUnitsPerBox").value.trim();
    unitsPerBox = raw ? parseInt(raw, 10) : null;
    pricePerUnitRon = priceEnteredRon;
  } else {
    // Adding: units_per_box only applies if "this comes in a box" is checked.
    const isBox = document.getElementById("fIsBox").checked;
    const raw = document.getElementById("fUnitsPerBox").value.trim();
    unitsPerBox = isBox && raw ? parseInt(raw, 10) : null;
    // In box mode the entered price is for the WHOLE box — convert to per-unit
    // before saving, since price always has to match stock_qty's unit.
    pricePerUnitRon = isBox && unitsPerBox
      ? priceEnteredRon / unitsPerBox
      : priceEnteredRon;
  }

  const payload = {
    name: document.getElementById("fName").value.trim(),
    brand: document.getElementById("fBrand").value.trim(),
    category: document.getElementById("fCategory").value.trim(),
    flavour: document.getElementById("fFlavour").value.trim(),
    weight: parseFloat(document.getElementById("fWeight").value || "0"),
    price: Math.round(pricePerUnitRon * 100),
    units_per_box: unitsPerBox,
    stock_qty: parseInt(document.getElementById("fStock").value || "0", 10),
    expiration_date: document.getElementById("fExpiration").value || null,
    cat_ids: getSelectedCatIds(),
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

// ---------- Feed: pick which cat modal ----------
const feedBackdrop = document.getElementById("feedBackdrop");
const closeFeedBtn = document.getElementById("closeFeedBtn");
const feedCatsList = document.getElementById("feedCatsList");
let feedTargetProduct = null;

function openFeedModal(product, eligibleCats) {
  feedTargetProduct = product;
  feedCatsList.innerHTML = eligibleCats
    .map(
      (c) => `
      <li class="cat-row cat-row-select" data-cat-id="${c.id}">
        <span>${escapeHtml(c.name)}</span>
        <span class="cat-row-feed-icon">🐾</span>
      </li>`
    )
    .join("");
  feedBackdrop.classList.remove("hidden");
}

function closeFeedModal() {
  feedBackdrop.classList.add("hidden");
  feedTargetProduct = null;
}

closeFeedBtn.addEventListener("click", closeFeedModal);
feedBackdrop.addEventListener("click", (e) => {
  if (e.target === feedBackdrop) closeFeedModal();
});

feedCatsList.addEventListener("click", (e) => {
  const row = e.target.closest("li[data-cat-id]");
  if (!row || !feedTargetProduct) return;
  const catId = Number(row.dataset.catId);
  const productId = feedTargetProduct.id;
  closeFeedModal();
  feedProduct(productId, catId, null);
});

// ---------- Manage cats modal ----------
const openCatsBtn = document.getElementById("openCatsBtn");
const catsBackdrop = document.getElementById("catsBackdrop");
const closeCatsBtn = document.getElementById("closeCatsBtn");
const addCatForm = document.getElementById("addCatForm");
const catFormError = document.getElementById("catFormError");
const catsList = document.getElementById("catsList");

function renderCatsList() {
  if (cats.length === 0) {
    catsList.innerHTML = `<li class="history-empty">No cats yet — add one above.</li>`;
    return;
  }
  catsList.innerHTML = cats
    .map(
      (c) => `
      <li class="cat-row">
        <span>${escapeHtml(c.name)}</span>
        <button type="button" class="cat-row-delete" data-cat-id="${c.id}">Remove</button>
      </li>`
    )
    .join("");
}

function openCatsModal() {
  catFormError.classList.add("hidden");
  addCatForm.reset();
  renderCatsList();
  catsBackdrop.classList.remove("hidden");
  document.getElementById("fCatName").focus();
}

function closeCatsModal() {
  catsBackdrop.classList.add("hidden");
}

openCatsBtn.addEventListener("click", openCatsModal);
closeCatsBtn.addEventListener("click", closeCatsModal);
catsBackdrop.addEventListener("click", (e) => {
  if (e.target === catsBackdrop) closeCatsModal();
});

addCatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  catFormError.classList.add("hidden");
  const name = document.getElementById("fCatName").value.trim();
  if (!name) return;
  try {
    await apiSend("/cats", "POST", { name });
    await loadCats();
    renderCatsList();
    addCatForm.reset();
    document.getElementById("fCatName").focus();
  } catch (err) {
    catFormError.textContent = err.message;
    catFormError.classList.remove("hidden");
  }
});

catsList.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-cat-id]");
  if (!btn) return;
  const catId = Number(btn.dataset.catId);
  const cat = cats.find((c) => c.id === catId);
  if (!cat) return;
  if (!window.confirm(`Remove "${cat.name}"? Foods tagged only to them will become "all cats".`)) {
    return;
  }
  btn.disabled = true;
  try {
    await apiDelete(`/cats/${catId}`);
    await loadCats();
    renderCatsList();
    await loadProducts();
  } catch (err) {
    showToast(err.message);
  }
});

// ---------- Init ----------
loadAll();