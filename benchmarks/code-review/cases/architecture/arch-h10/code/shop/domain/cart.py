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

    def price_of(self, sku: str) -> int:
        """Return the catalogue unit price in cents for a SKU in this cart."""
        if sku not in self.quantities:
            raise KeyError(f"sku {sku} is not in cart {self.cart_id}")
        from ..infrastructure.repo import SqlRepo

        return SqlRepo().unit_price_cents(sku)
