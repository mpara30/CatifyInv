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
    GET    /api/stock-history                stock change history across all products
    GET    /                        serves the frontend (frontend/index.html)

Filters for GET /api/products (all optional, combine with &):
    q                free-text search across name/brand/category/flavour
    brand            exact brand match
    category         dry | wet | raw | freeze-dried | treats (whatever you seed)
    flavour          exact flavour match
    in_stock         true -> stock_qty > 0 | false -> stock_qty = 0
    max_price        maximum price per unit, in bani (RON subunit)
    expiring_before  ISO date -> only products expiring on/before this date
    sort             name | brand | price | stock_qty | expiration_date
    order            asc | desc (default asc)

Run with:
    python main.py
Then visit http://127.0.0.1:5000/
"""
from datetime import datetime, timedelta

from flask import Flask, request, jsonify

from database import get_connection, init_db
from models import Product

app = Flask(__name__, static_folder="frontend", static_url_path="")

REQUIRED_FIELDS = {"name", "brand"}
ALLOWED_FIELDS = {
    "name", "brand", "category", "flavour", "weight",
    "price", "units_per_box", "stock_qty", "expiration_date",
}
SORTABLE_FIELDS = {"name", "brand", "price", "stock_qty", "expiration_date"}

# Explicit column order matches Product.from_row's expectations.
COLUMNS = "id, name, brand, category, flavour, weight, price, units_per_box, stock_qty, expiration_date"

LOW_STOCK_THRESHOLD = 2    # stock_qty at/below this (but > 0) counts as "running low" — tuned for home quantities, not shop stock
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
                       previous_qty, new_qty, source, skip_if_unchanged=True):
    """Insert a stock_history row, snapshotting the product's name/brand so
    the row stays readable even after the product itself is deleted.
    By default, no-op edits (previous_qty == new_qty) aren't logged."""
    if skip_if_unchanged and previous_qty == new_qty:
        return
    conn.execute(
        "INSERT INTO stock_history "
        "(product_id, product_name, product_brand, previous_qty, new_qty, delta, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (product_id, product_name, product_brand, previous_qty, new_qty,
         new_qty - previous_qty, source),
    )


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(status="ok")


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

    sort = args.get("sort", "name")
    if sort not in SORTABLE_FIELDS:
        sort = "name"
    order = "DESC" if args.get("order", "asc").lower() == "desc" else "ASC"

    sql = f"SELECT {COLUMNS} FROM products"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {sort} {order}"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        products = [Product.from_row(r).to_dict() for r in rows]
        return jsonify(products)
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_connection()
    try:
        row = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404
        return jsonify(Product.from_row(row).to_dict())
    finally:
        conn.close()


@app.route("/api/products", methods=["POST"])
def create_product():
    data = request.get_json(silent=True) or {}
    err = validate_payload(data, partial=False)
    if err:
        return jsonify(error=err), 400

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
            f"INSERT INTO products ({columns}) VALUES ({placeholders})", data
        )
        log_stock_history(
            conn, cur.lastrowid, data["name"], data["brand"],
            0, data["stock_qty"], "create", skip_if_unchanged=False,
        )
        conn.commit()
        row = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return jsonify(Product.from_row(row).to_dict()), 201
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["PUT", "PATCH"])
def update_product(product_id):
    data = request.get_json(silent=True) or {}
    err = validate_payload(data, partial=True)
    if err:
        return jsonify(error=err), 400
    if not data:
        return jsonify(error="No fields provided to update"), 400

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, name, brand, stock_qty FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        set_clause = ", ".join(f"{f} = :{f}" for f in data.keys())
        data["id"] = product_id
        conn.execute(
            f"UPDATE products SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
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
            )

        conn.commit()
        row = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return jsonify(Product.from_row(row).to_dict())
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>/adjust-stock", methods=["POST"])
def adjust_stock(product_id):
    """Bump stock_qty up or down by a delta. Body: {"delta": 1} or {"delta": -1}.
    Clamps at 0 — never goes negative."""
    data = request.get_json(silent=True) or {}
    delta = data.get("delta")
    if not isinstance(delta, int):
        return jsonify(error="delta must be an integer"), 400

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name, brand, stock_qty FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404

        new_qty = max(0, row["stock_qty"] + delta)
        conn.execute(
            "UPDATE products SET stock_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_qty, product_id),
        )
        log_stock_history(
            conn, product_id, row["name"], row["brand"],
            row["stock_qty"], new_qty, "adjust",
        )
        conn.commit()
        updated = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return jsonify(Product.from_row(updated).to_dict())
    finally:
        conn.close()


@app.route("/history")
def history_page():
    return app.send_static_file("history.html")


@app.route("/api/stock-history", methods=["GET"])
def all_stock_history():
    """Stock change history across all products (including deleted ones),
    most recent first.

    Optional filters:
        q          search by product name or brand
        source     'create' | 'edit' | 'adjust' | 'delete'
        limit      max rows to return (default 200)
    """
    args = request.args
    clauses = []
    params = []

    if args.get("q"):
        clauses.append("(product_name LIKE ? OR product_brand LIKE ?)")
        like = f"%{args['q']}%"
        params.extend([like, like])

    if args.get("source") in ("create", "edit", "adjust", "delete"):
        clauses.append("source = ?")
        params.append(args["source"])

    limit = args.get("limit", "200")
    try:
        limit = max(1, min(1000, int(limit)))
    except ValueError:
        limit = 200

    sql = (
        "SELECT id, product_id, product_name, product_brand, "
        "previous_qty, new_qty, delta, source, created_at FROM stock_history"
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
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        rows = conn.execute(
            "SELECT id, previous_qty, new_qty, delta, source, created_at "
            "FROM stock_history WHERE product_id = ? ORDER BY created_at DESC, id DESC",
            (product_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, name, brand, stock_qty FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        log_stock_history(
            conn, product_id, existing["name"], existing["brand"],
            existing["stock_qty"], 0, "delete", skip_if_unchanged=False,
        )
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return "", 204
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
