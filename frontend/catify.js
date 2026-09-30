"use strict";
const $ = (i) => document.getElementById(i);
const on = (id, ev, fn) => { const e = $(id); if (e) e.addEventListener(ev, fn); };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const lei = (bani) => (bani / 100).toFixed(2) + " lei";
const PAGE = document.body.dataset.page;
const S = { stats: {}, products: [], cats: [], hist: [] };
let monthSel = "all";

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (r.status === 204) return null;
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Request failed (" + r.status + ")");
  return d;
}
async function load() {
  const [stats, products, cats, hist] = await Promise.all([
    api("/api/stats"), api("/api/products"), api("/api/cats"), api("/api/stock-history?limit=1000"),
  ]);
  Object.assign(S, { stats, products, cats, hist });
}
async function act(fn) {
  try { await fn(); await load(); render(); return true; }
  catch (e) { alert(e.message); return false; }
}

const T = () => S.stats.low_stock_threshold ?? 2;
const needs = (p) => p.stock_qty <= T();
const prod = (id) => S.products.find((p) => p.id === +id);
const price = (id) => (prod(id) ? prod(id).price : 0);
function expState(p) {
  if (!p.expiration_date) return "";
  const d = (new Date(p.expiration_date + "T00:00:00") - new Date().setHours(0, 0, 0, 0)) / 864e5;
  return d < 0 ? "past" : d <= (S.stats.expiring_soon_days ?? 30) ? "soon" : "";
}
const opts = (list, f) => list.map((x) => `<option value="${x.id}">${esc(f(x))}</option>`).join("");
function keep(sel, html) { const v = sel.value; sel.innerHTML = html; if (v) sel.value = v; }
const utc = (s) => new Date(s.replace(" ", "T") + "Z");
const mkey = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
const mlabel = (k) => { const [y, m] = k.split("-"); return new Date(+y, +m - 1, 1).toLocaleDateString([], { month: "long", year: "numeric" }); };
const forCats = (p) => (p.cats || []).map((c) => c.name).join(", ");

async function feed(catId, prodId, qty, msg) {
  const q = parseInt(qty, 10), p = prod(prodId), c = S.cats.find((x) => x.id === +catId);
  if (!c) { msg.textContent = "Add a cat first."; return; }
  if (!p) { msg.textContent = "Add a food first."; return; }
  if (!(q > 0)) { msg.textContent = "Enter a whole number of units."; return; }
  if (q > p.stock_qty) { msg.textContent = "Only " + p.stock_qty + " of " + p.name + " left."; return; }
  const ok = await act(() => api(`/api/products/${p.id}/adjust-stock`, { method: "POST", body: { delta: -q, cat_id: c.id } }));
  if (ok) msg.textContent = `Fed ${c.name} ${q} unit(s) of ${p.name}.`;
}

/* ---------- Home ---------- */
function renderHome() {
  const s = S.stats, fed = S.hist.filter((h) => h.source === "feed");
  $("stats").innerHTML = [
    ["Foods", s.total_skus], ["Running low", s.low_stock_count], ["Out of stock", s.out_of_stock_count],
    ["Expiring soon", s.expiring_soon_count], ["Stock value", (s.total_value_ron ?? 0).toFixed(2) + " lei"],
    ["Cats", S.cats.length], ["Feedings", fed.length],
  ].map((x) => `<div class="stat"><small>${x[0]}</small><b>${x[1]}</b></div>`).join("");

  keep($("fCat"), opts(S.cats, (c) => c.name));
  keep($("fFood"), opts(S.products, (p) => `${p.name} – ${p.brand} (${p.stock_qty})`));

  $("catGrid").innerHTML = S.cats.length ? S.cats.map((c) => {
    const f = fed.filter((h) => h.cat_id === c.id);
    const cost = f.reduce((a, h) => a - h.delta * price(h.product_id), 0);
    return `<div class="panel"><div style="display:flex;justify-content:space-between;align-items:center"><b>🐱 ${esc(c.name)}</b>
      <button class="sm" data-a="delCat" data-id="${c.id}">Remove</button></div>
      <div class="sub mono" style="margin:6px 0 0;font-size:13px">${f.length} feedings · ≈ ${lei(cost)}</div></div>`;
  }).join("") : '<div class="empty">No cats yet.</div>';

  const low = S.products.filter(needs).sort((a, b) => a.stock_qty - b.stock_qty);
  $("homeRows").innerHTML = low.length ? low.map((p) =>
    `<tr><td>${esc(p.name)}<small class="m">${esc(p.brand)}</small></td><td class="n need">${p.stock_qty} units</td>
     <td class="n ${expState(p)}">${p.expiration_date || "–"}</td><td class="n">${lei(p.price * p.stock_qty)}</td></tr>`
  ).join("") : `<tr><td class="empty" colspan="4">${S.products.length ? "Everything is stocked." : "No food yet. Add some in the Pantry."}</td></tr>`;
}

