"""Checkout use case: prices an order before payment."""

from __future__ import annotations

from domain import Money
from domain.order import Order, apply_tax

TAX_SERVICE_URL = "https://tax.example.internal"


def checkout(order: Order) -> Order:
    """Return the order as it will be charged, with tax applied to a non-zero subtotal."""
    if order.subtotal == Money(0, order.subtotal.currency):
        return order
    return apply_tax(order, TAX_SERVICE_URL)
