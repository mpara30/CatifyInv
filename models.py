"""
models.py
Product dataclass for the cat food inventory, plus a factory method
that builds one from a raw sqlite3 row.
"""
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Optional


@dataclass
class Product:
    """Class representing a product."""
    id: int
    name: str
    brand: str
    category: str = ''
    flavour: str = ''
    weight: float = 0
    price: int = 0          # price PER INDIVIDUAL UNIT — matches stock_qty's unit
    units_per_box: Optional[int] = None  # Used to add a full box at once. None = not sold as a box.
    stock_qty: int = 0      # ALWAYS individual units on hand (cans/pouches/bags), never a box count
    expiration_date: Optional[date] = None

    @classmethod
    def from_row(cls, row) -> "Product":
        """Build a Product from a sqlite3.Row (or plain tuple) in column order:
        id, name, brand, category, flavour, weight, price, units_per_box, stock_qty, expiration_date
        """
        raw_expiration = row[9]
        if raw_expiration:
            expiration_date = datetime.strptime(raw_expiration, "%Y-%m-%d").date()
        else:
            expiration_date = None

        return cls(
            id=row[0],
            name=row[1],
            brand=row[2],
            category=row[3] or '',
            flavour=row[4] or '',
            weight=row[5] or 0,
            price=int(row[6]),
            units_per_box=int(row[7]) if row[7] is not None else None,
            stock_qty=int(row[8]),
            expiration_date=expiration_date,
        )

    def to_dict(self) -> dict:
        """Function converting a Product to a dict."""
        d = asdict(self)
        d["expiration_date"] = self.expiration_date.isoformat() if self.expiration_date else None
        d["price_ron"] = round(self.price / 100, 2)
        d["price_per_unit_ron"] = d["price_ron"]
        return d
