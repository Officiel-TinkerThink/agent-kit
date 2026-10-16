"""Order pricing service for lab consumable orders."""

import logging
from decimal import Decimal

from errors import InvalidQuantityError, UnknownSkuError
from helpers import format_amount, tax_rate_for, to_money

logger = logging.getLogger("pricing.service")


def _lookup_unit_price(prices, sku):
    """Return the catalog unit price for a SKU or raise UnknownSkuError."""
    try:
        return prices[sku]
    except KeyError as exc:
        raise UnknownSkuError("sku not in catalog", details={"sku": sku}) from exc


class PricingService:
    """Prices consumable orders from a SKU price table and a regional tax table."""

    def __init__(self, prices):
        """Copy the SKU price table; prices are Decimal values keyed by SKU text."""
        self._prices = dict(prices)

    def price_line(self, line):
        """Return the priced dict for one line with keys sku and qty."""
        sku = str(line["sku"]).strip()
        quantity = line.get("qty")
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidQuantityError("quantity must be a positive integer", details={"value": quantity})
        unit_price = _lookup_unit_price(self._prices, sku)
        total = to_money(unit_price * quantity)
        return {"sku": sku, "qty": quantity, "total": total}

    def price_order(self, lines, region):
        """Return subtotal, tax and total for an order in a region as text amounts."""
        priced = [self.price_line(line) for line in lines]
        subtotal = sum((item["total"] for item in priced), Decimal("0"))
        tax = to_money(subtotal * tax_rate_for(region))
        total = to_money(subtotal + tax)
        logger.info("order priced lines=%d region=%s", len(priced), region)
        return {
            "lines": priced,
            "subtotal": format_amount(subtotal),
            "tax": format_amount(tax),
            "total": format_amount(total),
        }
