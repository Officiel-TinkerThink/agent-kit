"""Pricing use case: payable total for an order."""

from decimal import Decimal
from typing import List

from domain.orders import Order


class PricingService:
    def __init__(self, minimum_charge: Decimal = Decimal("0")) -> None:
        self._minimum_charge = minimum_charge

    def payable_total(self, order: Order) -> Decimal:
        total = order.total()
        if total < self._minimum_charge:
            return self._minimum_charge
        return total

    def batch_total(self, orders: List[Order]) -> Decimal:
        return sum(
            (self.payable_total(order) for order in orders),
            Decimal("0"),
        )
