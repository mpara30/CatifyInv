# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
def test_adjust_stock_positive_delta(client, make_product):
    pid = make_product(stock_qty=5)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 3})
    assert resp.status_code == 200
    assert resp.get_json()["stock_qty"] == 8


def test_adjust_stock_negative_delta(client, make_product):
    pid = make_product(stock_qty=5)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -2})
    assert resp.status_code == 200
    assert resp.get_json()["stock_qty"] == 3


def test_adjust_stock_clamps_at_zero(client, make_product):
    pid = make_product(stock_qty=2)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -10})
    assert resp.status_code == 200
    assert resp.get_json()["stock_qty"] == 0


def test_adjust_stock_non_integer_delta_400(client, make_product):
    pid = make_product(stock_qty=5)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": "two"})
    assert resp.status_code == 400


def test_adjust_stock_missing_delta_400(client, make_product):
    pid = make_product(stock_qty=5)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={})
    assert resp.status_code == 400


def test_adjust_stock_not_found_404(client):
    resp = client.post("/api/products/99999/adjust-stock", json={"delta": 1})
    assert resp.status_code == 404


def test_adjust_stock_logs_history(client, make_product):
    pid = make_product(stock_qty=5)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 2})
    history = client.get(f"/api/products/{pid}/history").get_json()
    assert len(history) == 1
    assert history[0]["source"] == "adjust"
    assert history[0]["previous_qty"] == 5
    assert history[0]["new_qty"] == 7


def test_adjust_stock_zero_delta_does_not_log(client, make_product):
    pid = make_product(stock_qty=5)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 0})
    history = client.get(f"/api/products/{pid}/history").get_json()
    assert history == []


def test_adjust_stock_below_zero_clamped_delta_still_logs_clamped_value(client, make_product):
    pid = make_product(stock_qty=2)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -10})
    history = client.get(f"/api/products/{pid}/history").get_json()
    assert history[0]["previous_qty"] == 2
    assert history[0]["new_qty"] == 0
    assert history[0]["delta"] == -2  # actual change applied, not the raw -10 requested
