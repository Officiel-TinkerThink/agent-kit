"""Order aggregate and total calculation."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

from infrastructure.db import fetch_discount_rate

CENT = Decimal("0.01")
ONE = Decimal("1")


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal


@dataclass
class Order:
    order_id: str
    customer_id: str
    lines: List[OrderLine] = field(default_factory=list)

    def subtotal(self) -> Decimal:
        return sum(
            (line.unit_price * line.quantity for line in self.lines),
            Decimal("0"),
        )

    def discount_rate(self) -> Decimal:
        return fetch_discount_rate(self.customer_id)

    def total(self) -> Decimal:
        rate = self.discount_rate()
        return (self.subtotal() * (ONE - rate)).quantize(CENT)
