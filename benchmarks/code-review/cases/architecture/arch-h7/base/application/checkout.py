"""Checkout use case: prices an order before payment."""

from __future__ import annotations

from domain.order import Order

TAX_SERVICE_URL = "https://tax.example.internal"


def checkout(order: Order) -> Order:
    """Return the order as it will be charged."""
    return order
