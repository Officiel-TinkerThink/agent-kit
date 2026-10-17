from __future__ import annotations

import logging
from enum import Enum

from orders.repo import OrderRepo, OrderRow
from refunds.repo import RefundRepo

LOGGER = logging.getLogger("orders.service")


class OrderStatus(str, Enum):
    NEW = "NEW"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class OrderError(Exception):
    """Raised when an order transition is not allowed."""


class OrderService:
    def __init__(self, repo: OrderRepo, refunds: RefundRepo) -> None:
        self._repo = repo
        self._refunds = refunds

    def mark_paid(self, order_id: str) -> OrderRow:
        row = self._repo.get(order_id)
        if OrderStatus(row.status) is not OrderStatus.NEW:
            raise OrderError(f"order {order_id} cannot be paid from {row.status}")
        LOGGER.info("marking order %s as paid", order_id)
        return self._repo.save_status(order_id, OrderStatus.PAID.value)

    def cancel(self, order_id: str) -> OrderRow:
        row = self._repo.get(order_id)
        current = OrderStatus(row.status)
        if current is OrderStatus.CANCELLED:
            raise OrderError(f"order {order_id} is already cancelled")
        LOGGER.info("cancelling order %s", order_id)
        self._refunds.add_pending_if_refundable(order_id, row.amount_cents, current)
        return self._repo.save_status(order_id, OrderStatus.CANCELLED.value)
