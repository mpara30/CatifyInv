import pytest


def test_list_empty(client):
    resp = client.get("/api/products")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_default_sort_is_name_asc(client, make_product):
    make_product(name="Zebra Snacks")
    make_product(name="Apple Treats")
    resp = client.get("/api/products")
    names = [p["name"] for p in resp.get_json()]
    assert names == ["Apple Treats", "Zebra Snacks"]


def test_filter_by_q_matches_name_brand_category_flavour(client, make_product):
    make_product(name="Salmon Pate", brand="Purrfect Bowl", category="wet", flavour="salmon")
    make_product(name="Chicken Kibble", brand="Wildcat", category="dry", flavour="chicken")

    resp = client.get("/api/products?q=salmon")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["name"] == "Salmon Pate"


def test_filter_by_brand_exact_match(client, make_product):
    make_product(name="A", brand="Purrfect Bowl")
    make_product(name="B", brand="Wildcat")

    resp = client.get("/api/products?brand=Wildcat")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["brand"] == "Wildcat"


def test_filter_by_category(client, make_product):
    make_product(name="A", category="dry")
    make_product(name="B", category="wet")

    resp = client.get("/api/products?category=wet")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["category"] == "wet"


def test_filter_by_flavour(client, make_product):
    make_product(name="A", flavour="chicken")
    make_product(name="B", flavour="salmon")

    resp = client.get("/api/products?flavour=salmon")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["flavour"] == "salmon"


def test_filter_in_stock_true(client, make_product):
    make_product(name="In stock", stock_qty=3)
    make_product(name="Out", stock_qty=0)

    resp = client.get("/api/products?in_stock=true")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["name"] == "In stock"


def test_filter_in_stock_false(client, make_product):
    make_product(name="In stock", stock_qty=3)
    make_product(name="Out", stock_qty=0)

    resp = client.get("/api/products?in_stock=false")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["name"] == "Out"


def test_filter_max_price(client, make_product):
    make_product(name="Cheap", price=500)
    make_product(name="Pricey", price=50000)

    resp = client.get("/api/products?max_price=1000")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["name"] == "Cheap"


def test_filter_expiring_before(client, make_product):
    make_product(name="Expires soon", expiration_date="2026-01-01")
    make_product(name="Expires later", expiration_date="2030-01-01")
    make_product(name="No date", expiration_date=None)

    resp = client.get("/api/products?expiring_before=2027-01-01")
    results = resp.get_json()
    names = {p["name"] for p in results}
    assert names == {"Expires soon"}


def test_filters_combine_with_and(client, make_product):
    make_product(name="Match", brand="Wildcat", category="dry", stock_qty=5)
    make_product(name="Wrong category", brand="Wildcat", category="wet", stock_qty=5)
    make_product(name="Wrong brand", brand="Other", category="dry", stock_qty=5)

    resp = client.get("/api/products?brand=Wildcat&category=dry")
    results = resp.get_json()
    assert len(results) == 1
    assert results[0]["name"] == "Match"


@pytest.mark.parametrize("sort_field", ["name", "brand", "price", "stock_qty", "expiration_date"])
def test_sort_by_each_allowed_field_ascending(client, make_product, sort_field):
    make_product(name="B", brand="B", price=200, stock_qty=2, expiration_date="2027-01-01")
    make_product(name="A", brand="A", price=100, stock_qty=1, expiration_date="2026-01-01")

    resp = client.get(f"/api/products?sort={sort_field}&order=asc")
    assert resp.status_code == 200
    values = [p[sort_field] for p in resp.get_json()]
    assert values == sorted(values)


def test_sort_order_desc(client, make_product):
    make_product(name="A", price=100)
    make_product(name="B", price=200)

    resp = client.get("/api/products?sort=price&order=desc")
    prices = [p["price"] for p in resp.get_json()]
    assert prices == [200, 100]


def test_sort_order_defaults_to_asc_for_unrecognized_value(client, make_product):
    make_product(name="A", price=100)
    make_product(name="B", price=200)

    resp = client.get("/api/products?sort=price&order=sideways")
    prices = [p["price"] for p in resp.get_json()]
    assert prices == [100, 200]


def test_invalid_sort_field_does_not_leak_into_query(client, make_product):
    """Regression test for CWE-89 (bandit B608): `sort` must never reach the
    SQL string unvalidated. main.py currently raises a bare ValueError for
    an invalid sort field instead of returning a clean 400 -- with
    TESTING=True, Flask propagates that exception rather than turning it
    into a 500 response, so the test client re-raises it here. This test
    pins that *current* behavior so a regression that instead lets injected
    SQL execute successfully (no exception, malformed/extra data returned)
    would be caught. If this is changed to a proper 400 JSON error, update
    this test to assert on the response instead of expecting a raise.
    """
    make_product(name="A")
    with pytest.raises(ValueError):
        client.get("/api/products?sort=id%3B%20DROP%20TABLE%20products%3B--&order=asc")

    # Whatever happened, the table must still exist and still have our row.
    follow_up = client.get("/api/products")
    assert follow_up.status_code == 200
    assert len(follow_up.get_json()) == 1
