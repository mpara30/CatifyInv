# CatifyInv — Backlog

Copy each ticket below into Jira (Summary / Description / Acceptance Criteria map directly to Jira fields). Suggested project key: `CFI`.

---

## CFI-1: Add per-product reorder threshold
**Type:** Story | **Priority:** Medium | **Labels:** inventory, backend

**Description:**
Currently "low stock" uses a single hardcoded threshold (10 units) for every product in `/api/stats`. Different products need different thresholds — a slow-moving premium raw food might need reordering at 5 units, while a high-turnover treat might need it at 50.

**Acceptance Criteria:**
- [ ] Add a `reorder_threshold` column to the `products` table (nullable int, falls back to a global default if unset)
- [ ] Add `reorder_threshold` to the add/edit product form
- [ ] `/api/stats` low-stock count uses each product's own threshold
- [ ] Product cards show a "Low stock" badge based on the product's own threshold, not a global constant

---

## CFI-2: CSV import for bulk product catalog loading
**Type:** Story | **Priority:** Medium | **Labels:** inventory, backend

**Description:**
Let an admin upload a CSV to bulk-create or bulk-update products instead of adding them one at a time through the UI.

**Acceptance Criteria:**
- [ ] `POST /api/products/import` accepts a CSV file (multipart or raw text)
- [ ] Validates each row using the same rules as the single-product create endpoint
- [ ] Returns a per-row success/error summary (not all-or-nothing)
- [ ] Frontend: an "Import CSV" button with a file picker and a results summary after upload

---

## CFI-3: CSV export of current inventory
**Type:** Story | **Priority:** Low | **Labels:** inventory, backend

**Description:**
Let an admin download the current product catalog (respecting active filters) as a CSV for use in a spreadsheet.

**Acceptance Criteria:**
- [ ] `GET /api/products/export` returns a CSV, honoring the same filter query params as `GET /api/products`
- [ ] Frontend: an "Export CSV" button in the toolbar that downloads the currently filtered view

---

## CFI-4: Stock change history / audit log — ✅ Done
**Type:** Story | **Priority:** Medium | **Labels:** inventory, backend

**Description:**
Track every stock change (manual edit, +/- quick adjust) so it's possible to answer "what happened to this product's stock over time."

**Acceptance Criteria:**
- [ ] New `stock_history` table: product_id, previous_qty, new_qty, delta, source (`edit` | `adjust`), timestamp
- [ ] Every write to `stock_qty` (via edit or adjust-stock) inserts a history row
- [ ] `GET /api/products/<id>/history` returns the change log for a product
- [ ] (Optional, later) simple history view in the product edit modal

---

## CFI-5: Admin authentication for write actions
**Type:** Story | **Priority:** High (before any multi-user or public deployment) | **Labels:** security, backend

**Description:**
All write endpoints (`POST`/`PUT`/`DELETE`/`adjust-stock`) are currently open to anyone who can reach the API. Needed before this is used by more than one trusted person locally.

**Acceptance Criteria:**
- [ ] Basic auth or token-based auth on all write endpoints
- [ ] Read endpoints (`GET`) remain open, or are gated separately depending on deployment needs
- [ ] Frontend: login flow, and write actions (add/edit/delete/adjust) disabled or hidden when logged out
- [ ] Document the auth setup in the README

---

## CFI-6: Migrate from SQLite to Postgres (or MySQL)
**Type:** Task | **Priority:** Low (until concurrent-write load becomes a real issue) | **Labels:** infra, backend

**Description:**
SQLite is fine for single-user local use but won't hold up well under concurrent writes from multiple users. Migrate to a server-based database when that becomes a real requirement.

**Acceptance Criteria:**
- [ ] Introduce an ORM or query layer that isn't SQLite-specific (or write a Postgres-specific `database.py`)
- [ ] Migration script to move existing SQLite data to the new database
- [ ] Update `requirements.txt` and README setup instructions
- [ ] Confirm all existing API behavior (filters, sorting, stats) still works against the new database

---

## CFI-7: Inventory value breakdown by category/brand
**Type:** Story | **Priority:** Low | **Labels:** inventory, frontend

**Description:**
The dashboard currently shows one total inventory value figure. Breaking it down by category or brand would help spot where value/risk is concentrated (e.g. a lot of capital tied up in one brand nearing expiration).

