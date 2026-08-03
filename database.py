"""
database.py
Handles the SQLite connection and schema for the cat food database.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cat_food.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cat_foods (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    brand               TEXT NOT NULL,
    food_type           TEXT NOT NULL CHECK (food_type IN ('dry', 'wet', 'raw', 'freeze-dried')),
    life_stage          TEXT NOT NULL CHECK (life_stage IN ('kitten', 'adult', 'senior', 'all')),
    grain_free          INTEGER NOT NULL DEFAULT 0,       -- 0/1 boolean
    calories_per_100g   REAL,
    protein_percent     REAL,
    fat_percent         REAL,
    fiber_percent       REAL,
    moisture_percent    REAL,
    price           REAL,                             -- price per typical unit (bag/can)
    ingredients          TEXT,                            -- free-text ingredient list
    description         TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
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