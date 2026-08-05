def test_delete_success_returns_204(client, make_product):
    pid = make_product()
    resp = client.delete(f"/api/products/{pid}")
    assert resp.status_code == 204
    assert resp.data == b""


def test_delete_removes_product(client, make_product):
    pid = make_product()
    client.delete(f"/api/products/{pid}")
    resp = client.get(f"/api/products/{pid}")
    assert resp.status_code == 404


def test_delete_not_found_404(client):
    resp = client.delete("/api/products/99999")
    assert resp.status_code == 404


def test_delete_logs_history_with_zero_new_qty(client, make_product, db_conn):
    pid = make_product(name="Doomed", brand="Acme", stock_qty=7)
    client.delete(f"/api/products/{pid}")

    rows = db_conn.execute(
        "SELECT * FROM stock_history WHERE product_id = ? ORDER BY id DESC",
        (pid,),
    ).fetchall()
    assert rows[0]["source"] == "delete"
    assert rows[0]["previous_qty"] == 7
    assert rows[0]["new_qty"] == 0
    assert rows[0]["product_name"] == "Doomed"
    assert rows[0]["product_brand"] == "Acme"


def test_delete_history_survives_product_deletion(client, make_product):
    """stock_history.product_id is deliberately not a foreign key, so
    history rows must remain queryable after the product itself is gone."""
    pid = make_product(name="Doomed", brand="Acme", stock_qty=1)
    client.delete(f"/api/products/{pid}")

    resp = client.get("/api/stock-history?q=Doomed")
    assert resp.status_code == 200
    entries = resp.get_json()
    assert any(e["source"] == "delete" and e["product_name"] == "Doomed" for e in entries)


def test_delete_zero_stock_product_still_logs(client, make_product):
    """delete uses skip_if_unchanged=False, so a 0 -> 0 delete is logged too."""
    pid = make_product(stock_qty=0)
    client.delete(f"/api/products/{pid}")
    resp = client.get("/api/stock-history")
    entries = resp.get_json()
    assert any(e["product_id"] == pid and e["source"] == "delete" for e in entries)
