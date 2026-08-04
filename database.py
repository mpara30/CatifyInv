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
    price               INTEGER NOT NULL DEFAULT 0,  -- price in cents
    stock_qty           INTEGER NOT NULL DEFAULT 0,
    expiration_date     TEXT,                    -- ISO date 'YYYY-MM-DD', nullable
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER,                -- not a FK on purpose: rows must survive product deletion
    product_name        TEXT NOT NULL,           -- snapshot at the time of the event
    product_brand       TEXT NOT NULL,           -- snapshot at the time of the event
    previous_qty        INTEGER NOT NULL,
    new_qty             INTEGER NOT NULL,
    delta               INTEGER NOT NULL,
    source              TEXT NOT NULL CHECK (source IN ('create', 'edit', 'adjust', 'delete')),
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_history_product_id ON stock_history(product_id);
"""


def get_connection():
    """Return a SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Create the database schema if it doesn't already exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {DB_PATH}")