from __future__ import annotations

from dataclasses import dataclass


class OrderNotFound(LookupError):
    """Raised when an order id is not present in the store."""


@dataclass
class OrderRow:
    order_id: str
    amount_cents: int
    status: str


class OrderRepo:
    def __init__(self) -> None:
        self._rows: dict[str, OrderRow] = {}

    def add(self, row: OrderRow) -> None:
        if row.order_id in self._rows:
            raise ValueError(f"duplicate order id {row.order_id}")
        self._rows[row.order_id] = row

    def get(self, order_id: str) -> OrderRow:
        try:
            return self._rows[order_id]
        except KeyError as exc:
            raise OrderNotFound(order_id) from exc

    def save_status(self, order_id: str, status: str) -> OrderRow:
        row = self.get(order_id)
        row.status = status
        return row
