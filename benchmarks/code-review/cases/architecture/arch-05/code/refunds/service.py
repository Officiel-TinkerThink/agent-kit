from __future__ import annotations

import logging

from refunds.repo import RefundRepo, RefundRow

LOGGER = logging.getLogger("refunds.service")


class RefundError(Exception):
    """Raised when a refund request is invalid."""


class RefundService:
    def __init__(self, repo: RefundRepo) -> None:
        self._repo = repo

    def request_refund(self, order_id: str, amount_cents: int) -> RefundRow:
        if amount_cents <= 0:
            raise RefundError(f"refund amount must be positive for order {order_id}")
        LOGGER.info("requesting refund order=%s amount=%d", order_id, amount_cents)
        return self._repo.add_pending(order_id, amount_cents)
