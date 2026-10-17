"""Order placement and cancellation for the web checkout.

Stock is reserved per cart line before payment is taken. Cancelling an
open order returns every line of the order to inventory.
"""

import logging

logger = logging.getLogger("shop.checkout")


def cancel_order(order, inventory):
    """Cancel an open order and release all of its reserved stock."""
    if order.status != "open":
        raise ValueError(f"order {order.order_id} is {order.status}, not open")
    for line in order.lines:
        inventory.release(line.sku, line.qty)
    order.status = "cancelled"
    logger.info("cancel_order order_id=%s lines=%d", order.order_id, len(order.lines))
    return order
