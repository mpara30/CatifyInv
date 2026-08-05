# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
"""Shared pytest fixtures for the CatifyInv API test suite.

Drop this `tests/` directory into the CatifyInv project root (next to
main.py, database.py, models.py), then:

    pip install pytest
    pytest

`pytest.ini` (in this directory) sets `pythonpath = ..`, which puts the
project root on sys.path automatically -- this works no matter which
directory you invoke pytest from, and with either `pytest` or
`python -m pytest`.

Each test gets its own throwaway SQLite file (via tmp_path), so tests
never touch your real cat_food.db and can run in any order or in
parallel.
"""
import pytest

import database
import main as main_module


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Point the app at a fresh, empty SQLite DB for this test only."""
    db_path = tmp_path / "test_cat_food.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
    main_module.app.config.update(TESTING=True)
    yield main_module.app


@pytest.fixture()
def client(app):  # pylint: disable=redefined-outer-name
    """Flask test client wired to the isolated test DB."""
    return app.test_client()


@pytest.fixture()
def db_conn(app):  # pylint: disable=redefined-outer-name
    """Direct DB connection against the same test DB, for setup/assertions
    that intentionally bypass the API (e.g. seeding fixtures, checking
    stock_history rows the API doesn't expose)."""
    conn = database.get_connection()
    yield conn
    conn.close()


DEFAULT_PRODUCT = {
    "name": "Test Kibble",
    "brand": "TestBrand",
    "category": "dry",
    "flavour": "chicken",
    "weight": 1000,
    "price": 1000,
    "units_per_box": None,
    "stock_qty": 5,
    "expiration_date": None,
}


def insert_product(conn, **overrides):
    """Insert a product directly (bypassing the API/validation) and return
    its id. Useful for setting up list/filter/sort fixtures quickly."""
    product = {**DEFAULT_PRODUCT, **overrides}
    cur = conn.execute(
        """
        INSERT INTO products (
            name, brand, category, flavour, weight,
            price, units_per_box, stock_qty, expiration_date
        ) VALUES (
            :name, :brand, :category, :flavour, :weight,
            :price, :units_per_box, :stock_qty, :expiration_date
        )
        """,
        product,
    )
    conn.commit()
    return cur.lastrowid


@pytest.fixture()
def make_product(db_conn):  # pylint: disable=redefined-outer-name
    """Factory fixture: make_product(name="...", stock_qty=0, ...) -> id"""

    def _make(**overrides):
        return insert_product(db_conn, **overrides)

    return _make


@pytest.fixture()
def valid_payload():
    """A minimal, fully valid create-product payload."""
    return {
        "name": "Grain-Free Chicken Recipe",
        "brand": "Wildcat Naturals",
        "category": "dry",
        "flavour": "chicken",
        "weight": 2000,
        "price": 11499,
        "units_per_box": None,
        "stock_qty": 2,
        "expiration_date": "2027-03-15",
    }
