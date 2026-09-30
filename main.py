"""
main.py
A REST API + static frontend server for the cat food product database.

Endpoints:
    GET    /api/health              health check
    GET    /api/stats               dashboard aggregates
    GET    /api/products            list products (supports filters, see below)
    GET    /api/products/<id>       get one product
    POST   /api/products            create a product
    PUT    /api/products/<id>       update a product (partial updates allowed)
    DELETE /api/products/<id>       delete a product
    POST   /api/products/<id>/adjust-stock   bump stock_qty by a delta
    GET    /api/products/<id>/history        stock change history for a product
    POST   /api/products/<id>/restock        add stock ({"boxes": 2} or {"units": 6}, optional "price", "expiration_date")
    GET    /api/stock-history                stock change history across all products
    GET    /api/stock-history/monthly        per-month totals: units fed, food cost, restock spend
    GET    /api/cats                list cats
    POST   /api/cats                create a cat ({"name": "..."})
    DELETE /api/cats/<id>           delete a cat (also un-tags it from any products)
    GET    /                        serves the frontend (frontend/index.html)

Filters for GET /api/products (all optional, combine with &):
    q                free-text search across name/brand/category/flavour
    brand            exact brand match
    category         dry | wet | raw | freeze-dried | treats (whatever you seed)
    flavour          exact flavour match
    in_stock         true -> stock_qty > 0 | false -> stock_qty = 0
    max_price        maximum price per unit, in bani (RON subunit)
    expiring_before  ISO date -> only products expiring on/before this date
    cat_id           only products tagged for this cat, PLUS any "all cats" products
                      (a product with no cat tags at all is implicitly for every cat)
    sort             name | brand | price | stock_qty | expiration_date
    order            asc | desc (default asc)

A product's cats are managed via the "cat_ids" field on create/update (a list
of cat ids, or omitted/empty for "all cats"). Every product response includes
"cat_ids" and "cats" (id + name) regardless of which endpoint returned it.

Run with:
    python main.py
Then visit http://127.0.0.1:5000/
"""
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, request, jsonify

from utils.database import get_connection, init_db
from models import Product
from utils.quality_checks import run_quality_checks


app = Flask(__name__, static_folder="frontend", static_url_path="")

REQUIRED_FIELDS = {"name", "brand"}
ALLOWED_FIELDS = {
    "name", "brand", "category", "flavour", "weight",
    "price", "units_per_box", "stock_qty", "expiration_date",
}
SORTABLE_FIELDS = {"name", "brand", "price", "stock_qty", "expiration_date"}

# Explicit column order matches Product.from_row's expectations.
COLUMNS =\
    "id, name, brand, category, flavour, weight, price, units_per_box, stock_qty, expiration_date"

LOW_STOCK_THRESHOLD = 2    # stock_qty at/below this (but > 0) counts as "running low"
EXPIRING_SOON_DAYS = 30    # expiration_date within this many days counts as "expiring soon"


def validate_payload(data, partial=False):
    """Return an error string if invalid, else None."""
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        return f"Unknown field(s): {', '.join(sorted(unknown))}"

    if not partial:
        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            return f"Missing required field(s): {', '.join(sorted(missing))}"

    if "price" in data and (not isinstance(data["price"], int) or data["price"] < 0):
        return "price (price per unit, in bani) must be a non-negative integer"

    if "units_per_box" in data and data["units_per_box"] is not None:
        if not isinstance(data["units_per_box"], int) or data["units_per_box"] < 1:
            return "units_per_box must be a positive integer, or omitted/null for single items"

    if "stock_qty" in data and (not isinstance(data["stock_qty"], int) or data["stock_qty"] < 0):
        return "stock_qty must be a non-negative integer"

    if "expiration_date" in data and data["expiration_date"]:
        try:
            datetime.strptime(data["expiration_date"], "%Y-%m-%d")
        except ValueError:
            return "expiration_date must be in YYYY-MM-DD format"

    return None


def log_stock_history(conn, product_id, product_name, product_brand,
                       previous_qty, new_qty, source, skip_if_unchanged=True,
                       cat_id=None, cat_name=None, unit_price=None):
    """Insert a stock_history row, snapshotting the product's name/brand (and
    the cat's name, if one was specified, and the unit price at that moment)
    so the row stays readable, and monthly costs stay accurate, even after
    the product or cat is deleted or its price changes.
    By default, no-op edits (previous_qty == new_qty) aren't logged."""
    if skip_if_unchanged and previous_qty == new_qty:
        return
    conn.execute(
        "INSERT INTO stock_history "
        "(product_id, product_name, product_brand, cat_id, cat_name, "
        "previous_qty, new_qty, delta, unit_price, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (product_id, product_name, product_brand, cat_id, cat_name,
         previous_qty, new_qty, new_qty - previous_qty, unit_price, source),
    )


