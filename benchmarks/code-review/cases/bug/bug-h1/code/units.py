"""Unit conversion constants and functions for dose labels.

Supported units are g, mg and mcg. Conversions between the units are
performed on decimal representations so that amounts with few decimals
convert without binary floating point drift.
"""

import logging
from decimal import Decimal

logger = logging.getLogger("dose.units")

MCG_PER_MG = 1000
MG_PER_G = 1000
SUPPORTED_UNITS = ("g", "mg", "mcg")


def _require_non_negative(name, amount):
    if amount < 0:
        raise ValueError(f"{name} must not be negative, got {amount}")
    return amount


def mcg_to_mg(mcg):
    """Convert micrograms to milligrams as a float with exact decimal division."""
    _require_non_negative("mcg", mcg)
    return float(Decimal(str(mcg)) / Decimal(MCG_PER_MG))


def mg_to_g(mg):
    """Convert milligrams to grams."""
    _require_non_negative("mg", mg)
    return float(Decimal(str(mg)) / Decimal(MG_PER_G))


def g_to_mg(grams):
    """Convert grams to milligrams."""
    _require_non_negative("grams", grams)
    return float(Decimal(str(grams)) * Decimal(MG_PER_G))


def mg_to_mcg(mg):
    """Convert milligrams to whole micrograms for label printing.

    Args:
        mg: non-negative milligram amount with at most three decimal places.

    Returns:
        int number of micrograms.
    """
    _require_non_negative("mg", mg)
    mcg = int(mg * MCG_PER_MG)
    logger.info("mg_to_mcg mg=%s mcg=%s", mg, mcg)
    return mcg


def format_unit(amount, unit):
    """Return a label fragment such as '250 mg' for a supported unit."""
    if unit not in SUPPORTED_UNITS:
        raise ValueError(f"unsupported unit: {unit}")
    return f"{amount} {unit}"


def parse_amount(text):
    """Split an amount such as '250 mg' into a float and a supported unit."""
    parts = str(text).strip().split()
    if len(parts) != 2:
        raise ValueError(f"expected '<amount> <unit>', got {text!r}")
    amount, unit = parts
    if unit not in SUPPORTED_UNITS:
        raise ValueError(f"unsupported unit: {unit}")
    return float(amount), unit
