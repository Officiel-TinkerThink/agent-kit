"""Payment capture client for order intake."""

from __future__ import annotations

import logging
import uuid

from http_client import HttpClient
from models import ChargeRequest, ChargeResult, PaymentError, to_payload

LOGGER = logging.getLogger("orders.payments")

DEFAULT_TIMEOUT_S = 10.0
CHARGE_PATH = "/charges"
IDEMPOTENCY_HEADER = "Idempotency-Key"


class PaymentsClient:
    """Captures payments through the gateway."""

    def __init__(self, http: HttpClient, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._http = http
        self._timeout = timeout_s

    def charge(self, request: ChargeRequest) -> ChargeResult:
        """Capture the payment for an order and return the gateway result."""
        if request.amount_cents <= 0:
            raise PaymentError(f"amount must be positive for order {request.order_id}")
        LOGGER.info("charging order %s amount=%d", request.order_id, request.amount_cents)
        key = str(uuid.uuid4())
        response = self._http.post(
            CHARGE_PATH,
            to_payload(request),
            headers={IDEMPOTENCY_HEADER: key},
            timeout=self._timeout,
        )
        return ChargeResult(
            charge_id=response["id"],
            status=response["status"],
            idempotency_key=key,
        )
