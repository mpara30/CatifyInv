# Cat Food Database — API

A small REST API for browsing and managing a database of cat foods.
Built with **Flask** and Python's built-in **sqlite3** — no external
database server needed.

## Project structure

```
cat_food_db/
├── app.py           # Flask app: all API routes
├── database.py       # SQLite connection + schema
├── seed.py            # Loads placeholder cat food data
├── requirements.txt
├── cat_food.db        # created automatically (SQLite file)
└── README.md
```

## Setup

```bash
cd cat_food_db
pip install -r requirements.txt
python seed.py      # creates cat_food.db and loads 6 sample entries
python app.py        # starts the API at http://127.0.0.1:5000
```

Re-run `python seed.py` any time to reset the data back to the placeholder set.

## Data model

Each cat food entry has:

| Field               | Type    | Notes                                        |
|---------------------|---------|-----------------------------------------------|
| id                  | int     | auto-assigned                                  |
| name                | string  | required                                       |
| brand               | string  | required                                       |
| food_type           | string  | required: `dry`, `wet`, `raw`, `freeze-dried`  |
| life_stage          | string  | required: `kitten`, `adult`, `senior`, `all`   |
| grain_free          | bool    | default `false`                                |
| calories_per_100g   | number  |                                                 |
| protein_percent     | number  |                                                 |
| fat_percent         | number  |                                                 |
| fiber_percent       | number  |                                                 |
| moisture_percent    | number  |                                                 |
| price_usd           | number  | per bag/can, whatever unit you choose          |
| ingredients         | string  | free text                                      |
| description         | string  | free text                                      |

## Endpoints

| Method | Path              | Description                     |
|--------|-------------------|----------------------------------|
| GET    | /api/health       | health check                     |
| GET    | /api/foods        | list foods (filters below)       |
| GET    | /api/foods/<id>   | get one food                     |
| POST   | /api/foods        | create a food                    |
| PUT    | /api/foods/<id>   | update a food (partial OK)       |
| DELETE | /api/foods/<id>   | delete a food                    |

### Filtering / searching `GET /api/foods`

Combine any of these as query params:

- `q=salmon` — free-text search across name, brand, ingredients, description
- `brand=Purrfect Bowl`
- `food_type=dry`
- `life_stage=kitten`
- `grain_free=true`
- `min_protein=30`
- `max_price=25`
- `sort=protein_percent&order=desc`

Example:
```bash
curl "http://127.0.0.1:5000/api/foods?food_type=dry&grain_free=true&sort=protein_percent&order=desc"
```

### Creating a food

```bash
curl -X POST http://127.0.0.1:5000/api/foods \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Ocean Whitefish Formula",
        "brand": "Coastal Cat Co.",
        "food_type": "dry",
        "life_stage": "adult",
        "grain_free": true,
        "protein_percent": 38,
        "price_usd": 22.50
      }'
```

### Updating a food (partial update is fine)

```bash
curl -X PUT http://127.0.0.1:5000/api/foods/1 \
  -H "Content-Type: application/json" \
  -d '{"price_usd": 26.99}'
```

### Deleting a food

```bash
curl -X DELETE http://127.0.0.1:5000/api/foods/1
```