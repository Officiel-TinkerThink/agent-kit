"""Catalogue adapter backed by an in-process price table."""

from __future__ import annotations

from typing import Dict

from ..application.ports import CatalogPort

PRICES_CENTS: Dict[str, int] = {"SKU-1": 1250, "SKU-2": 899}


class StaticCatalogue(CatalogPort):
    """Serves unit prices from PRICES_CENTS."""

    def unit_price_cents(self, sku: str) -> int:
        try:
            return PRICES_CENTS[sku]
        except KeyError:
            raise LookupError(f"unknown sku {sku}") from None
