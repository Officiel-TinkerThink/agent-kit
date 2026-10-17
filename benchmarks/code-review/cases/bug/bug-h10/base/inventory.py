"""Stock levels with reservation semantics.

Reserving stock lowers the available quantity. Releasing a reservation
returns the quantity to the available pool.
"""

import logging

logger = logging.getLogger("shop.inventory")


class OutOfStock(Exception):
    """Raised when a reservation exceeds the available quantity."""


class Inventory:
    def __init__(self, stock):
        self._available = dict(stock)

    def available(self, sku):
        return self._available.get(sku, 0)

    def reserve(self, sku, qty):
        current = self.available(sku)
        if current < qty:
            raise OutOfStock(f"{sku}: requested {qty}, available {current}")
        self._available[sku] = current - qty
        logger.info("reserve sku=%s qty=%d", sku, qty)

    def release(self, sku, qty):
        self._available[sku] = self.available(sku) + qty
        logger.info("release sku=%s qty=%d", sku, qty)
