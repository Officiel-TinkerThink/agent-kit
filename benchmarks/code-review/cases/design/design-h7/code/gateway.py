"""Client wrapper for the card-capture provider used by lab order payments."""

import logging

from settings import MAX_RETRIES, PAYMENT_TIMEOUT_S, QUOTA_TIMEOUT_S

logger = logging.getLogger("payments.gateway")


class GatewayError(Exception):
    """Raised when a capture cannot be completed."""


class TransientError(Exception):
    """Raised by the transport for retryable network errors and 5xx responses."""


class PaymentGateway:
    """Captures payments through the provider API with retry and quota checks."""

    def __init__(self, client, quota_client, max_retries=MAX_RETRIES):
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        self._client = client
        self._quota = quota_client
        self._max_retries = max_retries

    def capture(self, order_id, amount_cents, idempotency_key):
        """Capture amount_cents for order_id, retrying transient failures.

        Every attempt sends the same idempotency_key, so the provider applies
        the charge at most once even when a response is lost in transit.
        Returns the provider capture id.
        """
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if not self._quota_allows(order_id):
            raise GatewayError(f"quota check denied capture for {order_id}")

        payload = {
            "order_ref": order_id,
            "amount_cents": amount_cents,
            "idempotency_key": idempotency_key,
        }
        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.post("/v1/captures", payload, timeout=PAYMENT_TIMEOUT_S)
                capture_id = response["capture_id"]
            except TransientError as exc:
                last_error = exc
                logger.warning(
                    "capture attempt %d of %d failed for %s",
                    attempt,
                    self._max_retries,
                    order_id,
                )
                continue
            except Exception as exc:
                logger.error("capture rejected for %s", order_id, exc_info=True)
                raise GatewayError(f"capture failed for {order_id}") from exc
            logger.info("capture %s accepted for %s on attempt %d", capture_id, order_id, attempt)
            return capture_id
        raise GatewayError(
            f"capture not completed for {order_id} after {self._max_retries} attempts"
        ) from last_error

    def _quota_allows(self, order_id):
        """Return True only when the quota service confirms the capture is allowed."""
        try:
            decision = self._quota.check(order_id, timeout=QUOTA_TIMEOUT_S)
            return decision["allowed"] is True
        except Exception:
            logger.error("quota service unavailable for %s", order_id, exc_info=True)
            return False
