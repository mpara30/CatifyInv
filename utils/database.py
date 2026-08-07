"""
database.py
Handles the SQLite connection and schema for the cat food product database.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cat_food.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    brand               TEXT NOT NULL,
    category            TEXT,                    -- e.g. 'dry', 'wet', 'raw', 'treats'
    flavour             TEXT,                    -- e.g. 'chicken', 'salmon'
    weight              REAL,                    -- grams (or whatever unit you standardize on)
    price               INTEGER NOT NULL DEFAULT 0,  -- price PER INDIVIDUAL UNIT, in bani (RON subunit) — matches stock_qty's unit
    units_per_box       INTEGER,                 -- optional: items inside one box/case (e.g. 12 cans). Used to add a full box at once. NULL = not sold as a box.
    stock_qty           INTEGER NOT NULL DEFAULT 0,  -- ALWAYS individual units on hand (cans/pouches/bags), never a box count
    expiration_date     TEXT,                    -- ISO date 'YYYY-MM-DD', nullable
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Kept separate from SCHEMA (but included in it below) so _migrate_stock_history
# can recreate this exact table on its own during an in-place migration --
# single source of truth for the table's current shape either way.
STOCK_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS stock_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER,                -- not a FK on purpose: rows must survive product deletion
    product_name        TEXT NOT NULL,           -- snapshot at the time of the event
    product_brand       TEXT NOT NULL,           -- snapshot at the time of the event
    cat_id              INTEGER,                 -- not a FK on purpose: rows must survive cat deletion
    cat_name            TEXT,                    -- snapshot at the time of the event; NULL if no cat was specified
    previous_qty        INTEGER NOT NULL,
    new_qty             INTEGER NOT NULL,
    delta               INTEGER NOT NULL,
    source              TEXT NOT NULL CHECK (source IN ('create', 'edit', 'adjust', 'delete', 'feed')),
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_history_product_id ON stock_history(product_id);
"""

SCHEMA += STOCK_HISTORY_DDL

SCHEMA += """
CREATE TABLE IF NOT EXISTS cats (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

-- A product with NO rows here is implicitly "for all cats". A product with
-- one or more rows here is only for those specific cats.
CREATE TABLE IF NOT EXISTS product_cats (
    product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    cat_id              INTEGER NOT NULL REFERENCES cats(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, cat_id)
);

CREATE INDEX IF NOT EXISTS idx_product_cats_cat_id ON product_cats(cat_id);
"""


def get_connection():
    """Return a SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _table_exists(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}  # nosec B608


def _migrate_stock_history(conn):
    """Older databases have a stock_history table from before cat tracking
    was added: no cat_id/cat_name columns, and a CHECK constraint that
    doesn't allow the 'feed' source. SQLite can't ALTER a CHECK constraint
    in place, so when that gap is detected, the table is safely rebuilt:
    renamed aside, recreated with the current shape, data copied back over
    (existing rows just get NULL cat_id/cat_name), old copy dropped.

    This is the general pattern for any future stock_history schema change
    too, not just this one -- add the new column(s) to the CREATE TABLE
    above, then extend the "needs_rebuild" check and PRESERVED_COLUMNS
    below to match.
    """
    if not _table_exists(conn, "stock_history"):
        return  # fresh install; CREATE TABLE IF NOT EXISTS above already made the current shape

    needs_rebuild = "cat_id" not in _columns(conn, "stock_history")
    if not needs_rebuild:
        return

    preserved_columns = [
        "id", "product_id", "product_name", "product_brand",
        "previous_qty", "new_qty", "delta", "source", "created_at",
    ]
    old_columns = _columns(conn, "stock_history")
    copy_columns = [c for c in preserved_columns if c in old_columns]
    column_list = ", ".join(copy_columns)

    conn.execute("ALTER TABLE stock_history RENAME TO stock_history_old")
    conn.executescript(STOCK_HISTORY_DDL)
    conn.execute(
        f"INSERT INTO stock_history ({column_list}) "  # nosec B608
        f"SELECT {column_list} FROM stock_history_old"
    )
    conn.execute("DROP TABLE stock_history_old")


def init_db():
    """Create the database schema if it doesn't already exist, and migrate
    an existing database in place if it predates a schema change (rather
    than requiring the file to be deleted and recreated)."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        _migrate_stock_history(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {DB_PATH}")