"""Order identifiers for the dispensing queue."""

import logging

logger = logging.getLogger("orders.model")

MAX_ORDER_ID_LENGTH = 32


def validate_order_id(order_id):
    """Return the stripped order id or raise ValueError."""
    if not isinstance(order_id, str):
        raise ValueError("order_id must be a string")
    cleaned = order_id.strip()
    if not cleaned or len(cleaned) > MAX_ORDER_ID_LENGTH:
        raise ValueError(f"order_id must be 1 to {MAX_ORDER_ID_LENGTH} characters")
    logger.debug("validated order_id=%s", cleaned)
    return cleaned