**Acceptance Criteria:**
- [ ] `/api/stats` optionally returns value grouped by category and by brand
- [ ] Frontend: a simple breakdown view (table or small bar chart) alongside the existing stats

---

## CFI-8: Barcode / SKU field for receiving & scanning workflows
**Type:** Story | **Priority:** Low | **Labels:** inventory, backend

**Description:**
Add a dedicated barcode/UPC field (distinct from the internal `id`) so products can eventually be scanned in at receiving or checkout.

**Acceptance Criteria:**
- [ ] Add a `barcode` column (unique, nullable) to `products`
- [ ] Add to add/edit form
- [ ] `GET /api/products?barcode=<code>` for fast lookup by scan

---

## CFI-9: Shopping list view
**Type:** Story | **Priority:** High | **Labels:** frontend, home-use

**User story:** As a cat owner, I want a single view that shows only what's running low or out, so that I can glance at it before heading to the store instead of scanning the whole pantry grid.

**Description:**
Builds entirely on data that already exists (`in_stock=false` and the low-stock logic behind the "Running low" badge) — this is a new view, not new backend logic.

**Acceptance Criteria:**
- [ ] New page (e.g. `/shopping-list`), linked from the top bar alongside "History"
- [ ] Lists only products that are out (`stock_qty = 0`) or running low (at/below threshold)
- [ ] Groups or visually separates "Out" from "Running low"
- [ ] Each item shows name, brand, and how many you'd typically buy (if known)
- [ ] Empty state when nothing needs restocking ("You're all stocked up")

---

## CFI-10: Consumption-based "runs out in ~N days" estimate
**Type:** Story | **Priority:** Medium | **Labels:** backend, frontend, insights

**User story:** As a cat owner, I want to see roughly when a food will run out based on how fast I've been using it, so that I can restock proactively instead of reacting to a static low/out badge.

**Description:**
`stock_history` already has enough data (past `adjust`/`edit` deltas over time) to estimate a rough daily consumption rate per product.

**Acceptance Criteria:**
- [ ] Backend computes an average daily usage rate per product from recent negative stock deltas
- [ ] `GET /api/products/<id>` (or a new endpoint) returns an estimated "runs out around" date when enough history exists
- [ ] Product card or detail view shows this estimate (e.g. "~12 days left")
- [ ] Products with too little history simply omit the estimate rather than guessing wildly

---

## CFI-11: Multi-cat support
**Type:** Story | **Priority:** Medium | **Labels:** backend, frontend, data-model

**User story:** As a cat owner with more than one cat, I want to tag which food belongs to which cat, so that the app is useful for my whole household instead of treating all food as one undifferentiated pool.

**Acceptance Criteria:**
- [ ] New `cats` table (name, and any other basic identifying info)
- [ ] Products can be associated with one or more cats (or "all cats")
- [ ] Filter the pantry view by cat
- [ ] Shopping list (CFI-9) and low-stock badges work per-cat as well as overall

---

## CFI-12: Mobile-friendliness / add-to-home-screen
**Type:** Task | **Priority:** Medium | **Labels:** frontend, mobile

**User story:** As a cat owner, I want to check and update CatifyInv from my phone — ideally installed like an app — so that I can use it standing in the kitchen or at the store, not just at a desktop.

**Acceptance Criteria:**
- [ ] Responsive layout audit across all pages (pantry, history, shopping list) at phone widths
- [ ] Web app manifest (`manifest.json`) with app name, icons, and theme color
- [ ] "Add to home screen" works on iOS and Android
- [ ] Quick stock +/- buttons are comfortably tappable on a phone screen

---

## CFI-13: Simpler add flow
**Type:** Story | **Priority:** Medium | **Labels:** frontend, ux

**User story:** As a cat owner adding a new food, I want to enter just the name and how many I have, so that adding something takes a few seconds instead of filling out a full form up front.

**Description:**
Price, weight, category, flavour, and expiration are all useful but not essential at the moment of adding — they should be editable later without blocking the initial add.

**Acceptance Criteria:**
- [ ] "Quick add" mode: name + quantity only, all other fields optional/defaulted
- [ ] Full edit form still available afterward to fill in the rest
- [ ] Existing full add form remains available (e.g. an "add details" toggle) for people who want to enter everything up front

