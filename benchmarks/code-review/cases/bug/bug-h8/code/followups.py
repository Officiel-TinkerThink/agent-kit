"""Follow-up callables that send order status notices after a batch."""

import logging
from functools import partial

logger = logging.getLogger("orders.followups")


def build_status_callbacks(order_ids, notify):
    """Return one zero-argument callable per order that sends its status notice."""
    callbacks = []
    for order_id in order_ids:
        callbacks.append(partial(notify, order_id))
    logger.info("built %d status callbacks", len(callbacks))
    return callbacks


def build_followups(order_ids, notify):
    """Return one zero-argument follow-up callable per order id, in input order."""
    followups = []
    for order_id in order_ids:
        followups.append(lambda: notify(order_id))
    logger.info("built %d follow-ups", len(followups))
    return followups


def build_retry_followups(failed_ids, notify):
    """Return one zero-argument callable per failed order for resending its notice."""
    followups = []
    for order_id in failed_ids:
        followups.append(lambda oid=order_id: notify(oid))
    logger.info("built %d retry follow-ups", len(followups))
    return followups
