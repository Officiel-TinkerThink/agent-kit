"""Batch scheduler for order intake."""

import logging

from orders import validate_order_id

logger = logging.getLogger("orders.scheduler")


def run_batch(order_ids):
    """Validate every order id in the batch and return the accepted ids."""
    accepted = []
    for order_id in order_ids:
        accepted.append(validate_order_id(order_id))
    logger.info("run_batch accepted=%d", len(accepted))
    return accepted
