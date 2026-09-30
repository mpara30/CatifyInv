# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
def test_restock_units_updates_stock_price_and_logs(client, make_product):
    pid = make_product(stock_qty=2, price=1000)
    resp = client.post(f"/api/products/{pid}/restock", json={"units": 6, "price": 1200})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["stock_qty"] == 8
    assert body["price"] == 1200
    hist = client.get("/api/stock-history?source=restock").get_json()
    assert hist[0]["delta"] == 6
    assert hist[0]["unit_price"] == 1200


def test_restock_boxes_uses_units_per_box(client, make_product):
    pid = make_product(stock_qty=0, units_per_box=12)
    resp = client.post(f"/api/products/{pid}/restock", json={"boxes": 2, "expiration_date": "2027-01-31"})
    assert resp.status_code == 200
    assert resp.get_json()["stock_qty"] == 24
    assert resp.get_json()["expiration_date"] == "2027-01-31"


def test_restock_boxes_without_units_per_box_400(client, make_product):
    pid = make_product(units_per_box=None)
    assert client.post(f"/api/products/{pid}/restock", json={"boxes": 1}).status_code == 400


def test_restock_validation_errors(client, make_product):
    pid = make_product()
    url = f"/api/products/{pid}/restock"
    assert client.post(url, json={}).status_code == 400
    assert client.post(url, json={"units": 1, "boxes": 1}).status_code == 400
    assert client.post(url, json={"units": 0}).status_code == 400
    assert client.post(url, json={"units": "two"}).status_code == 400
    assert client.post(url, json={"units": 1, "price": -5}).status_code == 400
    assert client.post(url, json={"units": 1, "expiration_date": "soon"}).status_code == 400
    assert client.post("/api/products/9999/restock", json={"units": 1}).status_code == 404


def test_monthly_history_totals(client, make_product):
    pid = make_product(stock_qty=10, price=500)
    cat = client.post("/api/cats", json={"name": "Miso"}).get_json()["id"]
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -2, "cat_id": cat})
    client.post(f"/api/products/{pid}/restock", json={"units": 4, "price": 600})
    rows = client.get("/api/stock-history/monthly").get_json()
    assert len(rows) == 1
    month = rows[0]
    assert month["feedings"] == 1
    assert month["units_fed"] == 2
    assert month["food_cost"] == 1000
    assert month["spend"] == 4 * 600  # make_product inserts directly, so no "create" row
    assert month["food_cost_ron"] == 10.0


def test_monthly_history_cat_filter(client, make_product):
    pid = make_product(stock_qty=10, price=500)
    cat = client.post("/api/cats", json={"name": "Miso"}).get_json()["id"]
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": cat})
    rows = client.get(f"/api/stock-history/monthly?cat_id={cat}").get_json()
    assert rows[0]["units_fed"] == 1
    assert rows[0]["spend"] == 0


def test_migration_adds_unit_price_and_restock_source(tmp_path, monkeypatch):
    import sqlite3
    from utils import database
    db_path = tmp_path / "old.db"
    old = sqlite3.connect(db_path)
    old.executescript("""
        CREATE TABLE stock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
            product_name TEXT NOT NULL, product_brand TEXT NOT NULL,
            cat_id INTEGER, cat_name TEXT, previous_qty INTEGER NOT NULL,
            new_qty INTEGER NOT NULL, delta INTEGER NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('create','edit','adjust','delete','feed')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO stock_history (product_id, product_name, product_brand, cat_id, cat_name,
            previous_qty, new_qty, delta, source) VALUES (1,'Old','B',7,'Miso',5,4,-1,'feed');
    """)
    old.commit()
    old.close()
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
    conn = database.get_connection()
    row = conn.execute("SELECT cat_name, unit_price FROM stock_history").fetchone()
    assert row["cat_name"] == "Miso" and row["unit_price"] is None
    conn.execute("INSERT INTO stock_history (product_name, product_brand, previous_qty, new_qty, delta, source) "
                 "VALUES ('x','y',0,1,1,'restock')")
    conn.close()
