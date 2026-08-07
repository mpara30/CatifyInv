# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
import pytest


# ---------- Cats CRUD ----------

def test_list_cats_empty(client):
    resp = client.get("/api/cats")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_cat(client):
    resp = client.post("/api/cats", json={"name": "Whiskers"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Whiskers"
    assert isinstance(body["id"], int)


def test_create_cat_missing_name(client):
    resp = client.post("/api/cats", json={})
    assert resp.status_code == 400
    assert "name" in resp.get_json()["error"]


def test_create_cat_blank_name(client):
    resp = client.post("/api/cats", json={"name": "   "})
    assert resp.status_code == 400


def test_create_cat_duplicate_name_conflicts(client):
    client.post("/api/cats", json={"name": "Whiskers"})
    resp = client.post("/api/cats", json={"name": "Whiskers"})
    assert resp.status_code == 409


def test_list_cats_sorted_by_name(client):
    client.post("/api/cats", json={"name": "Zeus"})
    client.post("/api/cats", json={"name": "Amber"})
    resp = client.get("/api/cats")
    names = [c["name"] for c in resp.get_json()]
    assert names == ["Amber", "Zeus"]


def test_delete_cat(client):
    create = client.post("/api/cats", json={"name": "Whiskers"})
    cat_id = create.get_json()["id"]

    resp = client.delete(f"/api/cats/{cat_id}")
    assert resp.status_code == 204
    assert client.get("/api/cats").get_json() == []


def test_delete_cat_not_found(client):
    resp = client.delete("/api/cats/9999")
    assert resp.status_code == 404


# ---------- Product <-> cat tagging ----------

def test_new_product_defaults_to_all_cats(client, valid_payload):
    resp = client.post("/api/products", json=valid_payload)
    body = resp.get_json()
    assert body["cat_ids"] == []
    assert body["cats"] == []


def test_create_product_with_cat_ids(client, valid_payload):
    cat = client.post("/api/cats", json={"name": "Whiskers"}).get_json()
    payload = {**valid_payload, "cat_ids": [cat["id"]]}

    resp = client.post("/api/products", json=payload)
    body = resp.get_json()
    assert body["cat_ids"] == [cat["id"]]
    assert body["cats"] == [{"id": cat["id"], "name": "Whiskers"}]


def test_create_product_with_unknown_cat_id_fails(client, valid_payload):
    payload = {**valid_payload, "cat_ids": [9999]}
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 400


def test_create_product_cat_ids_must_be_list_of_ints(client, valid_payload):
    payload = {**valid_payload, "cat_ids": "whiskers"}
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 400


def test_update_product_sets_cat_ids(client, make_product):
    cat = client.post("/api/cats", json={"name": "Mittens"}).get_json()
    product_id = make_product(name="Salmon Pate")

    resp = client.put(f"/api/products/{product_id}", json={"cat_ids": [cat["id"]]})
    body = resp.get_json()
    assert body["cat_ids"] == [cat["id"]]


def test_update_product_clears_cat_ids_back_to_all_cats(client, make_product):
    cat = client.post("/api/cats", json={"name": "Mittens"}).get_json()
    product_id = make_product(name="Salmon Pate")
    client.put(f"/api/products/{product_id}", json={"cat_ids": [cat["id"]]})

    resp = client.put(f"/api/products/{product_id}", json={"cat_ids": []})
    assert resp.get_json()["cat_ids"] == []


def test_update_product_without_cat_ids_leaves_tags_untouched(client, make_product):
    cat = client.post("/api/cats", json={"name": "Mittens"}).get_json()
    product_id = make_product(name="Salmon Pate")
    client.put(f"/api/products/{product_id}", json={"cat_ids": [cat["id"]]})

    resp = client.put(f"/api/products/{product_id}", json={"name": "Renamed"})
    body = resp.get_json()
    assert body["name"] == "Renamed"
    assert body["cat_ids"] == [cat["id"]]


def test_update_product_cat_only_change_is_not_rejected_as_empty(client, make_product):
    cat = client.post("/api/cats", json={"name": "Mittens"}).get_json()
    product_id = make_product(name="Salmon Pate")

    resp = client.put(f"/api/products/{product_id}", json={"cat_ids": [cat["id"]]})
    assert resp.status_code == 200


def test_update_product_unknown_cat_id_fails(client, make_product):
    product_id = make_product(name="Salmon Pate")
    resp = client.put(f"/api/products/{product_id}", json={"cat_ids": [9999]})
    assert resp.status_code == 400


def test_get_product_includes_cat_info(client, make_product):
    cat = client.post("/api/cats", json={"name": "Mittens"}).get_json()
    product_id = make_product(name="Salmon Pate")
    client.put(f"/api/products/{product_id}", json={"cat_ids": [cat["id"]]})

    resp = client.get(f"/api/products/{product_id}")
    body = resp.get_json()
    assert body["cat_ids"] == [cat["id"]]
    assert body["cats"] == [{"id": cat["id"], "name": "Mittens"}]


def test_deleting_a_cat_untags_its_products(client, make_product):
    cat = client.post("/api/cats", json={"name": "Mittens"}).get_json()
    product_id = make_product(name="Salmon Pate")
    client.put(f"/api/products/{product_id}", json={"cat_ids": [cat["id"]]})

    client.delete(f"/api/cats/{cat['id']}")

    resp = client.get(f"/api/products/{product_id}")
    assert resp.get_json()["cat_ids"] == []


# ---------- cat_id filter on GET /api/products ----------

def test_filter_by_cat_id_includes_tagged_and_all_cats_products(client, make_product):
    whiskers = client.post("/api/cats", json={"name": "Whiskers"}).get_json()
    mittens = client.post("/api/cats", json={"name": "Mittens"}).get_json()

    tagged_id = make_product(name="Whiskers Only")
    client.put(f"/api/products/{tagged_id}", json={"cat_ids": [whiskers["id"]]})
    shared_id = make_product(name="Shared Food")  # untagged -> all cats

    resp = client.get(f"/api/products?cat_id={whiskers['id']}")
    names = {p["name"] for p in resp.get_json()}
    assert names == {"Whiskers Only", "Shared Food"}

    resp = client.get(f"/api/products?cat_id={mittens['id']}")
    names = {p["name"] for p in resp.get_json()}
    assert names == {"Shared Food"}
    assert tagged_id not in [p["id"] for p in resp.get_json()]
    assert shared_id in [p["id"] for p in resp.get_json()]


def test_filter_by_invalid_cat_id_is_ignored(client, make_product):
    make_product(name="Anything")
    resp = client.get("/api/products?cat_id=not-a-number")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


# ---------- Feeding: adjust-stock with an optional cat_id ----------

def test_adjust_stock_with_cat_id_logs_as_feed(client, make_product):
    cat = client.post("/api/cats", json={"name": "Luna"}).get_json()
    pid = make_product(stock_qty=5)

    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": cat["id"]})
    assert resp.status_code == 200

    history = client.get(f"/api/products/{pid}/history").get_json()
    assert len(history) == 1
    assert history[0]["source"] == "feed"
    assert history[0]["cat_id"] == cat["id"]
    assert history[0]["cat_name"] == "Luna"


def test_adjust_stock_without_cat_id_still_logs_as_adjust(client, make_product):
    pid = make_product(stock_qty=5)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1})

    history = client.get(f"/api/products/{pid}/history").get_json()
    assert history[0]["source"] == "adjust"
    assert history[0]["cat_id"] is None
    assert history[0]["cat_name"] is None


