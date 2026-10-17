"""Notification use case: sends the order total to the shopper."""

from __future__ import annotations

from ..domain.cart import Cart
from ..infrastructure.ports import Notifier as MailSink
from .ports import CatalogPort


def notify_order_total(cart: Cart, catalogue: CatalogPort, notifier: MailSink, recipient: str) -> int:
    """Compute the cart total from catalogue prices, send it, and return it in cents."""
    total = 0
    for sku, quantity in cart.quantities.items():
        total += catalogue.unit_price_cents(sku) * quantity
    notifier.send(recipient, f"order total {total} cents")
    return total