def extract_cat_ids(data):
    """Pop and validate cat_ids from a product payload. Not a real products
    column -- it's a separate relation -- so it never reaches
    validate_payload or the ALLOWED_FIELDS check.

    Returns (cat_ids, error). cat_ids is None if the field wasn't present at
    all (leave associations untouched), or a list (possibly empty) to apply.
    """
    if "cat_ids" not in data:
        return None, None
    cat_ids = data.pop("cat_ids")
    if cat_ids is None:
        return [], None
    if not isinstance(cat_ids, list) or not all(isinstance(c, int) for c in cat_ids):
        return None, "cat_ids must be a list of integers, or omitted/null for all cats"
    return cat_ids, None


def set_product_cats(conn, product_id, cat_ids):
    """Replace a product's cat associations entirely. Empty list means
    'all cats'. Raises sqlite3.IntegrityError if a cat_id doesn't exist."""
    conn.execute("DELETE FROM product_cats WHERE product_id = ?", (product_id,))
    if cat_ids:
        conn.executemany(
            "INSERT INTO product_cats (product_id, cat_id) VALUES (?, ?)",
            [(product_id, cid) for cid in cat_ids],
        )


def attach_cat_info(conn, product_dicts):
    """Adds 'cat_ids' (list of ints) and 'cats' (list of {id, name}) to each
    product dict in place. No associations at all means 'all cats'."""
    if not product_dicts:
        return product_dicts
    ids = [p["id"] for p in product_dicts]
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT pc.product_id, c.id AS cat_id, c.name AS cat_name "  # nosec B608
        f"FROM product_cats pc JOIN cats c ON c.id = pc.cat_id "
        f"WHERE pc.product_id IN ({placeholders})",
        ids,
    ).fetchall()
    by_product = {}
    for r in rows:
        by_product.setdefault(r["product_id"], []).append(
            {"id": r["cat_id"], "name": r["cat_name"]}
        )
    for p in product_dicts:
        cats = by_product.get(p["id"], [])
        p["cats"] = cats
        p["cat_ids"] = [c["id"] for c in cats]
    return product_dicts


@app.route("/")
def index():
    """Function that returns the index page."""
    return app.send_static_file("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    """Function that returns the health status."""
    return jsonify(status="ok")


@app.route("/api/cats", methods=["GET"])
def list_cats():
    """Function that returns the list of cats."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name FROM cats ORDER BY name").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/cats", methods=["POST"])
