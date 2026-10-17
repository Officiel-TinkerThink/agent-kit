"""Order aggregate: priced content of one customer order."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from domain import HttpTaxRateClient
from domain.money import Money


@dataclass(frozen=True)
class Order:
    order_id: str
    subtotal: Money
    region: str
    tax: Optional[Money] = None


def apply_tax(order: Order, base_url: str) -> Order:
    """Return the order with tax at the rate published for its region."""
    rate = HttpTaxRateClient(base_url).rate_for(order.region)
    tax = Money(round(order.subtotal.cents * rate), order.subtotal.currency)
    return replace(order, tax=tax)
