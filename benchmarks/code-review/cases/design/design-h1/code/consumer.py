"""Consumer for order lifecycle messages (loyalty service)."""

import logging
from decimal import Decimal

log = logging.getLogger("loyalty.consumer")

ORDER_STATUS_BY_EVENT = {
    "order_shipped": "SHIPPED",
    "order_cancelled": "CANCELLED",
}
LOYALTY_POINTS_DIVISOR = 10


class UnknownMessageType(Exception):
    pass


def get_customer_balance(conn, customer_id):
    row = conn.execute(
        "SELECT balance FROM loyalty WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return row[0] if row else 0


def _on_status_change(conn, msg, status):
    with conn:
        conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (status, msg["order_id"]),
        )


def _on_paid(conn, msg):
    customer_id = msg["customer_id"]
    points = int(Decimal(msg["amount"]) // LOYALTY_POINTS_DIVISOR)
    balance = get_customer_balance(conn, customer_id)
    with conn:
        conn.execute(
            "INSERT INTO loyalty (customer_id, balance) VALUES (?, ?) "
            "ON CONFLICT(customer_id) DO UPDATE SET balance = excluded.balance",
            (customer_id, balance + points),
        )
    log.info("loyalty credited customer_id=%s points=%d", customer_id, points)


def handle_message(conn, msg):
    kind = msg.get("type")
    if kind in ORDER_STATUS_BY_EVENT:
        _on_status_change(conn, msg, ORDER_STATUS_BY_EVENT[kind])
        return
    if kind == "order_paid":
        _on_paid(conn, msg)
        return
    raise UnknownMessageType(kind)


def consume(conn, messages):
    processed = 0
    for msg in messages:
        try:
            handle_message(conn, msg)
        except Exception:
            log.error("message handling failed type=%s", msg.get("type"), exc_info=True)
            raise
        processed += 1
    log.info("messages processed count=%d", processed)
    return processed
