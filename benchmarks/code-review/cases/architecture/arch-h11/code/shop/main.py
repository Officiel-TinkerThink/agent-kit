"""Composition root: wires adapters into the application."""

from __future__ import annotations

from .application.notify import notify_order_total
from .application.ports import CatalogPort
from .domain.cart import Cart
from .infrastructure.catalogue import StaticCatalogue
from .infrastructure.mailer import ConsoleMailer


def main(catalogue: CatalogPort) -> None:
    cart = Cart(cart_id="c-1", quantities={"SKU-1": 2, "SKU-2": 1})
    mailer = ConsoleMailer(catalogue)
    total = notify_order_total(cart, catalogue, mailer, "shopper@example.com")
    print(f"total {total}")
    for line in mailer.outbox:
        print(line)


if __name__ == "__main__":
    main(StaticCatalogue())
