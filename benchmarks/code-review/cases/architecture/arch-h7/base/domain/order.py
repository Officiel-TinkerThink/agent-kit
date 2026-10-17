"""Order aggregate: priced content of one customer order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.money import Money


@dataclass(frozen=True)
class Order:
    order_id: str
    subtotal: Money
    region: str
    tax: Optional[Money] = None
