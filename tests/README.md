# CatifyInv test suite

## Setup

Place this `tests/` folder directly inside your `cat_food_db/` project
root, next to `main.py`, `database.py`, and `models.py`:

```
cat_food_db/
├── app.py / main.py
├── database.py
├── models.py
├── seed.py
├── cat_food.db
├── frontend/
└── tests/            <- this folder
    ├── conftest.py
    ├── requirements-test.txt
    └── test_*.py
```

Then, from `cat_food_db/`:

```bash
pip install -r requirements.txt
pip install -r tests/requirements-test.txt
pytest
```

This works whether you run it from the project root or from inside
`tests/` -- `tests/pytest.ini` sets `pythonpath = ..`, which tells pytest
itself to put the project root on `sys.path` (pytest >= 7.0 required,
already pinned in `requirements-test.txt`). No `sys.path` hacks, no
`__init__.py` needed in `tests/`.

## How isolation works

Every test gets a brand-new, empty SQLite file created in a pytest
`tmp_path`, via a `monkeypatch` of `database.DB_PATH`. Your real
`cat_food.db` is never touched, and tests don't affect each other.

## What's covered

- `test_health.py` — health check
- `test_stats.py` — dashboard aggregates (counts, value, expiring-soon window)
- `test_list_products.py` — all filters, all sortable fields, sort/order
  edge cases, and a regression test for the `sort` SQL-injection fix
- `test_get_product.py` — fetch by id, 404, non-integer id
- `test_create_product.py` — happy path, defaults, every validation rule,
  unknown-field/whitelist rejection, injection-hardening regressions
- `test_update_product.py` — partial updates, validation, unknown-field
  rejection, `id` immutability, stock-history logging behavior
- `test_adjust_stock.py` — increment/decrement, zero-clamping, validation,
  history logging (including the clamped delta being logged correctly)
- `test_delete_product.py` — deletion, 404, history logged and surviving
  product deletion (no FK)
- `test_stock_history.py` — global and per-product history endpoints:
  filtering, ordering, `limit` handling

## Pylint

Every test file starts with:

```python
# pylint: disable=missing-module-docstring,missing-function-docstring,redefined-outer-name
```

This is a **file-scoped inline disable**, so it applies no matter what
directory you run pylint from -- unlike `tests/.pylintrc`, which pylint
only picks up if you run it *from inside* `tests/` or pass
`--rcfile=tests/.pylintrc` explicitly (pylint's config search starts at
your current working directory, not at the files being linted). Both are
included: the inline comments are what actually take effect in the
common case (`pylint tests/` from the project root); `.pylintrc` is
there if you'd rather point `--rcfile` at it instead of touching every
file.

Why these three, specifically, and only in `tests/`:

- **missing-module-docstring / missing-function-docstring** -- test
  names are written to double as the docstring
  (`test_adjust_stock_clamps_at_zero` doesn't need a second sentence
  saying the same thing). A handful of tests that need extra context
  (e.g. the sort-injection regression test) already have a real
  docstring explaining why.
- **redefined-outer-name** -- pylint doesn't understand pytest's
  fixture injection: `def client(app):` intentionally takes a
  same-named fixture as a parameter; that's how fixtures compose, not
  accidental shadowing.

These are not disabled anywhere in your application code, only in this
test directory.

`GET /api/products` with an invalid `sort` value currently hits:

```python
if sort not in SORTABLE_FIELDS:
    raise ValueError(f"Invalid sort field: {sort}")
```

This raises an *unhandled* exception rather than returning a clean 400.
With `TESTING=True` (as in these tests), Flask re-raises it through the
test client instead of turning it into a 500 response, which is why
`test_invalid_sort_field_does_not_leak_into_query` uses
`pytest.raises(ValueError)`. In production (`TESTING=False`), the same
request would surface as a generic 500 Internal Server Error page instead
of a helpful JSON error.

There's also dead code right after it:

```python
if sort not in SORTABLE_FIELDS:
    raise ValueError(...)

if sort not in SORTABLE_FIELDS:   # unreachable -- the branch above already raised
    sort = "name"
```

Recommended fix, replacing both blocks:

```python
if sort not in SORTABLE_FIELDS:
    return jsonify(error=f"Invalid sort field: {sort}"), 400
```

If you make that change, update the regression test in
`test_list_products.py` to assert `resp.status_code == 400` instead of
`pytest.raises(ValueError)`.