def create_cat():
    """Function that creates a new cat."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400

    conn = get_connection()
    try:
        try:
            cur = conn.execute("INSERT INTO cats (name) VALUES (?)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify(error=f"A cat named '{name}' already exists"), 409
        row = conn.execute("SELECT id, name FROM cats WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    finally:
        conn.close()


@app.route("/api/cats/<int:cat_id>", methods=["DELETE"])
def delete_cat(cat_id):
    """Function that deletes a cat."""
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM cats WHERE id = ?", (cat_id,)).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404
        conn.execute("DELETE FROM cats WHERE id = ?", (cat_id,))  # cascades product_cats rows
        conn.commit()
        return "", 204
    finally:
        conn.close()


@app.route("/api/stats", methods=["GET"])
def stats():
    """Aggregate numbers for the dashboard header. Always computed across
    the full catalog, independent of whatever filters are applied to the
    product grid."""
    today = datetime.now().date().isoformat()
    soon = (datetime.now().date() + timedelta(days=EXPIRING_SOON_DAYS)).isoformat()

    conn = get_connection()
    try:
        total_skus = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

        low_stock_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE stock_qty > 0 AND stock_qty <= ?",
            (LOW_STOCK_THRESHOLD,),
        ).fetchone()[0]

        out_of_stock_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE stock_qty = 0"
        ).fetchone()[0]

        expiring_soon_count = conn.execute(
            "SELECT COUNT(*) FROM products "
            "WHERE expiration_date IS NOT NULL AND expiration_date BETWEEN ? AND ?",
            (today, soon),
        ).fetchone()[0]

        total_value_bani = conn.execute(
            "SELECT COALESCE(SUM(price * stock_qty), 0) FROM products"
        ).fetchone()[0]

        return jsonify(
            total_skus=total_skus,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            expiring_soon_count=expiring_soon_count,
            total_value_ron=round(total_value_bani / 100, 2),
            low_stock_threshold=LOW_STOCK_THRESHOLD,
            expiring_soon_days=EXPIRING_SOON_DAYS,
        )
    finally:
        conn.close()


@app.route("/api/products", methods=["GET"])
def list_products():
    """Function that returns the list of products."""
    args = request.args
    clauses = []
    params = []

    if args.get("q"):
        clauses.append("(name LIKE ? OR brand LIKE ? OR category LIKE ? OR flavour LIKE ?)")
        like = f"%{args['q']}%"
        params.extend([like, like, like, like])

    if args.get("brand"):
        clauses.append("brand = ?")
        params.append(args["brand"])

    if args.get("category"):
        clauses.append("category = ?")
        params.append(args["category"])

    if args.get("flavour"):
        clauses.append("flavour = ?")
        params.append(args["flavour"])

    if args.get("in_stock") is not None and args.get("in_stock") != "":
        if args["in_stock"].lower() == "true":
            clauses.append("stock_qty > 0")
        else:
            clauses.append("stock_qty = 0")

    if args.get("max_price"):
        clauses.append("price <= ?")
        params.append(int(args["max_price"]))

    if args.get("expiring_before"):
        clauses.append("expiration_date IS NOT NULL AND expiration_date <= ?")
        params.append(args["expiring_before"])

    if args.get("cat_id"):
        try:
            cat_id_val = int(args["cat_id"])
            clauses.append(
                "(EXISTS (SELECT 1 FROM product_cats pc "
                "WHERE pc.product_id = products.id AND pc.cat_id = ?) "
                "OR NOT EXISTS (SELECT 1 FROM product_cats pc WHERE pc.product_id = products.id))"
            )
            params.append(cat_id_val)
        except ValueError:
            pass

    sort = args.get("sort", "name")

    if sort not in SORTABLE_FIELDS:
        raise ValueError(f"Invalid sort field: {sort}")

    if sort not in SORTABLE_FIELDS:
        sort = "name"
    order = "DESC" if args.get("order", "asc").lower() == "desc" else "ASC"

    sql = f"SELECT {COLUMNS} FROM products" # nosec B608
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {sort} {order}"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        products = [Product.from_row(r).to_dict() for r in rows]
        attach_cat_info(conn, products)
        return jsonify(products)
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """Function that returns the product details."""
    conn = get_connection()
    try:
        row = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,) # nosec B608
        ).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404
        product = Product.from_row(row).to_dict()
        attach_cat_info(conn, [product])
        return jsonify(product)
    finally:
        conn.close()


@app.route("/api/products", methods=["POST"])
def create_product():
    """Function that creates a new product."""
    data = request.get_json(silent=True) or {}
    cat_ids, cat_err = extract_cat_ids(data)
    if cat_err:
        return jsonify(error=cat_err), 400

    err = validate_payload(data, partial=False)
    if err:
        return jsonify(error=err), 400

    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        return jsonify(error=f"Unknown fields: {sorted(unknown)}"), 400

    data.setdefault("category", "")
    data.setdefault("flavour", "")
    data.setdefault("weight", 0)
    data.setdefault("price", 0)
    data.setdefault("units_per_box", None)
    data.setdefault("stock_qty", 0)
    data.setdefault("expiration_date", None)

    fields = list(data.keys())
    placeholders = ", ".join(f":{f}" for f in fields)
    columns = ", ".join(fields)

    conn = get_connection()
    try:
        cur = conn.execute(
            f"INSERT INTO products ({columns}) VALUES ({placeholders})", data  # nosec B608
        )
        log_stock_history(
            conn, cur.lastrowid, data["name"], data["brand"],
            0, data["stock_qty"], "create", skip_if_unchanged=False,
            unit_price=data["price"],
        )
        if cat_ids:
            try:
                set_product_cats(conn, cur.lastrowid, cat_ids)
            except sqlite3.IntegrityError:
                conn.rollback()
                return jsonify(error="One or more cat_ids don't exist"), 400
        conn.commit()
        row = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (cur.lastrowid,) # nosec B608
        ).fetchone()
        product = Product.from_row(row).to_dict()
        attach_cat_info(conn, [product])
        return jsonify(product), 201
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["PUT", "PATCH"])
def update_product(product_id):
    """Function that updates a product."""
    data = request.get_json(silent=True) or {}
    cat_ids, cat_err = extract_cat_ids(data)
    if cat_err:
        return jsonify(error=cat_err), 400

    err = validate_payload(data, partial=True)
    if err:
        return jsonify(error=err), 400
    if not data and cat_ids is None:
        return jsonify(error="No fields provided to update"), 400

    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        return jsonify(error=f"Unknown fields: {sorted(unknown)}"), 400

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, name, brand, price, stock_qty FROM products WHERE id = ?",  # nosec B608
            (product_id,),
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        if data:
            set_clause = ", ".join(f"{f} = :{f}" for f in data.keys())
            data["id"] = product_id
            conn.execute(
                f"UPDATE products SET {set_clause}, updated_at = CURRENT_TIMESTAMP "  # nosec B608
                f"WHERE id = :id",
                data,
            )

        if "stock_qty" in data:
            # Use the post-edit name/brand if those were changed in this same request.
            snap_name = data.get("name", existing["name"])
            snap_brand = data.get("brand", existing["brand"])
            log_stock_history(
                conn, product_id, snap_name, snap_brand,
                existing["stock_qty"], data["stock_qty"], "edit",
                unit_price=data.get("price", existing["price"]),
            )

        if cat_ids is not None:
            try:
                set_product_cats(conn, product_id, cat_ids)
            except sqlite3.IntegrityError:
                conn.rollback()
                return jsonify(error="One or more cat_ids don't exist"), 400

        conn.commit()
        row = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)  # nosec B608
        ).fetchone()
        product = Product.from_row(row).to_dict()
        attach_cat_info(conn, [product])
        return jsonify(product)
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>/adjust-stock", methods=["POST"])
def adjust_stock(product_id):
    """Bump stock_qty up or down by a delta. Body: {"delta": 1} or {"delta": -1}.
    Optionally include {"cat_id": N} to record which cat this feeding was
    for -- when present, the history entry is logged as a 'feed' event
    instead of a generic 'adjust'. Clamps at 0 — never goes negative."""
    data = request.get_json(silent=True) or {}
    delta = data.get("delta")
    if not isinstance(delta, int):
        return jsonify(error="delta must be an integer"), 400

    cat_id = data.get("cat_id")
    if cat_id is not None and not isinstance(cat_id, int):
        return jsonify(error="cat_id must be an integer, or omitted"), 400

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name, brand, price, stock_qty FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404

        cat_name = None
        if cat_id is not None:
            cat_row = conn.execute("SELECT name FROM cats WHERE id = ?", (cat_id,)).fetchone()
            if cat_row is None:
                return jsonify(error="cat_id doesn't exist"), 400
            cat_name = cat_row["name"]

        new_qty = max(0, row["stock_qty"] + delta)
        conn.execute(
            "UPDATE products SET stock_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_qty, product_id),
        )
        log_stock_history(
            conn, product_id, row["name"], row["brand"],
            row["stock_qty"], new_qty, "feed" if cat_id is not None else "adjust",
            cat_id=cat_id, cat_name=cat_name, unit_price=row["price"],
        )
        conn.commit()
        updated = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)  # nosec B608
        ).fetchone()
        return jsonify(Product.from_row(updated).to_dict())
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>/restock", methods=["POST"])
def restock(product_id):
    """Add stock you just bought. Body: {"boxes": 2} (needs units_per_box on
    the product) or {"units": 6}. Optional: "price" (bani per unit, updates
    the product's price) and "expiration_date" (YYYY-MM-DD). Logged as a
    'restock' event with the price paid, so monthly spend is accurate."""
    data = request.get_json(silent=True) or {}
    boxes, units = data.get("boxes"), data.get("units")
    price, expiration = data.get("price"), data.get("expiration_date")

    if (boxes is None) == (units is None):
        return jsonify(error="Provide exactly one of boxes or units"), 400
    for value in (boxes, units, price):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            return jsonify(error="boxes, units and price must be integers"), 400
    if (boxes if boxes is not None else units) < 1:
        return jsonify(error="Quantity must be at least 1"), 400
    if price is not None and price < 0:
        return jsonify(error="price must be >= 0"), 400
    if expiration is not None:
        try:
            datetime.strptime(expiration, "%Y-%m-%d")
        except (TypeError, ValueError):
            return jsonify(error="expiration_date must be YYYY-MM-DD"), 400

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name, brand, price, units_per_box, stock_qty FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404

        if boxes is not None:
            if not row["units_per_box"]:
                return jsonify(error="Product has no units_per_box; send units instead"), 400
            units = boxes * row["units_per_box"]

        new_price = row["price"] if price is None else price
        new_qty = row["stock_qty"] + units
        conn.execute(
            "UPDATE products SET stock_qty = ?, price = ?, "
            "expiration_date = COALESCE(?, expiration_date), "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_qty, new_price, expiration, product_id),
        )
        log_stock_history(
            conn, product_id, row["name"], row["brand"],
            row["stock_qty"], new_qty, "restock", unit_price=new_price,
        )
        conn.commit()
        updated = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)  # nosec B608
        ).fetchone()
        return jsonify(Product.from_row(updated).to_dict())
    finally:
        conn.close()


@app.route("/api/stock-history/monthly", methods=["GET"])
def monthly_history():
    """Per-month totals, most recent month first.

    For each month: number of feedings and units fed, what that food cost
    (units x the price at the time), and restock spend (restocks plus the
    starting stock of newly created products). Money is in bani, with _ron
    twins. Rows logged before unit_price existed count as 0 cost.

    Optional filter: cat_id (only feedings for this cat; spend is then 0).
    """
    cat_id = request.args.get("cat_id", type=int)
    sql = (
        "SELECT strftime('%Y-%m', created_at) AS month, "
        "SUM(CASE WHEN source = 'feed' THEN 1 ELSE 0 END) AS feedings, "
        "SUM(CASE WHEN source = 'feed' THEN -delta ELSE 0 END) AS units_fed, "
        "SUM(CASE WHEN source = 'feed' THEN -delta * COALESCE(unit_price, 0) ELSE 0 END) AS food_cost, "
        "SUM(CASE WHEN source IN ('restock', 'create') AND delta > 0 "
        "THEN delta * COALESCE(unit_price, 0) ELSE 0 END) AS spend "
        "FROM stock_history"
    )
    params = []
    if cat_id is not None:
        sql += " WHERE source = 'feed' AND cat_id = ?"
        params.append(cat_id)
    sql += " GROUP BY month ORDER BY month DESC"

    conn = get_connection()
    try:
        out = []
        for r in conn.execute(sql, params).fetchall():
            item = dict(r)
            item["food_cost_ron"] = round(item["food_cost"] / 100, 2)
            item["spend_ron"] = round(item["spend"] / 100, 2)
            out.append(item)
        return jsonify(out)
    finally:
        conn.close()


@app.route("/history")
def history_page():
    """Function that displays the history page."""
    return app.send_static_file("history.html")


@app.route("/api/stock-history", methods=["GET"])
def all_stock_history():
    """Stock change history across all products (including deleted ones),
    most recent first.

    Optional filters:
        q          search by product name or brand
        source     'create' | 'edit' | 'adjust' | 'delete' | 'feed' | 'restock'
        cat_id     only 'feed' events logged for this cat
        limit      max rows to return (default 200)
    """
    args = request.args
    clauses = []
    params = []

    if args.get("q"):
        clauses.append("(product_name LIKE ? OR product_brand LIKE ?)")
        like = f"%{args['q']}%"
        params.extend([like, like])

    if args.get("source") in ("create", "edit", "adjust", "delete", "feed", "restock"):
        clauses.append("source = ?")
        params.append(args["source"])

    if args.get("cat_id"):
        try:
            clauses.append("cat_id = ?")
            params.append(int(args["cat_id"]))
        except ValueError:
            pass

    limit = args.get("limit", "200")
    try:
        limit = max(1, min(1000, int(limit)))
    except ValueError:
        limit = 200

    sql = (
        "SELECT id, product_id, product_name, product_brand, cat_id, cat_name, "
        "previous_qty, new_qty, delta, unit_price, source, created_at FROM stock_history"
    )
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>/history", methods=["GET"])
def product_history(product_id):
    """Function that displays the history of a product."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        rows = conn.execute(
            "SELECT id, cat_id, cat_name, previous_qty, new_qty, delta, source, created_at "
            "FROM stock_history WHERE product_id = ? ORDER BY created_at DESC, id DESC",
            (product_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    """Function that deletes a product."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, name, brand, price, stock_qty FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        log_stock_history(
            conn, product_id, existing["name"], existing["brand"],
            existing["stock_qty"], 0, "delete", skip_if_unchanged=False,
            unit_price=existing["price"],
        )
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return "", 204
    finally:
        conn.close()

if __name__ == "__main__":
    run_quality_checks()

    init_db()
    app.run(port=5000)
