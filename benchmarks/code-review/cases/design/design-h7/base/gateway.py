"""Client wrapper for the card-capture provider used by lab order payments."""

import logging

from settings import PAYMENT_TIMEOUT_S

logger = logging.getLogger("payments.gateway")


class GatewayError(Exception):
    """Raised when a capture cannot be completed."""


class PaymentGateway:
    """Captures payments through the provider API."""

    def __init__(self, client):
        self._client = client

    def capture(self, order_id, amount_cents, idempotency_key):
        """Capture amount_cents for order_id and return the provider capture id."""
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        payload = {
            "order_ref": order_id,
            "amount_cents": amount_cents,
            "idempotency_key": idempotency_key,
        }
        try:
            response = self._client.post("/v1/captures", payload, timeout=PAYMENT_TIMEOUT_S)
        except Exception as exc:
            logger.error("capture rejected for %s", order_id, exc_info=True)
            raise GatewayError(f"capture failed for {order_id}") from exc
        logger.info("capture %s accepted for %s", response["capture_id"], order_id)
        return response["capture_id"]
