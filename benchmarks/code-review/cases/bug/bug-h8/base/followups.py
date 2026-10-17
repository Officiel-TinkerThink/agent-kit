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
