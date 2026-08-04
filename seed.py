"""
seed.py
Populates the database with placeholder cat food product entries so you
have something to browse right away. Safe to re-run: it clears existing
rows first.

Usage:
    python seed.py
"""
from database import get_connection, init_db

PLACEHOLDER_PRODUCTS = [
    dict(
        name="Grain-Free Chicken Recipe",
        brand="Wildcat Naturals",
        category="dry",
        flavour="chicken",
        weight=2000,          # grams
        price=2499,            # cents -> $24.99
        stock_qty=42,
        expiration_date="2027-03-15",
    ),
    dict(
        name="Classic Pate Salmon Dinner",
        brand="Purrfect Bowl",
        category="wet",
        flavour="salmon",
        weight=85,
        price=129,
        stock_qty=180,
        expiration_date="2026-11-01",
    ),
    dict(
        name="Kitten Growth Formula",
        brand="Little Paws",
        category="dry",
        flavour="chicken",
        weight=1500,
        price=1999,
        stock_qty=0,
        expiration_date="2027-01-20",
    ),
    dict(
        name="Senior Sensitive Digestion",
        brand="GentleCat",
        category="wet",
        flavour="turkey",
        weight=85,
        price=149,
        stock_qty=95,
        expiration_date="2026-09-10",
    ),
    dict(
        name="Raw Freeze-Dried Rabbit Bites",
        brand="Ancestral Feast",
        category="freeze-dried",
        flavour="rabbit",
        weight=340,
        price=3499,
        stock_qty=12,
        expiration_date="2027-06-30",
    ),
    dict(
        name="Indoor Hairball Control",
        brand="TabbyTown",
        category="dry",
        flavour="chicken",
        weight=1800,
        price=2199,
        stock_qty=60,
        expiration_date="2026-08-25",
    ),
    dict(
        name="Crunchy Salmon Treats",
        brand="TabbyTown",
        category="treats",
        flavour="salmon",
        weight=60,
        price=399,
        stock_qty=200,
        expiration_date="2026-08-15",
    ),
]


def seed():
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM products")
        conn.executemany(
            """
            INSERT INTO products (
                name, brand, category, flavour, weight,
                price, stock_qty, expiration_date
            ) VALUES (
                :name, :brand, :category, :flavour, :weight,
                :price, :stock_qty, :expiration_date
            )
            """,
            PLACEHOLDER_PRODUCTS,
        )
        conn.commit()
        print(f"Seeded {len(PLACEHOLDER_PRODUCTS)} products.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()