# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
"""Shared pytest fixtures for the CatifyInv API test suite.

Drop this `tests/` directory into the CatifyInv project root (next to
main.py, database.py, models.py), then:

    pip install pytest
    pytest

The sys.path.insert below makes `import database` / `import main` work
no matter what directory pytest is invoked from or with what arguments.
(An earlier version of this file relied on tests/pytest.ini's
`pythonpath = ..` option instead -- that only works if pytest's config
search actually reaches tests/pytest.ini, which it doesn't when invoked
as bare `pytest` from the project root: pytest searches from the
invocation args' common ancestor *upward*, never down into
subdirectories, so a bare `pytest` run from the project root never finds
an ini file that lives inside tests/. This runs unconditionally instead,
since conftest.py is always imported before collection.)

Each test gets its own throwaway SQLite file (via tmp_path), so tests
never touch your real cat_food.db and can run in any order or in
parallel.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # pylint: disable=wrong-import-position

import pytest  # noqa: E402  pylint: disable=wrong-import-position

import database  # noqa: E402  pylint: disable=wrong-import-position
import main as main_module  # noqa: E402  pylint: disable=wrong-import-position


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
