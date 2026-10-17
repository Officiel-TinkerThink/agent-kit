"""Order use cases used by the partner API."""

from __future__ import annotations

from typing import Mapping, Sequence

from .exporter import export_rows

ORDER_COLUMNS = ("order_id", "sku", "quantity", "status")


def export_orders_csv(orders: Sequence[Mapping[str, object]]) -> str:
    """Export orders with the fixed partner column set."""
    return export_rows(orders, columns=ORDER_COLUMNS)
