"""Partner order endpoints."""

from __future__ import annotations

from typing import Mapping, Sequence

from ..service.orders import export_orders_csv


def export_orders(orders: Sequence[Mapping[str, object]]) -> str:
    """Return the partner order export as delimited text."""
    return export_orders_csv(orders)
