"""Persistence adapters for the shop."""

from __future__ import annotations

from typing import Dict

from ..domain.cart import Cart

CATALOGUE_PRICES_CENTS: Dict[str, int] = {"SKU-1": 1250, "SKU-2": 899}


class SqlRepo:
    """Stores carts and reads catalogue data."""

    def __init__(self) -> None:
        self._carts: Dict[str, Cart] = {}

    def save_cart(self, cart: Cart) -> None:
        self._carts[cart.cart_id] = cart

    def load_cart(self, cart_id: str) -> Cart:
        return self._carts[cart_id]
