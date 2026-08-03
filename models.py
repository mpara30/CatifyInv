from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Dict, Any

@dataclass
class Product:
    id: Optional[int]
    name: str
    brand: str
    category: str
    flavour: str
    weight: int
    price: int
    stock_qty: int
    expiration_date: Optional[date] = None

    def is_expired(self) -> bool:
        return self.expiration_date is not None and self.expiration_date < date.today()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'brand': self.brand,
            'category': self.category,
            'flavour': self.flavour,
            'weight': self.weight,
            'price': self.price,
            'stock_qty': self.stock_qty,
            'expiration_date': self.expiration_date.isoformat() if self.expiration_date else None,
        }

    @staticmethod
    def from_row(row) -> 'Product':
        expiration_date = None

        if row[8]:
            expiration_date = datetime.strptime(row[8], '%Y-%m-%d').date()

        return Product(
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