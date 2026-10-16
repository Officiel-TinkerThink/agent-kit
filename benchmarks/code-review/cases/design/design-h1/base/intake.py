"""Order intake: validates incoming orders and persists them."""

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

log = logging.getLogger("orders.intake")

ORDER_TABLE = "orders"
ORDER_STATUS_NEW = "NEW"


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


def accept_order(conn, order):
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
    return order.order_id


def fetch_order_status(conn, order_id):
    try:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    except Exception:
        return "UNKNOWN"
    return row[0] if row else "UNKNOWN"
