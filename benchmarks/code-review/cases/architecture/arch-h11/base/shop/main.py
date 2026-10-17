"""Composition root: wires adapters into the application."""

from __future__ import annotations

from .application.ports import CatalogPort
from .domain.cart import Cart
from .infrastructure.mailer import ConsoleMailer


def main(catalogue: CatalogPort) -> None:
    cart = Cart(cart_id="c-1", quantities={"SKU-1": 2, "SKU-2": 1})
    mailer = ConsoleMailer(catalogue)
    mailer.receipt("shopper@example.com", cart)
    for line in mailer.outbox:
        print(line)
