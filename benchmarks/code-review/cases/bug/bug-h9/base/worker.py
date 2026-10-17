"""Payment request worker."""

import logging

from payments import validate_amount

logger = logging.getLogger("payments.worker")


def validate_request(request):
    """Return (key, amount_cents) from a request dict after validation."""
    key = request.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("key must be a non-empty string")
    amount_cents = validate_amount(request.get("amount_cents"))
    return key, amount_cents


def build_receipt(key, reference):
    """Return the receipt payload sent back to the client."""
    logger.info("receipt key=%s reference=%s", key, reference)
    return {"key": key, "reference": reference}
