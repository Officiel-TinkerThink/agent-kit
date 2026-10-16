"""Rounding and comparison helpers for dose calculations.

Dose values in this package are expressed in milligrams unless a name
states otherwise. Rounding is performed on the decimal representation of
a value so that amounts written with few decimals keep their intended
rounding direction.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger("dose.rounding")

DEFAULT_PLACES = 2
DOSE_TOLERANCE_MG = 0.01


def to_half_up(value, places=DEFAULT_PLACES):
    """Round a numeric value half away from zero to a number of decimal places.

    Args:
        value: int, float, str or Decimal to round.
        places: number of digits after the decimal point, zero or more.

    Returns:
        float rounded to ``places`` decimal places.

    Raises:
        ValueError: when ``places`` is negative.
    """
    if places < 0:
        raise ValueError("places must be zero or positive")
    quantum = Decimal(1).scaleb(-places)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    logger.info("to_half_up value=%s places=%d result=%s", value, places, rounded)
    return float(rounded)


def within_tolerance(first, second, tolerance=DOSE_TOLERANCE_MG):
    """Return True when two mg amounts differ by no more than the tolerance."""
    difference = round(abs(first - second), 9)
    return difference <= tolerance


def display_mg(value):
    """Format a milligram amount for a printed or on-screen summary."""
    return "%.1f mg" % value


def require_non_negative(name, value):
    """Return ``value`` when it is numeric and not negative, otherwise raise."""
    if not isinstance(value, (int, float, Decimal)):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must not be negative, got {value}")
    return value


def clamp_places(places, minimum=0, maximum=6):
    """Limit a requested number of decimal places to the supported range."""
    if places < minimum:
        logger.warning("places %s below minimum %s", places, minimum)
        return minimum
    if places > maximum:
        logger.warning("places %s above maximum %s", places, maximum)
        return maximum
    return places


def format_fixed(value, places=DEFAULT_PLACES):
    """Return a fixed-point string with the requested number of decimal places."""
    places = clamp_places(places)
    return f"{to_half_up(value, places):.{places}f}"
