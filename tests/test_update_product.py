# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
def test_update_partial_field_success(client, make_product):
    pid = make_product(name="Old Name", stock_qty=5)
    resp = client.put(f"/api/products/{pid}", json={"name": "New Name"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "New Name"
    assert body["stock_qty"] == 5  # untouched fields preserved


def test_patch_method_also_works(client, make_product):
    pid = make_product(name="Old Name")
    resp = client.patch(f"/api/products/{pid}", json={"name": "Patched"})
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Patched"


def test_update_multiple_fields(client, make_product):
    pid = make_product(name="A", brand="B", price=100)
    resp = client.put(f"/api/products/{pid}", json={"name": "A2", "price": 200})
    body = resp.get_json()
    assert body["name"] == "A2"
    assert body["price"] == 200
    assert body["brand"] == "B"


def test_update_not_found_404(client):
    resp = client.put("/api/products/99999", json={"name": "Ghost"})
    assert resp.status_code == 404


def test_update_empty_body_400(client, make_product):
    pid = make_product()
    resp = client.put(f"/api/products/{pid}", json={})
    assert resp.status_code == 400
    assert "No fields" in resp.get_json()["error"]


def test_update_unknown_field_400(client, make_product):
    pid = make_product()
    resp = client.put(f"/api/products/{pid}", json={"not_a_column": "x"})
    assert resp.status_code == 400


def test_update_cannot_set_id_directly(client, make_product):
    pid = make_product()
    resp = client.put(f"/api/products/{pid}", json={"id": 12345})
    assert resp.status_code == 400
    assert "id" in resp.get_json()["error"]


def test_update_invalid_price_400(client, make_product):
    pid = make_product()
    resp = client.put(f"/api/products/{pid}", json={"price": -5})
    assert resp.status_code == 400


def test_update_invalid_expiration_date_400(client, make_product):
    pid = make_product()
    resp = client.put(f"/api/products/{pid}", json={"expiration_date": "not-a-date"})
    assert resp.status_code == 400


def test_update_stock_qty_logs_edit_history(client, make_product):
    pid = make_product(stock_qty=5)
    client.put(f"/api/products/{pid}", json={"stock_qty": 8})
    history = client.get(f"/api/products/{pid}/history").get_json()
    assert len(history) == 1
    assert history[0]["source"] == "edit"
    assert history[0]["previous_qty"] == 5
    assert history[0]["new_qty"] == 8


def test_update_stock_qty_to_same_value_does_not_log(client, make_product):
    pid = make_product(stock_qty=5)
    client.put(f"/api/products/{pid}", json={"stock_qty": 5})
    history = client.get(f"/api/products/{pid}/history").get_json()
    assert history == []


def test_update_without_stock_qty_does_not_log_history(client, make_product):
    pid = make_product(stock_qty=5)
    client.put(f"/api/products/{pid}", json={"name": "Renamed"})
    history = client.get(f"/api/products/{pid}/history").get_json()
    assert history == []


def test_update_history_uses_post_edit_name_and_brand(client, make_product, db_conn):
    pid = make_product(name="Old", brand="OldBrand", stock_qty=5)
    client.put(
        f"/api/products/{pid}",
        json={"name": "New", "brand": "NewBrand", "stock_qty": 9},
    )
    rows = db_conn.execute(
        "SELECT product_name, product_brand FROM stock_history WHERE product_id = ?",
        (pid,),
    ).fetchall()
    assert rows[0]["product_name"] == "New"
    assert rows[0]["product_brand"] == "NewBrand"


def test_update_malicious_field_name_rejected(client, make_product):
    """Regression test: a crafted key can't ride into the UPDATE SET
    clause -- must be rejected with 400 before the query is ever built."""
    pid = make_product()
    resp = client.put(
        f"/api/products/{pid}",
        json={"name = name, stock_qty": 999999},
    )
    assert resp.status_code == 400

    unchanged = client.get(f"/api/products/{pid}").get_json()
    assert unchanged["stock_qty"] != 999999
