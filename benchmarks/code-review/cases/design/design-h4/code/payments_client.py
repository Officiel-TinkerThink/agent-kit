"""Payment capture client for order intake."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from http_client import HttpClient, ServiceUnavailable
from models import ChargeRequest, ChargeResult, PaymentError, to_payload
from retry import full_jitter_delay, retry_call

LOGGER = logging.getLogger("orders.payments")

DEFAULT_TIMEOUT_S = 10.0
CHARGE_PATH = "/charges"
IDEMPOTENCY_HEADER = "Idempotency-Key"
REFUND_MAX_ATTEMPTS = 3


class PaymentsClient:
    """Captures payments and refunds through the gateway."""

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
        return self._attempt_charge(request)

    @retry_call(max_attempts=5)
    def _attempt_charge(self, request: ChargeRequest) -> ChargeResult:
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

    def refund(self, charge_id: str, amount_cents: int) -> ChargeResult:
        """Refund part or all of a charge; transient failures are retried with one key."""
        if amount_cents <= 0:
            raise PaymentError("refund amount must be positive")
        key = str(uuid.uuid4())
        path = f"{CHARGE_PATH}/{charge_id}/refunds"
        last_error: Optional[ServiceUnavailable] = None
        for attempt in range(1, REFUND_MAX_ATTEMPTS + 1):
            try:
                response = self._http.post(
                    path,
                    {"amount_cents": amount_cents},
                    headers={IDEMPOTENCY_HEADER: key},
                    timeout=self._timeout,
                )
            except ServiceUnavailable as exc:
                last_error = exc
                LOGGER.warning(
                    "refund attempt %d of %d for charge %s failed",
                    attempt,
                    REFUND_MAX_ATTEMPTS,
                    charge_id,
                )
                time.sleep(full_jitter_delay(attempt))
                continue
            return ChargeResult(
                charge_id=response["id"],
                status=response["status"],
                idempotency_key=key,
            )
        raise PaymentError(f"refund failed for charge {charge_id}") from last_error

    def void_authorization(self, charge_id: str) -> dict:
        """Void an uncaptured authorization; failures are raised with their cause."""
        try:
            return self._http.post(f"{CHARGE_PATH}/{charge_id}/void", {}, timeout=self._timeout)
        except Exception as exc:
            LOGGER.error("void failed for charge %s", charge_id)
            raise PaymentError(f"void failed for charge {charge_id}") from exc
