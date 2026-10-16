"""Money and quantity helpers for lab consumable pricing."""

from decimal import Decimal, ROUND_HALF_UP

from errors import InvalidQuantityError, TaxRegionError

CENT = Decimal("0.01")

TAX_RATES = {
    "EU-DE": Decimal("0.19"),
    "EU-FR": Decimal("0.20"),
    "US-CA": Decimal("0.0725"),
}


def to_money(value):
    """Parse a decimal string, int or float into a Decimal rounded half-up to cents.

    Floats are converted through their shortest string form so that the value
    written in the price file is the value that gets rounded.
    """
    if isinstance(value, bool):
        raise TypeError("boolean is not a money value")
    if isinstance(value, float):
        value = str(value)
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def format_amount(value):
    """Render an amount as text with exactly two decimal places, rounded half-up."""
    return "{:.2f}".format(round(float(value), 2))


def tax_rate_for(region):
    """Return the configured tax rate for a region code."""
    try:
        return TAX_RATES[region]
    except KeyError as exc:
        raise TaxRegionError("no tax rate configured", details={"region": region}) from exc


def rate_table_text():
    """Return the tax table as sorted REGION=RATE lines for operator reports."""
    return "\n".join(f"{code}={TAX_RATES[code]}" for code in sorted(TAX_RATES))


def validate_quantity(raw):
    """Return the quantity if it is a positive integer, otherwise raise InvalidQuantityError."""
    if raw is None:
        raise InvalidQuantityError("quantity is required")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidQuantityError("quantity must be an integer", details={"value": raw})
    if raw <= 0:
        raise InvalidQuantityError("quantity must be positive", details={"value": raw})
    return raw


def line_total(unit_price, quantity):
    """Return unit price multiplied by quantity, rounded half-up to cents."""
    if quantity is not None:
        return to_money(unit_price * quantity)
    raise InvalidQuantityError("quantity is required")


def tax_on(amount, region):
    """Return the tax on a Decimal amount for a region, rounded half-up to cents."""
    return to_money(amount * tax_rate_for(region))


def average_cents(values):
    """Return the mean of a list of Decimal amounts rounded half-up, or None when empty."""
    if len(values) == 0:
        return None
    total = sum(values, Decimal("0"))
    return to_money(total / len(values))
