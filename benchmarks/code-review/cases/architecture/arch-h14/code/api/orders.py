"""Partner order endpoints."""

from __future__ import annotations

from typing import List, Mapping, Optional, Sequence

from ..service.orders import export_orders_csv, filter_by_status


def export_orders(orders: Sequence[Mapping[str, object]]) -> str:
    """Return the partner order export as delimited text."""
    return export_orders_csv(orders)


def list_orders(
    orders: Sequence[Mapping[str, object]],
    status: Optional[str] = None,
    page_size: int = 50,
) -> List[Mapping[str, object]]:
    """Return orders filtered by status.

    page_size is part of the partner contract; paging is applied by the gateway.
    """
    return filter_by_status(orders, status)
