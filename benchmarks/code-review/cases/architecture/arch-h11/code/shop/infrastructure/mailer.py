"""Notifier adapter that collects messages in an in-memory outbox."""

from __future__ import annotations

from typing import List

from ..application.ports import CatalogPort
from ..domain.cart import Cart


class ConsoleMailer:
    """Formats receipts with catalogue prices and records outgoing messages."""

    def __init__(self, catalogue: CatalogPort) -> None:
        self._catalogue = catalogue
        self.outbox: List[str] = []

    def send(self, recipient: str, message: str) -> None:
        self.outbox.append(f"to={recipient} {message}")

    def receipt(self, recipient: str, cart: Cart) -> None:
        lines = [
            f"{sku} x{qty} @ {self._catalogue.unit_price_cents(sku)}"
            for sku, qty in sorted(cart.quantities.items())
        ]
        self.send(recipient, "; ".join(lines))
