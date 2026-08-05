def test_get_existing_product(client, make_product):
    pid = make_product(name="Salmon Pate", brand="Purrfect Bowl", price=599)
    resp = client.get(f"/api/products/{pid}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == pid
    assert body["name"] == "Salmon Pate"
    assert body["brand"] == "Purrfect Bowl"
    assert body["price"] == 599
    assert body["price_ron"] == 5.99


def test_get_missing_product_404(client):
    resp = client.get("/api/products/99999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Not found"


def test_get_product_non_integer_id_404s_via_routing(client):
    # <int:product_id> converter rejects non-integer path segments
    resp = client.get("/api/products/not-an-id")
    assert resp.status_code == 404
