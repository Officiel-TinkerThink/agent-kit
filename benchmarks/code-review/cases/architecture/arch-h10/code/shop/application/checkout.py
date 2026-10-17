"""Checkout use case: computes the order total from catalogue prices."""

from __future__ import annotations

from typing import Dict

from ..domain.cart import Cart


def order_total_cents(cart: Cart, unit_prices_cents: Dict[str, int]) -> int:
    """Sum quantity multiplied by unit price over every cart line."""
    total = 0
    for sku, quantity in cart.quantities.items():
        total += unit_prices_cents[sku] * quantity
    return total
