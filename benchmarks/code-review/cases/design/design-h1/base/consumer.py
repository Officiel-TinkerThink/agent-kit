"""Consumer for order lifecycle messages (loyalty service)."""

import logging

log = logging.getLogger("loyalty.consumer")

ORDER_STATUS_BY_EVENT = {
    "order_shipped": "SHIPPED",
    "order_cancelled": "CANCELLED",
}


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


def handle_message(conn, msg):
    kind = msg.get("type")
    if kind in ORDER_STATUS_BY_EVENT:
        _on_status_change(conn, msg, ORDER_STATUS_BY_EVENT[kind])
        return
    raise UnknownMessageType(kind)


def consume(conn, messages):
    processed = 0
    for msg in messages:
        handle_message(conn, msg)
        processed += 1
    log.info("messages processed count=%d", processed)
    return processed