/* ---------- Pantry ---------- */
function fillFilters() {
  const uniq = (k) => [...new Set(S.products.map((p) => p[k]).filter(Boolean))].sort();
  keep($("fc"), '<option value="">All cats</option>' + opts(S.cats, (c) => c.name));
  keep($("fk"), '<option value="">All categories</option>' + uniq("category").map((x) => `<option>${esc(x)}</option>`).join(""));
  keep($("ff"), '<option value="">All flavours</option>' + uniq("flavour").map((x) => `<option>${esc(x)}</option>`).join(""));
}
function renderCards() {
  const q = $("q").value.trim().toLowerCase(), fc = $("fc").value, fk = $("fk").value, ff = $("ff").value, fs = $("fs").value, so = $("so").value;
  const L = S.products.filter((p) => {
    if (q && [p.name, p.brand, p.flavour, p.category].join(" ").toLowerCase().indexOf(q) < 0) return false;
    if (fc && p.cat_ids.length && !p.cat_ids.includes(+fc)) return false;
    if (fk && p.category !== fk) return false;
    if (ff && p.flavour !== ff) return false;
    if (fs === "have" && needs(p)) return false;
    if (fs === "need" && !needs(p)) return false;
    if (fs === "out" && p.stock_qty > 0) return false;
    return true;
  });
  L.sort((a, b) => so === "stock" ? a.stock_qty - b.stock_qty : so === "price" ? a.price - b.price
    : so === "exp" ? (a.expiration_date || "9999").localeCompare(b.expiration_date || "9999") : a.name.localeCompare(b.name));
  $("cards").innerHTML = L.length ? L.map((p) => {
    const box = p.units_per_box > 1, chips = [p.category, p.flavour, p.weight ? p.weight + "g" : "", box ? "box of " + p.units_per_box : ""].filter(Boolean);
    return `<article class="fc"><span class="st ${needs(p) ? "n" : "o"}">${needs(p) ? "NEED MORE" : "STOCKED"}</span>
      <h3>${esc(p.name)}</h3><div class="br">${esc(p.brand)}</div>${p.cats.length ? `<div class="for">For: ${esc(forCats(p))}</div>` : ""}
      <div class="chips">${chips.map((x) => `<span>${esc(x)}</span>`).join("")}</div>
      <div class="r"><span>Price per unit</span><b class="big">${lei(p.price)}</b></div>
      ${box ? `<div class="r"><span>Box price</span><em>≈ ${lei(p.price * p.units_per_box)}</em></div>` : ""}
      <div class="r"><span>You have</span><b class="${needs(p) ? "need" : ""}">${p.stock_qty}</b></div>
      <div class="r"><span>Use by</span><b class="${expState(p)}">${p.expiration_date || "–"}</b></div>
      <button class="feed" data-a="feed" data-id="${p.id}" ${p.stock_qty > 0 ? "" : "disabled"}>🐾 Feed</button>
      <div class="btns"><button class="sm" data-a="rs" data-id="${p.id}">Restock</button><button class="sm" data-a="edit" data-id="${p.id}">Edit</button><button class="sm" data-a="delFood" data-id="${p.id}">Delete</button></div></article>`;
  }).join("") : `<div class="empty">${S.products.length ? "No matches." : "No food yet. Tap “+ Add food”."}</div>`;
}
function renderPantry() {
  fillFilters();
  const fo = opts(S.products, (p) => `${p.name} – ${p.brand} (${p.stock_qty})`);
  keep($("rFood"), fo); keep($("dFoodS"), fo); keep($("dCatS"), opts(S.cats, (c) => c.name));
  renderCards();
}
function openFood(p) {
  $("foodForm").reset();
  $("nId").value = p ? p.id : ""; $("dfT").textContent = p ? "Edit food" : "Add food";
  $("nCats").innerHTML = S.cats.map((c) => `<label><input type="checkbox" value="${c.id}" ${p && p.cat_ids.includes(c.id) ? "checked" : ""}> ${esc(c.name)}</label>`).join("") || '<span class="sub">No cats yet.</span>';
  if (p) {
    $("nName").value = p.name; $("nBrand").value = p.brand; $("nCat").value = p.category; $("nFlav").value = p.flavour;
    $("nW").value = p.weight || ""; $("nPrice").value = (p.price / 100).toFixed(2); $("nUpb").value = p.units_per_box || "";
    $("nUnits").value = p.stock_qty; $("nExp").value = p.expiration_date || "";
  }
  $("dFood").showModal(); $("nName").focus();
}
function openRestock(id) {
  if (!S.products.length) { openFood(); return; }
  if (id) $("rFood").value = id;
  $("dRestock").showModal(); $("rQty").focus();
}

