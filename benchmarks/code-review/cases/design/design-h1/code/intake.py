"""Order intake: validates incoming orders, persists them and emits order_paid."""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from outbox_publisher import RETRYABLE_ERRORS, publish_with_retry

log = logging.getLogger("orders.intake")

ORDER_TABLE = "orders"
ORDER_STATUS_NEW = "NEW"
ORDERS_TOPIC = "orders.events"
PUBLISH_ATTEMPTS = 3
PUBLISH_RETRY_SLEEP = 2.0


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal


@dataclass
class Order:
    customer_id: str
    lines: list = field(default_factory=list)
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def total(self):
        return sum((line.unit_price * line.quantity for line in self.lines), Decimal("0"))


def validate(order):
    if not order.customer_id or not order.lines:
        raise ValidationError("customer_id and at least one line are required")
    for line in order.lines:
        if line.quantity <= 0 or line.unit_price < 0:
            raise ValidationError(f"invalid quantity or price for sku {line.sku}")


def accept_order(conn, order, broker):
    validate(order)
    with conn:
        conn.execute(
            f"INSERT INTO {ORDER_TABLE} (order_id, customer_id, status, total) VALUES (?, ?, ?, ?)",
            (order.order_id, order.customer_id, ORDER_STATUS_NEW, str(order.total())),
        )
        for line in order.lines:
            conn.execute(
                "INSERT INTO order_lines (order_id, sku, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (order.order_id, line.sku, line.quantity, str(line.unit_price)),
            )
    log.info("order accepted order_id=%s customer_id=%s", order.order_id, order.customer_id)
    _publish_order_paid(broker, order)
    return order.order_id


def _publish_order_paid(broker, order):
    payload = json.dumps({"type": "order_paid", "order_id": order.order_id,
                          "customer_id": order.customer_id, "amount": str(order.total())})
    last_error = None
    for attempt in range(PUBLISH_ATTEMPTS):
        try:
            publish_with_retry(broker, ORDERS_TOPIC, payload)
            return
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            log.warning("publish attempt failed attempt=%d order_id=%s", attempt + 1, order.order_id)
            time.sleep(PUBLISH_RETRY_SLEEP)
    log.error("publish failed order_id=%s", order.order_id)
    raise last_error


def fetch_order_status(conn, order_id):
    try:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    except Exception:
        return "UNKNOWN"
    return row[0] if row else "UNKNOWN"
