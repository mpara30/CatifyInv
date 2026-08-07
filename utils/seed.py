"""
seed.py
Populates the database with placeholder cat food product entries so you
have something to browse right away. Safe to re-run: it clears existing
rows first.

Usage:
    python seed.py
"""
from utils.database import get_connection, init_db

PLACEHOLDER_PRODUCTS = [
    dict(
        name="Grain-Free Chicken Recipe",
        brand="Wildcat Naturals",
        category="dry",
        flavour="chicken",
        weight=2000,          # grams
        price=11499,           # bani -> 114.99 RON per box
        units_per_box=None,
        stock_qty=2,
        expiration_date="2027-03-15",
    ),
    dict(
        name="Classic Pate Salmon Dinner",
        brand="Purrfect Bowl",
        category="wet",
        flavour="salmon",
        weight=85,
        price=599,
        units_per_box=None,
        stock_qty=8,
        expiration_date="2026-11-01",
    ),
    dict(
        name="Kitten Growth Formula",
        brand="Little Paws",
        category="dry",
        flavour="chicken",
        weight=1500,
        price=9199,
        units_per_box=None,
        stock_qty=0,
        expiration_date="2027-01-20",
    ),
    dict(
        name="Senior Sensitive Digestion",
        brand="GentleCat",
        category="wet",
        flavour="turkey",
        weight=85,
        price=699,
        units_per_box=None,
        stock_qty=5,
        expiration_date="2026-09-10",
    ),
    dict(
        name="Raw Freeze-Dried Rabbit Bites",
        brand="Ancestral Feast",
        category="freeze-dried",
        flavour="rabbit",
        weight=340,
        price=16099,
        units_per_box=None,
        stock_qty=1,
        expiration_date="2027-06-30",
    ),
    dict(
        name="Indoor Hairball Control",
        brand="TabbyTown",
        category="dry",
        flavour="chicken",
        weight=1800,
        price=10199,
        units_per_box=None,
        stock_qty=3,
        expiration_date="2026-08-25",
    ),
    dict(
        name="Crunchy Salmon Treats",
        brand="TabbyTown",
        category="treats",
        flavour="salmon",
        weight=60,
        price=317,                 # bani -> 3.17 RON PER POUCH (18.99 RON box of 6 ÷ 6)
        units_per_box=6,          # sold as a box of 6 pouches
        stock_qty=12,              # 2 boxes' worth, tracked as individual pouches
        expiration_date="2026-08-15",
    ),
]


PLACEHOLDER_CATS = ["Luna", "Tom"]

# Maps product name -> list of cat names it's tagged to. Anything not listed
# here stays untagged, i.e. "all cats" (the default).
PLACEHOLDER_PRODUCT_CATS = {
    "Kitten Growth Formula": ["Luna"],
    "Senior Sensitive Digestion": ["Tom"],
}


def seed():
    """Function used to seed the database."""
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM products")
        conn.executemany(
            """
            INSERT INTO products (
                name, brand, category, flavour, weight,
                price, units_per_box, stock_qty, expiration_date
            ) VALUES (
                :name, :brand, :category, :flavour, :weight,
                :price, :units_per_box, :stock_qty, :expiration_date
            )
            """,
            PLACEHOLDER_PRODUCTS,
        )

        conn.execute("DELETE FROM product_cats")
        conn.execute("DELETE FROM cats")
        conn.executemany(
            "INSERT INTO cats (name) VALUES (?)",
            [(name,) for name in PLACEHOLDER_CATS],
        )

        name_to_product_id = dict(
            conn.execute("SELECT name, id FROM products").fetchall()
        )
        name_to_cat_id = dict(
            conn.execute("SELECT name, id FROM cats").fetchall()
        )
        for product_name, cat_names in PLACEHOLDER_PRODUCT_CATS.items():
            product_id = name_to_product_id[product_name]
            for cat_name in cat_names:
                conn.execute(
                    "INSERT INTO product_cats (product_id, cat_id) VALUES (?, ?)",
                    (product_id, name_to_cat_id[cat_name]),
                )

        conn.commit()
        print(f"Seeded {len(PLACEHOLDER_PRODUCTS)} products and {len(PLACEHOLDER_CATS)} cats.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