def test_adjust_stock_with_unknown_cat_id_fails(client, make_product):
    pid = make_product(stock_qty=5)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": 9999})
    assert resp.status_code == 400


def test_adjust_stock_cat_id_must_be_integer(client, make_product):
    pid = make_product(stock_qty=5)
    resp = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": "Luna"})
    assert resp.status_code == 400


def test_feed_event_survives_cat_deletion(client, make_product):
    cat = client.post("/api/cats", json={"name": "Luna"}).get_json()
    pid = make_product(stock_qty=5)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": cat["id"]})

    client.delete(f"/api/cats/{cat['id']}")

    history = client.get(f"/api/products/{pid}/history").get_json()
    assert history[0]["source"] == "feed"
    assert history[0]["cat_name"] == "Luna"  # snapshot survives, unlike a live join would


def test_all_stock_history_filter_by_source_feed(client, make_product):
    cat = client.post("/api/cats", json={"name": "Luna"}).get_json()
    pid = make_product(stock_qty=5)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": cat["id"]})
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1})  # plain adjust, no cat

    resp = client.get("/api/stock-history?source=feed")
    entries = resp.get_json()
    assert len(entries) == 1
    assert entries[0]["cat_name"] == "Luna"


def test_all_stock_history_filter_by_cat_id(client, make_product):
    luna = client.post("/api/cats", json={"name": "Luna"}).get_json()
    tom = client.post("/api/cats", json={"name": "Tom"}).get_json()
    pid = make_product(stock_qty=5)
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": luna["id"]})
    client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -1, "cat_id": tom["id"]})

    resp = client.get(f"/api/stock-history?cat_id={luna['id']}")
    entries = resp.get_json()
    assert len(entries) == 1
    assert entries[0]["cat_name"] == "Luna"
