def test_product_history_empty_for_untouched_product(client, make_product):
    pid = make_product()
    resp = client.get(f"/api/products/{pid}/history")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_product_history_not_found_404(client):
    resp = client.get("/api/products/99999/history")
    assert resp.status_code == 404


def test_product_history_most_recent_first(client, make_product):
    pid = make_product(stock_qty=1)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 1})  # -> 2
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 1})  # -> 3

    history = client.get(f"/api/products/{pid}/history").get_json()
    assert [h["new_qty"] for h in history] == [3, 2]


def test_all_stock_history_across_products(client, make_product):
    p1 = make_product(name="P1", stock_qty=1)
    p2 = make_product(name="P2", stock_qty=1)
    client.post(f"/api/products/{p1}/adjust-stock", json={"delta": 1})
    client.post(f"/api/products/{p2}/adjust-stock", json={"delta": 1})

    resp = client.get("/api/stock-history")
    assert resp.status_code == 200
    product_ids = {e["product_id"] for e in resp.get_json()}
    assert {p1, p2} <= product_ids


def test_stock_history_filter_by_q(client, make_product):
    p1 = make_product(name="Salmon Feast", stock_qty=1)
    p2 = make_product(name="Chicken Bites", stock_qty=1)
    client.post(f"/api/products/{p1}/adjust-stock", json={"delta": 1})
    client.post(f"/api/products/{p2}/adjust-stock", json={"delta": 1})

    resp = client.get("/api/stock-history?q=Salmon")
    entries = resp.get_json()
    assert all("Salmon" in e["product_name"] for e in entries)
    assert len(entries) >= 1


def test_stock_history_filter_by_source(client, make_product):
    pid = make_product(stock_qty=1)
    client.put(f"/api/products/{pid}", json={"stock_qty": 5})  # edit
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 1})  # adjust

    resp = client.get("/api/stock-history?source=adjust")
    entries = resp.get_json()
    assert entries
    assert all(e["source"] == "adjust" for e in entries)


def test_stock_history_invalid_source_is_ignored_not_errored(client, make_product):
    pid = make_product(stock_qty=1)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 1})

    resp = client.get("/api/stock-history?source=not-a-real-source")
    assert resp.status_code == 200
    # invalid source value is silently dropped as a filter (per the `in (...)`
    # allowlist check), so results are unfiltered rather than empty/erroring
    assert len(resp.get_json()) >= 1


def test_stock_history_limit_is_respected(client, make_product):
    pid = make_product(stock_qty=0)
    for i in range(5):
        client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 1})

    resp = client.get("/api/stock-history?limit=2")
    assert len(resp.get_json()) == 2


def test_stock_history_limit_invalid_falls_back_to_default(client, make_product):
    pid = make_product(stock_qty=0)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 1})

    resp = client.get("/api/stock-history?limit=not-a-number")
    assert resp.status_code == 200  # falls back to default 200, doesn't error


def test_stock_history_limit_clamped_to_max_1000(client, make_product):
    resp = client.get("/api/stock-history?limit=999999")
    assert resp.status_code == 200  # clamped server-side, no error