/* ---------- History ---------- */
function renderHistory() {
  const M = {};
  S.hist.forEach((h) => {
    if (h.source === "delete") return;
    const k = mkey(utc(h.created_at)), m = M[k] || (M[k] = { n: 0, q: 0, eat: 0, buy: 0 });
    if (h.source === "feed") { m.n++; m.q -= h.delta; m.eat -= h.delta * price(h.product_id); }
    else if (h.delta > 0) m.buy += h.delta * price(h.product_id);
  });
  const keys = Object.keys(M).sort().reverse();
  $("monthRows").innerHTML = keys.length ? keys.map((k) =>
    `<tr class="pick" data-m="${k}"><td>${mlabel(k)}</td><td class="n">${M[k].n}</td><td class="n">${M[k].q}</td><td class="n">${lei(M[k].eat)}</td><td class="n">${lei(M[k].buy)}</td></tr>`
  ).join("") : '<tr><td class="empty" colspan="5">No feedings or purchases yet.</td></tr>';

  const all = [...new Set(S.hist.map((h) => mkey(utc(h.created_at))))].sort().reverse();
  if (monthSel !== "all" && !all.includes(monthSel)) monthSel = "all";
  $("mFilter").innerHTML = '<option value="all">All months</option>' + all.map((k) => `<option value="${k}">${mlabel(k)}</option>`).join("");
  $("mFilter").value = monthSel;
  const src = $("sFilter").value, LBL = { create: "Added", edit: "Edited", adjust: "Adjusted", delete: "Deleted" };
  const ev = S.hist.filter((h) => (monthSel === "all" || mkey(utc(h.created_at)) === monthSel) && (!src || h.source === src));
  const shown = monthSel === "all" ? ev.slice(0, 100) : ev;
  $("logRows").innerHTML = shown.length ? shown.map((h) =>
    `<tr><td>${utc(h.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</td>
     <td>${h.source === "feed" ? "Fed " + esc(h.cat_name || "") : LBL[h.source] || esc(h.source)}</td>
     <td>${esc(h.product_name)}<small class="m">${esc(h.product_brand)}</small></td>
     <td class="n">${h.delta > 0 ? "+" : h.delta < 0 ? "−" : ""}${Math.abs(h.delta)}</td><td class="n">${h.previous_qty} → ${h.new_qty}</td></tr>`
  ).join("") : '<tr><td class="empty" colspan="5">Nothing yet.</td></tr>';
}

const render = () => ({ home: renderHome, pantry: renderPantry, history: renderHistory })[PAGE]();

