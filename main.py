"""
main.py
A REST API + static frontend server for the cat food product database.

Endpoints:
    GET    /api/health              health check
    GET    /api/products            list products (supports filters, see below)
    GET    /api/products/<id>       get one product
    POST   /api/products            create a product
    PUT    /api/products/<id>       update a product (partial updates allowed)
    DELETE /api/products/<id>       delete a product
    GET    /                        serves the frontend (frontend/index.html)

Filters for GET /api/products (all optional, combine with &):
    q                free-text search across name/brand/category/flavour
    brand            exact brand match
    category         dry | wet | raw | freeze-dried | treats (whatever you seed)
    flavour          exact flavour match
    in_stock         true -> stock_qty > 0 | false -> stock_qty = 0
    max_price        maximum price in cents
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
    "price", "stock_qty", "expiration_date",
}
SORTABLE_FIELDS = {"name", "brand", "price", "stock_qty", "expiration_date"}

# Explicit column order matches Product.from_row's expectations.
COLUMNS = "id, name, brand, category, flavour, weight, price, stock_qty, expiration_date"

LOW_STOCK_THRESHOLD = 10   # stock_qty at/below this (but > 0) counts as "low stock"
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
        return "price must be a non-negative integer (cents)"

    if "stock_qty" in data and (not isinstance(data["stock_qty"], int) or data["stock_qty"] < 0):
        return "stock_qty must be a non-negative integer"

    if "expiration_date" in data and data["expiration_date"]:
        try:
            datetime.strptime(data["expiration_date"], "%Y-%m-%d")
        except ValueError:
            return "expiration_date must be in YYYY-MM-DD format"

    return None


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

        total_value_cents = conn.execute(
            "SELECT COALESCE(SUM(price * stock_qty), 0) FROM products"
        ).fetchone()[0]

        return jsonify(
            total_skus=total_skus,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            expiring_soon_count=expiring_soon_count,
            total_value_usd=round(total_value_cents / 100, 2),
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
            "SELECT id FROM products WHERE id = ?", (product_id,)
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
            "SELECT stock_qty FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404

        new_qty = max(0, row["stock_qty"] + delta)
        conn.execute(
            "UPDATE products SET stock_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_qty, product_id),
        )
        conn.commit()
        updated = conn.execute(
            f"SELECT {COLUMNS} FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return jsonify(Product.from_row(updated).to_dict())
    finally:
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return "", 204
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)