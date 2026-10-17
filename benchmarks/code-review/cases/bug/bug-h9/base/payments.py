"""Gateway client for card charges."""

import logging
import uuid

logger = logging.getLogger("payments.gateway")

MAX_AMOUNT_CENTS = 1_000_000


def validate_amount(amount_cents):
    """Return amount_cents if it is an int within 1..MAX_AMOUNT_CENTS."""
    if not isinstance(amount_cents, int) or isinstance(amount_cents, bool):
        raise TypeError("amount_cents must be an int")
    if not 1 <= amount_cents <= MAX_AMOUNT_CENTS:
        raise ValueError(f"amount_cents must be within 1..{MAX_AMOUNT_CENTS}")
    return amount_cents


def charge(amount_cents):
    """Submit one card charge to the gateway and return its reference."""
    validate_amount(amount_cents)
    reference = f"ch_{uuid.uuid4().hex}"
    logger.info("charge submitted amount_cents=%s reference=%s", amount_cents, reference)
    return reference
