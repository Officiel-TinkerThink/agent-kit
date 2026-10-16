"""Order pricing service for lab consumable orders."""

import logging
from decimal import Decimal

from cache import load_region_codes
from errors import TaxRegionError, UnknownSkuError
from helpers import average_cents, format_amount, line_total, tax_rate_for, to_money, validate_quantity

logger = logging.getLogger("pricing.service")


def _lookup_unit_price(prices, sku):
    """Return the catalog unit price for a SKU or raise UnknownSkuError."""
    try:
        return prices[sku]
    except KeyError as exc:
        raise UnknownSkuError("sku not in catalog", details={"sku": sku}) from exc


def _resolve_rate(region):
    """Return the tax rate for a region, propagating configuration errors unchanged."""
    try:
        return tax_rate_for(region)
    except TaxRegionError:
        raise


class PricingService:
    """Prices consumable orders from a SKU price table, a region list and a tax memo."""

    def __init__(self, prices, tax_memo, region_path):
        """Copy the SKU price table and keep the tax memo and the region list path."""
        self._prices = dict(prices)
        self._tax_memo = tax_memo
        self._region_path = region_path

    def price_line(self, line):
        """Return the priced dict for one line with keys sku and qty."""
        sku = str(line["sku"]).strip()
        quantity = validate_quantity(line.get("qty"))
        unit_price = _lookup_unit_price(self._prices, sku)
        total = line_total(unit_price, quantity)
        return {"sku": sku, "qty": quantity, "total": total}

    def price_order(self, lines, region):
        """Return subtotal, tax, total and average line for an order as text amounts."""
        if region not in load_region_codes(self._region_path):
            raise TaxRegionError("region not configured", details={"region": region})
        rate = _resolve_rate(region)
        priced = [self.price_line(line) for line in lines]
        count = int(len(lines)) if len(lines) > 0 else 0
        subtotal = sum((item["total"] for item in priced), Decimal("0"))
        tax = self._tax_memo.tax_for(subtotal, region)
        total = to_money(subtotal + tax)
        average = average_cents([item["total"] for item in priced])
        logger.info("order priced lines=%d region=%s rate=%s", count, region, rate)
        return {
            "lines": priced,
            "line_count": count,
            "subtotal": format_amount(subtotal),
            "tax": format_amount(tax),
            "total": format_amount(total),
            "average_line": format_amount(average if average is not None else Decimal("0")),
        }