/* ---------- Events ---------- */
document.querySelectorAll("nav a").forEach((a) => a.classList.toggle("on", a.dataset.p === PAGE));
$("eye").textContent = { home: "At home", pantry: "My pantry", history: "Records" }[PAGE];
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));

on("feedForm", "submit", (e) => { e.preventDefault(); feed($("fCat").value, $("fFood").value, $("fQty").value, $("feedMsg")); });
on("openCat", "click", () => { $("dCat").showModal(); $("cName").focus(); });
on("catForm", "submit", (e) => {
  e.preventDefault();
  act(() => api("/api/cats", { method: "POST", body: { name: $("cName").value.trim() } })).then((ok) => {
    if (ok) { e.target.reset(); $("dCat").close(); }
  });
});

["q", "fc", "fk", "ff", "fs", "so"].forEach((i) => { on(i, "input", renderCards); on(i, "change", renderCards); });
on("openAdd", "click", () => openFood());
on("openRestock", "click", () => openRestock());
on("foodForm", "submit", (e) => {
  e.preventDefault();
  const id = $("nId").value;
  const body = {
    name: $("nName").value.trim(), brand: $("nBrand").value.trim(), category: $("nCat").value.trim(), flavour: $("nFlav").value.trim(),
    weight: parseFloat($("nW").value) || 0, price: Math.round(parseFloat($("nPrice").value) * 100) || 0,
    units_per_box: parseInt($("nUpb").value, 10) || null, stock_qty: parseInt($("nUnits").value, 10) || 0,
    expiration_date: $("nExp").value || null,
    cat_ids: [...document.querySelectorAll("#nCats input:checked")].map((i) => +i.value),
  };
  act(() => api(id ? "/api/products/" + id : "/api/products", { method: id ? "PUT" : "POST", body })).then((ok) => { if (ok) $("dFood").close(); });
});
on("restockForm", "submit", (e) => {
  e.preventDefault();
  const p = prod($("rFood").value), q = parseInt($("rQty").value, 10);
  if (!p || !(q > 0)) return;
  const delta = $("rUnit").value === "b" ? q * (p.units_per_box || 1) : q;
  const patch = {};
  if ($("rPrice").value) patch.price = Math.round(parseFloat($("rPrice").value) * 100);
  if ($("rExp").value) patch.expiration_date = $("rExp").value;
  act(async () => {
    await api(`/api/products/${p.id}/adjust-stock`, { method: "POST", body: { delta } });
    if (Object.keys(patch).length) await api("/api/products/" + p.id, { method: "PUT", body: patch });
  }).then((ok) => { if (ok) { e.target.reset(); $("rQty").value = 1; $("dRestock").close(); } });
});
on("feedDForm", "submit", (e) => { e.preventDefault(); feed($("dCatS").value, $("dFoodS").value, $("dQty").value, $("dMsg")); });

on("mFilter", "change", (e) => { monthSel = e.target.value; renderHistory(); });
on("sFilter", "change", renderHistory);

document.addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-m]");
  if (row) { monthSel = row.dataset.m; renderHistory(); $("mFilter").scrollIntoView({ behavior: "smooth", block: "center" }); return; }
  const b = e.target.closest("button[data-a]");
  if (!b) return;
  const a = b.dataset.a, p = prod(b.dataset.id);
  if (a === "feed" && p) {
    if (!S.cats.length) { alert("Add a cat first (Home page)."); return; }
    $("dFoodS").value = p.id; if (p.cat_ids.length === 1) $("dCatS").value = p.cat_ids[0];
    $("dMsg").textContent = ""; $("dFeed").showModal();
  }
  if (a === "rs" && p) openRestock(p.id);
  if (a === "edit" && p) openFood(p);
  if (a === "delFood" && p && confirm("Delete " + p.name + "? Its history stays.")) act(() => api("/api/products/" + p.id, { method: "DELETE" }));
  if (a === "delCat" && confirm("Remove this cat? It is un-tagged from any food.")) act(() => api("/api/cats/" + b.dataset.id, { method: "DELETE" }));
});

load().then(render).catch((e) => { document.querySelector("main").insertAdjacentHTML("afterbegin", `<p class="need">Could not load data: ${esc(e.message)}</p>`); });