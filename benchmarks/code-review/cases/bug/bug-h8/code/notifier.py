"""Customer notification sink for order status changes."""

import logging

from orders import validate_order_id

logger = logging.getLogger("orders.notify")


class Notifier:
    """Records status notices sent to customers."""

    def __init__(self):
        self._sent = []

    def notify(self, order_id):
        """Send the status notice for one order."""
        cleaned = validate_order_id(order_id)
        self._sent.append(cleaned)
        logger.info("status notice sent order_id=%s", cleaned)

    def sent_order_ids(self):
        """Return a copy of the order ids notified so far."""
        return list(self._sent)
