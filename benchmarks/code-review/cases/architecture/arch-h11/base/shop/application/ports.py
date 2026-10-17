"""Ports (typing.Protocol classes) that the application layer depends on."""

from __future__ import annotations

from typing import Protocol


class CatalogPort(Protocol):
    """Read access to catalogue unit prices, in cents."""

    def unit_price_cents(self, sku: str) -> int:
        ...
