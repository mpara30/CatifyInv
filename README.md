# CatifyInv

A friendly home pantry tracker for your cat's food — see what you have,
what's running low, and what needs a top-up. Built with a Flask +
SQLite REST API and a vanilla HTML/CSS/JS frontend served directly
by Flask (no build step, no CORS setup needed — same origin).

This is meant for a household, not a shop: quantities, thresholds, and
copy are tuned for "a couple of bags/cans in the cupboard," not
warehouse-scale stock.

## Project structure

```
cat_food_db/
├── app.py             # Flask app: API routes + serves the frontend
├── database.py         # SQLite connection + schema
├── models.py            # Product dataclass + row-mapping factory
├── seed.py               # Loads placeholder product data
├── requirements.txt
├── cat_food.db            # created automatically (SQLite file)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── README.md
```

## Setup

```bash
cd cat_food_db
pip install -r requirements.txt
python seed.py      # creates cat_food.db and loads 7 sample products
python app.py         # starts the app at http://127.0.0.1:5000
```

Open **http://127.0.0.1:5000** in a browser — that's the whole app.
Re-run `python seed.py` any time to reset the data back to the
placeholder set.

## Data model

Each product has:

| Field             | Type    | Notes                                              |
|-------------------|---------|----------------------------------------------------|
| id                | int     | auto-assigned                                      |
| name              | string  | required                                           |
| brand             | string  | required                                           |
| category          | string  | e.g. `dry`, `wet`, `treats`, `freeze-dried`        |
| flavour           | string  | e.g. `chicken`, `salmon`                           |
| weight            | number  | grams                                              |
| price             | int     | **stored in cents** (API also returns `price_ron`) |
| stock_qty         | int     | units in stock                                     |
| expiration_date   | string  | ISO date `YYYY-MM-DD`, nullable                    |

## Frontend features

- **Browse & filter** — search box, category/flavour/stock filters, sorting
- **Add / edit / delete** — modal form with validation
- **Quick stock adjust** — `+`/`–` buttons on each card, no need to open the edit form
- **Stock change history** — every product lifecycle event is logged: creation, manual edits to stock, quick +/- adjustments, and deletion. The edit modal shows the last 10 changes for that product, and a dedicated **History** page (linked from the top bar) shows a searchable, filterable ledger across the whole catalog — including deleted products, since each entry snapshots the product's name/brand at the time
- **Dashboard stats** — total SKUs, low-stock count, expiring-soon count, total inventory value — computed server-side across the whole catalog regardless of active filters
- Stock badges (in stock / low stock / out of stock) and expiration highlighting (upcoming vs. past)

## API endpoints

| Method | Path                             | Description                          |
|--------|-----------------------------------|----------------------------------------|
| GET    | /api/health                      | health check                           |
| GET    | /api/stats                       | dashboard aggregates (see below)       |
| GET    | /api/products                    | list products (filters below)          |
| GET    | /api/products/<id>                | get one product                        |
| POST   | /api/products                     | create a product                       |
| PUT    | /api/products/<id>                | update a product (partial OK)          |
| DELETE | /api/products/<id>                | delete a product                       |
| POST   | /api/products/<id>/adjust-stock  | bump stock_qty by a delta, clamped at 0 |
| GET    | /api/products/<id>/history        | stock change history for a product (most recent first) |
| GET    | /api/stock-history                 | stock change history across all products, including deleted ones (filters: `q`, `source`, `limit`) |

### Filtering `GET /api/products`

- `q=salmon` — search across name, brand, category, flavour
- `brand=Purrfect Bowl`
- `category=dry`
- `flavour=chicken`
- `in_stock=true` / `in_stock=false`
- `max_price=2500` (cents)
- `expiring_before=2026-12-31`
- `sort=price&order=desc`

### Adjusting stock

```bash
curl -X POST http://127.0.0.1:5000/api/products/1/adjust-stock \
  -H "Content-Type: application/json" -d '{"delta": -1}'
```

### Dashboard aggregates `GET /api/stats`

Returns `total_skus`, `low_stock_count` (≤10 units, >0), `out_of_stock_count`,
`expiring_soon_count` (within 30 days), `total_value_ron` (sum of price × stock
across the whole catalog).

## Next steps (when you're ready)

- Reorder threshold per product (custom low-stock point instead of the fixed 10-unit default)
- CSV import/export for bulk catalog management
- Auth for admin actions if this becomes multi-user
- Swap SQLite for Postgres/MySQL if you outgrow a single file