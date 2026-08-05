# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
from datetime import date, timedelta


def test_stats_empty_db(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_skus"] == 0
    assert body["low_stock_count"] == 0
    assert body["out_of_stock_count"] == 0
    assert body["expiring_soon_count"] == 0
    assert body["total_value_ron"] == 0


def test_stats_counts_and_value(client, make_product):
    # in stock, comfortably above the low-stock threshold (2)
    make_product(name="Plenty", stock_qty=10, price=500)
    # low stock: > 0 but <= LOW_STOCK_THRESHOLD (2)
    make_product(name="Almost gone", stock_qty=2, price=1000)
    # out of stock
    make_product(name="Empty", stock_qty=0, price=2000)

    resp = client.get("/api/stats")
    body = resp.get_json()
    assert body["total_skus"] == 3
    assert body["low_stock_count"] == 1
    assert body["out_of_stock_count"] == 1
    # (10*500 + 2*1000 + 0*2000) / 100 = 70.00
    assert body["total_value_ron"] == 70.0


def test_stats_expiring_soon_window(client, make_product):
    today = date.today()
    within_window = (today + timedelta(days=5)).isoformat()
    outside_window = (today + timedelta(days=90)).isoformat()
    already_past = (today - timedelta(days=5)).isoformat()

    make_product(name="Soon", expiration_date=within_window)
    make_product(name="Later", expiration_date=outside_window)
    make_product(name="Past", expiration_date=already_past)
    make_product(name="NoDate", expiration_date=None)

    resp = client.get("/api/stats")
    body = resp.get_json()
    assert body["expiring_soon_count"] == 1
