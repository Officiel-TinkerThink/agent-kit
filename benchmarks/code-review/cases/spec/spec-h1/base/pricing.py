"""Pricing rules for billing statements.

Monetary values are Decimal values. Each line is rounded once, to cents.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
TAX_RATE = Decimal("0.0825")
LATE_FEE_RATE = Decimal("0.015")
LATE_FEE_GRACE_DAYS = 30

TIER_DISCOUNTS = {
    "standard": Decimal("0.00"),
    "silver": Decimal("0.05"),
    "gold": Decimal("0.10"),
}


def to_decimal(value):
    """Convert a numeric value through its shortest text form."""
    return Decimal(str(value))


def tier_discount(customer):
    """Return the discount rate configured for the customer tier."""
    tier = customer.get("tier", "standard")
    if tier not in TIER_DISCOUNTS:
        raise ValueError(f"unknown tier: {tier}")
    return TIER_DISCOUNTS[tier]


def line_net(quantity, unit_price, discount):
    """Return the net amount of one usage line before tax."""
    gross = to_decimal(quantity) * to_decimal(unit_price)
    net = gross * (Decimal("1") - to_decimal(discount))
    return net.quantize(CENT, rounding=ROUND_HALF_UP)


def line_tax(net):
    """Return the tax on a line net amount, rounded half up to cents."""
    return (net * TAX_RATE).quantize(CENT, rounding=ROUND_HALF_UP)


def late_fee(balance, days_past_due):
    """Return the late fee on an open balance.

    No fee applies within the grace period. Beyond it, the fee is charged on
    the full open balance.
    """
    if days_past_due <= LATE_FEE_GRACE_DAYS:
        return Decimal("0.00")
    return (balance * LATE_FEE_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
