"""
seed.py
Populates the database with placeholder cat food entries so you have
something to browse right away. Safe to re-run: it clears existing
rows first.

Usage:
    python seed.py
"""
from database import get_connection, init_db

PLACEHOLDER_FOODS = [
    dict(
        name="Grain-Free Chicken Recipe",
        brand="Wildcat Naturals",
        food_type="dry",
        life_stage="adult",
        grain_free=1,
        calories_per_100g=390,
        protein_percent=42,
        fat_percent=18,
        fiber_percent=3.5,
        moisture_percent=10,
        price=24.99,
        ingredients="Chicken meal, peas, chicken fat, lentils, chicken, salmon oil",
        description="High-protein grain-free kibble built around real chicken meal.",
    ),
    dict(
        name="Classic Pate Salmon Dinner",
        brand="Purrfect Bowl",
        food_type="wet",
        life_stage="all",
        grain_free=0,
        calories_per_100g=95,
        protein_percent=10,
        fat_percent=6,
        fiber_percent=1,
        moisture_percent=78,
        price=1.29,
        ingredients="Salmon, chicken broth, liver, rice, salmon oil",
        description="Smooth pate-style canned food with salmon as the first ingredient.",
    ),
    dict(
        name="Kitten Growth Formula",
        brand="Little Paws",
        food_type="dry",
        life_stage="kitten",
        grain_free=0,
        calories_per_100g=430,
        protein_percent=40,
        fat_percent=22,
        fiber_percent=2.5,
        moisture_percent=8,
        price=19.99,
        ingredients="Chicken, brown rice, oatmeal, chicken fat, DHA, taurine",
        description="Nutrient-dense kibble formulated for kittens under 12 months.",
    ),
    dict(
        name="Senior Sensitive Digestion",
        brand="GentleCat",
        food_type="wet",
        life_stage="senior",
        grain_free=0,
        calories_per_100g=85,
        protein_percent=9,
        fat_percent=4,
        fiber_percent=1.5,
        moisture_percent=80,
        price=1.49,
        ingredients="Turkey, pumpkin, chicken broth, flaxseed, glucosamine",
        description="Easy-to-digest wet food with joint support for older cats.",
    ),
    dict(
        name="Raw Freeze-Dried Rabbit Bites",
        brand="Ancestral Feast",
        food_type="freeze-dried",
        life_stage="all",
        grain_free=1,
        calories_per_100g=520,
        protein_percent=48,
        fat_percent=30,
        fiber_percent=1,
        moisture_percent=5,
        price=34.99,
        ingredients="Rabbit meat, rabbit organs, rabbit bone, taurine",
        description="Single-protein raw diet, freeze-dried for shelf stability.",
    ),
    dict(
        name="Indoor Hairball Control",
        brand="TabbyTown",
        food_type="dry",
        life_stage="adult",
        grain_free=0,
        calories_per_100g=360,
        protein_percent=34,
        fat_percent=14,
        fiber_percent=6,
        moisture_percent=10,
        price=21.99,
        ingredients="Chicken meal, corn gluten meal, fiber blend, chicken fat",
        description="Higher-fiber kibble to help reduce hairballs in indoor cats.",
    ),
]


def seed():
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM cat_foods")
        conn.executemany(
            """
            INSERT INTO cat_foods (
                name, brand, food_type, life_stage, grain_free,
                calories_per_100g, protein_percent, fat_percent,
                fiber_percent, moisture_percent, price,
                ingredients, description
            ) VALUES (
                :name, :brand, :food_type, :life_stage, :grain_free,
                :calories_per_100g, :protein_percent, :fat_percent,
                :fiber_percent, :moisture_percent, :price,
                :ingredients, :description
            )
            """,
            PLACEHOLDER_FOODS,
        )
        conn.commit()
        print(f"Seeded {len(PLACEHOLDER_FOODS)} cat food entries.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()