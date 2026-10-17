"""Shopping cart aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Cart:
    """Holds the quantity of each SKU in one shopper's cart."""

    cart_id: str
    quantities: Dict[str, int] = field(default_factory=dict)

    def add(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        self.quantities[sku] = self.quantities.get(sku, 0) + quantity

    def line_count(self) -> int:
        return len(self.quantities)
