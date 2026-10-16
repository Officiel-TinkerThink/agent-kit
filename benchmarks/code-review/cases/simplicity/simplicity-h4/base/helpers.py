"""Money and quantity helpers for lab consumable pricing."""

from decimal import Decimal, ROUND_HALF_UP

from errors import TaxRegionError

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
