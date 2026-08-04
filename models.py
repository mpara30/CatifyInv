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
    id: int
    name: str
    brand: str
    category: str = ''
    flavour: str = ''
    weight: float = 0
    price: int = 0
    stock_qty: int = 0
    expiration_date: Optional[date] = None

    @classmethod
    def from_row(cls, row) -> "Product":
        """Build a Product from a sqlite3.Row (or plain tuple) in column order:
        id, name, brand, category, flavour, weight, price, stock_qty, expiration_date
        """
        raw_expiration = row[8]
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
            stock_qty=int(row[7]),
            expiration_date=expiration_date,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["expiration_date"] = self.expiration_date.isoformat() if self.expiration_date else None
        d["price_ron"] = round(self.price / 100, 2)
        return d