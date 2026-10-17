from __future__ import annotations

from dataclasses import dataclass

from orders.service import OrderStatus


@dataclass
class RefundRow:
    order_id: str
    amount_cents: int
    status: str


class RefundRepo:
    def __init__(self) -> None:
        self._rows: dict[str, RefundRow] = {}

    def add_pending(self, order_id: str, amount_cents: int) -> RefundRow:
        if order_id in self._rows:
            raise ValueError(f"refund already recorded for order {order_id}")
        row = RefundRow(order_id, amount_cents, "PENDING")
        self._rows[order_id] = row
        return row

    def add_pending_if_refundable(self, order_id: str, amount_cents: int, order_status: OrderStatus) -> bool:
        if order_status is not OrderStatus.PAID:
            return False
        self.add_pending(order_id, amount_cents)
        return True

    def get(self, order_id: str) -> RefundRow | None:
        return self._rows.get(order_id)
