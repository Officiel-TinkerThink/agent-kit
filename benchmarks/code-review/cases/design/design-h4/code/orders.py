"""Order intake: validation, payment capture and gateway confirmation."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from http_client import HttpClient
from models import ChargeRequest, Order, OrderValidationError, PaymentError
from payments_client import PaymentsClient

LOGGER = logging.getLogger("orders.service")

STATUS_TIMEOUT_S = 5.0
PAID_STATUSES = frozenset({"succeeded", "captured"})


class OrderService:
    """Coordinates order intake across the payment and order gateways."""

    def __init__(
        self,
        payments: PaymentsClient,
        http: HttpClient,
        store: Dict[str, Order],
    ) -> None:
        self._payments = payments
        self._http = http
        self._store = store

    def place_order(
        self,
        order: Order,
        card_token: str,
        card_number: Optional[str] = None,
    ) -> Order:
        """Validate the order, capture payment and store the result."""
        if not order.items:
            raise OrderValidationError(f"order {order.order_id} has no items")
        if order.order_id in self._store:
            raise OrderValidationError(f"order {order.order_id} already exists")
        request = ChargeRequest(
            order_id=order.order_id,
            amount_cents=order.total_cents,
            currency=order.currency,
            card_token=card_token,
            card_number=card_number,
        )
        result = self._payments.charge(request)
        order.status = "PAID" if result.status in PAID_STATUSES else "PAYMENT_PENDING"
        self._store[order.order_id] = order
        LOGGER.info("order %s status=%s charge=%s", order.order_id, order.status, result.charge_id)
        return order

    def confirm_with_gateway(self, order: Order) -> Dict[str, Any]:
        """Send the stored order state to the order gateway for confirmation."""
        if order.order_id not in self._store:
            raise OrderValidationError(f"order {order.order_id} is not stored")
        payload = {
            "order_id": order.order_id,
            "status": order.status,
            "total_cents": order.total_cents,
        }
        confirmation = self._http.post("/orders/confirm", payload)
        LOGGER.info("order %s confirmed by gateway", order.order_id)
        return confirmation

    def fetch_order_status(self, order_id: str) -> str:
        """Return the gateway state for an order, failing fast on a stalled gateway."""
        status = self._http.get(f"/orders/{order_id}/status", timeout=STATUS_TIMEOUT_S)
        if "state" not in status:
            raise PaymentError(f"gateway returned no state for order {order_id}")
        return status["state"]
