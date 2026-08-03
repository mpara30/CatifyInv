"""
app.py
A REST API for the cat food database, built with Flask + sqlite3.

Endpoints:
    GET    /api/foods            list foods (supports filters, see below)
    GET    /api/foods/<id>       get one food
    POST   /api/foods            create a food
    PUT    /api/foods/<id>       update a food (partial updates allowed)
    DELETE /api/foods/<id>       delete a food
    GET    /api/health           basic health check

Filters for GET /api/foods (all optional, combine with &):
    q            free-text search across name/brand/ingredients/description
    brand        exact brand match
    food_type    dry | wet | raw | freeze-dried
    life_stage   kitten | adult | senior | all
    grain_free   true | false
    min_protein  minimum protein_percent
    max_price    maximum price
    sort         name | brand | price | protein_percent | calories_per_100g
    order        asc | desc (default asc)

Run with:
    python app.py
Then visit http://127.0.0.1:5000/api/foods
"""
from flask import Flask, request, jsonify
from database import get_connection, init_db

app = Flask(__name__)

REQUIRED_FIELDS = {"name", "brand", "food_type", "life_stage"}
ALLOWED_FIELDS = {
    "name", "brand", "food_type", "life_stage", "grain_free",
    "calories_per_100g", "protein_percent", "fat_percent",
    "fiber_percent", "moisture_percent", "price",
    "ingredients", "description",
}
VALID_FOOD_TYPES = {"dry", "wet", "raw", "freeze-dried"}
VALID_LIFE_STAGES = {"kitten", "adult", "senior", "all"}
SORTABLE_FIELDS = {"name", "brand", "price", "protein_percent", "calories_per_100g"}


def row_to_dict(row):
    d = dict(row)
    d["grain_free"] = bool(d["grain_free"])
    return d


def validate_payload(data, partial=False):
    """Return an error string if invalid, else None."""
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        return f"Unknown field(s): {', '.join(sorted(unknown))}"

    if not partial:
        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            return f"Missing required field(s): {', '.join(sorted(missing))}"

    if "food_type" in data and data["food_type"] not in VALID_FOOD_TYPES:
        return f"food_type must be one of {sorted(VALID_FOOD_TYPES)}"

    if "life_stage" in data and data["life_stage"] not in VALID_LIFE_STAGES:
        return f"life_stage must be one of {sorted(VALID_LIFE_STAGES)}"

    return None


@app.route("/api/foods", methods=["GET"])
def list_foods():
    args = request.args
    clauses = []
    params = []

    if args.get("q"):
        clauses.append(
            "(name LIKE ? OR brand LIKE ? OR ingredients LIKE ? OR description LIKE ?)"
        )
        like = f"%{args['q']}%"
        params.extend([like, like, like, like])

    if args.get("brand"):
        clauses.append("brand = ?")
        params.append(args["brand"])

    if args.get("food_type"):
        clauses.append("food_type = ?")
        params.append(args["food_type"])

    if args.get("life_stage"):
        clauses.append("life_stage = ?")
        params.append(args["life_stage"])

    if args.get("grain_free") is not None and args.get("grain_free") != "":
        clauses.append("grain_free = ?")
        params.append(1 if args["grain_free"].lower() == "true" else 0)

    if args.get("min_protein"):
        clauses.append("protein_percent >= ?")
        params.append(float(args["min_protein"]))

    if args.get("max_price"):
        clauses.append("price <= ?")
        params.append(float(args["max_price"]))

    sort = args.get("sort", "name")
    if sort not in SORTABLE_FIELDS:
        sort = "name"
    order = "DESC" if args.get("order", "asc").lower() == "desc" else "ASC"

    sql = "SELECT * FROM cat_foods"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {sort} {order}"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/foods/<int:food_id>", methods=["GET"])
def get_food(food_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM cat_foods WHERE id = ?", (food_id,)).fetchone()
        if row is None:
            return jsonify(error="Not found"), 404
        return jsonify(row_to_dict(row))
    finally:
        conn.close()


@app.route("/api/foods", methods=["POST"])
def create_food():
    data = request.get_json(silent=True) or {}
    err = validate_payload(data, partial=False)
    if err:
        return jsonify(error=err), 400

    data.setdefault("grain_free", False)
    fields = list(data.keys())
    placeholders = ", ".join(f":{f}" for f in fields)
    columns = ", ".join(fields)
    payload = dict(data)
    payload["grain_free"] = 1 if payload.get("grain_free") else 0

    conn = get_connection()
    try:
        cur = conn.execute(
            f"INSERT INTO cat_foods ({columns}) VALUES ({placeholders})", payload
        )
        conn.commit()
        new_row = conn.execute(
            "SELECT * FROM cat_foods WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return jsonify(row_to_dict(new_row)), 201
    finally:
        conn.close()


@app.route("/api/foods/<int:food_id>", methods=["PUT", "PATCH"])
def update_food(food_id):
    data = request.get_json(silent=True) or {}
    err = validate_payload(data, partial=True)
    if err:
        return jsonify(error=err), 400
    if not data:
        return jsonify(error="No fields provided to update"), 400

    if "grain_free" in data:
        data["grain_free"] = 1 if data["grain_free"] else 0

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM cat_foods WHERE id = ?", (food_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404

        set_clause = ", ".join(f"{f} = :{f}" for f in data.keys())
        data["id"] = food_id
        conn.execute(
            f"UPDATE cat_foods SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = :id",
            data,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cat_foods WHERE id = ?", (food_id,)).fetchone()
        return jsonify(row_to_dict(row))
    finally:
        conn.close()


@app.route("/api/foods/<int:food_id>", methods=["DELETE"])
def delete_food(food_id):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM cat_foods WHERE id = ?", (food_id,)
        ).fetchone()
        if existing is None:
            return jsonify(error="Not found"), 404
        conn.execute("DELETE FROM cat_foods WHERE id = ?", (food_id,))
        conn.commit()
        return "", 204
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)