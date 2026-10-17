"""Order use cases used by the partner API."""

from __future__ import annotations

from typing import List, Mapping, Optional, Sequence

from .exporter import export_rows

ORDER_COLUMNS = ("order_id", "sku", "quantity", "status")


def export_orders_csv(orders: Sequence[Mapping[str, object]]) -> str:
    """Export orders with the fixed partner column set."""
    return export_rows(orders, columns=ORDER_COLUMNS)


def filter_by_status(
    orders: Sequence[Mapping[str, object]], status: Optional[str]
) -> List[Mapping[str, object]]:
    """Return orders whose status matches; all orders when status is None."""
    if status is None:
        return list(orders)
    return [order for order in orders if order.get("status") == status]
