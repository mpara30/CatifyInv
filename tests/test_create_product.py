# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
import pytest


def test_create_success_returns_201_and_full_record(client, valid_payload):
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] is not None
    assert body["name"] == valid_payload["name"]
    assert body["brand"] == valid_payload["brand"]
    assert body["stock_qty"] == valid_payload["stock_qty"]


def test_create_persists_and_is_retrievable(client, valid_payload):
    created = client.post("/api/products", json=valid_payload).get_json()
    fetched = client.get(f"/api/products/{created['id']}").get_json()
    assert fetched == created


def test_create_applies_defaults_when_optional_fields_omitted(client):
    resp = client.post("/api/products", json={"name": "Bare Minimum", "brand": "Acme"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["category"] == ""
    assert body["flavour"] == ""
    assert body["weight"] == 0
    assert body["price"] == 0
    assert body["units_per_box"] is None
    assert body["stock_qty"] == 0
    assert body["expiration_date"] is None


def test_create_missing_required_field_400(client):
    resp = client.post("/api/products", json={"name": "No Brand"})
    assert resp.status_code == 400
    assert "brand" in resp.get_json()["error"]


def test_create_missing_all_required_fields_400(client):
    resp = client.post("/api/products", json={})
    assert resp.status_code == 400
    assert "name" in resp.get_json()["error"]
    assert "brand" in resp.get_json()["error"]


def test_create_unknown_field_400(client, valid_payload):
    valid_payload["not_a_real_column"] = "sneaky"
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 400
    assert "not_a_real_column" in resp.get_json()["error"]


def test_create_cannot_set_id_directly(client, valid_payload):
    """`id` is intentionally excluded from ALLOWED_FIELDS -- a caller must
    not be able to choose a product's id via the create payload."""
    valid_payload["id"] = 99999
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 400
    assert "id" in resp.get_json()["error"]


@pytest.mark.parametrize("bad_price", [-1, "free", 9.99, None])
def test_create_invalid_price_400(client, valid_payload, bad_price):
    valid_payload["price"] = bad_price
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 400


@pytest.mark.parametrize("bad_units", [0, -3, "twelve", 1.5])
def test_create_invalid_units_per_box_400(client, valid_payload, bad_units):
    valid_payload["units_per_box"] = bad_units
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 400


def test_create_units_per_box_none_is_allowed(client, valid_payload):
    valid_payload["units_per_box"] = None
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 201


@pytest.mark.parametrize("bad_qty", [-1, "five", 2.5])
def test_create_invalid_stock_qty_400(client, valid_payload, bad_qty):
    valid_payload["stock_qty"] = bad_qty
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 400


@pytest.mark.parametrize("bad_date", ["2027/03/15", "15-03-2027", "not a date", "2027-13-40"])
def test_create_invalid_expiration_date_400(client, valid_payload, bad_date):
    valid_payload["expiration_date"] = bad_date
    resp = client.post("/api/products", json=valid_payload)
    assert resp.status_code == 400


def test_create_empty_body_400(client):
    resp = client.post("/api/products", data="", content_type="application/json")
    assert resp.status_code == 400


def test_create_logs_stock_history_create_entry(client, valid_payload):
    created = client.post("/api/products", json=valid_payload).get_json()
    history = client.get(f"/api/products/{created['id']}/history").get_json()
    assert len(history) == 1
    assert history[0]["source"] == "create"
    assert history[0]["previous_qty"] == 0
    assert history[0]["new_qty"] == valid_payload["stock_qty"]


def test_create_with_zero_stock_still_logs_history(client, valid_payload):
    """create uses skip_if_unchanged=False, so even a 0 -> 0 create is logged."""
    valid_payload["stock_qty"] = 0
    created = client.post("/api/products", json=valid_payload).get_json()
    history = client.get(f"/api/products/{created['id']}/history").get_json()
    assert len(history) == 1
    assert history[0]["source"] == "create"


def test_create_field_name_as_malicious_column_name_rejected(client, valid_payload):
    """Regression test: a crafted key can't ride into the INSERT column
    list -- ALLOWED_FIELDS whitelisting must reject it with 400, not a DB
    error or a successful write to an unintended column."""
    payload = dict(valid_payload)
    payload["name); DROP TABLE products;--"] = "x"
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 400

    # table must still be usable afterward
    follow_up = client.get("/api/products")
    assert follow_up.status_code == 200