---

## CFI-14: Specific cat feeding history
**Type:** Story | **Priority:** Medium | **Labels:** backend, frontend, data-model

**User story:** As a cat owner, I want to log which cat ate what and when, so that I can track each cat's feeding history, not just overall stock changes.

**Description:**
Distinct from CFI-11 (which just tags ownership) — this is an actual feeding log: a timestamped record of servings given to a specific cat. Depends on CFI-11 existing first (need cats as entities to log feedings against).

**Acceptance Criteria:**
- [ ] New `feeding_log` table: cat_id, product_id, amount, timestamp
- [ ] Quick "log a feeding" action (e.g. from the product card or a cat's page) that also decrements stock
- [ ] `GET /api/cats/<id>/feedings` returns a cat's feeding history
- [ ] A simple per-cat feeding timeline/view

---

## CFI-15: Product page with nutrition and ingredients
**Type:** Story | **Priority:** Medium | **Labels:** backend, frontend, data-model

**User story:** As a cat owner, I want a dedicated page for each food showing its full ingredient list and nutritional breakdown, so that I can compare foods and make informed choices for my cat, not just track quantity.

**Description:**
The original schema had nutrition fields (protein/fat/fiber/moisture/calories) before the pivot to the inventory-style Product model — this reintroduces them as an optional, richer layer on top of the current model rather than replacing it.

**Acceptance Criteria:**
- [ ] Add nutrition fields to `products`: ingredients (text), calories_per_100g, protein_percent, fat_percent, fiber_percent, moisture_percent (all optional/nullable)
- [ ] New product detail page (e.g. `/products/<id>`) showing full ingredients and nutrition breakdown
- [ ] Product cards link through to the detail page
- [ ] Add/edit form gets an optional "nutrition info" section

---

## CFI-16: Nutrition score on product page
**Type:** Story | **Priority:** Low | **Labels:** backend, frontend, insights

**User story:** As a cat owner, I want an at-a-glance quality score for each food's nutrition, so that I can quickly judge and compare foods without having to interpret raw percentages myself.

**Description:**
Depends on CFI-15 (nutrition data must exist first). Needs a defined scoring methodology — worth a short spike before building, since "nutrition score" implies a judgment call (protein source quality, ingredient order, etc.) that should be transparent rather than a black box.

**Acceptance Criteria:**
- [ ] Define and document a scoring formula/methodology (even a simple, transparent one to start)
- [ ] Score computed and shown on the product detail page (CFI-15)
- [ ] Score is explained, not just displayed as a bare number (e.g. what factors contributed)
- [ ] Product cards optionally show a compact version of the score

---

## CFI-17: History of all-time cost
**Type:** Story | **Priority:** Medium | **Labels:** backend, frontend, insights

**User story:** As a cat owner, I want to see how much I've spent on cat food over time, so that I understand my actual spending instead of just current stock value.

**Description:**
Depends on CFI-18 (price-per-box) for accurate cost basis — "all-time cost" needs to know what was actually paid at each restock, not just the current price field.

**Acceptance Criteria:**
- [ ] Each `create`/positive `adjust`/`edit` stock-history event captures the cost basis at that time (price per unit × quantity added)
- [ ] `GET /api/stats` or a new endpoint returns cumulative spend, optionally broken down by month/brand/product
- [ ] A simple spend-over-time view (e.g. on the History page or a new "Spending" section)

---

## CFI-18: Option to set price per box — ✅ Done
**Type:** Story | **Priority:** Medium | **Labels:** backend, frontend, data-model

**User story:** As a cat owner, I want to set the price per box/bag/case when I buy it, so that cost tracking reflects what I actually paid rather than one ambiguous "price" field.

**Description:**
Today's `price` field is ambiguous about what unit it represents. This clarifies pricing to be per purchase unit (box/bag/case), which CFI-17's cost history depends on.

**Acceptance Criteria:**
- [ ] Rename/clarify `price` as "price per box" (or per purchasable unit) in both schema comments and UI copy
- [ ] Add/edit form clearly labels this as the price paid per box/bag/case, not a running total
- [ ] Existing "stock value" dashboard stat continues to work correctly under the clarified meaning