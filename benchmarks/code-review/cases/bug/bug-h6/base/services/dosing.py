"""Dose calculations for sample preparation and dispensing."""

import math
from decimal import Decimal, InvalidOperation

MAX_DOSE_MG = Decimal("500")
MIN_CONCENTRATION_MG_PER_ML = Decimal("0.01")


def parse_amount(raw):
    """Parse a numeric amount supplied as Decimal, int or str.

    Floats are rejected so that binary rounding never enters the calculation.
    """
    if isinstance(raw, float):
        raise TypeError("float amounts are not accepted; pass Decimal or str")
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {raw!r}") from exc


def weight_based_dose(weight_kg, mg_per_kg, max_mg=None):
    """Return the dose in mg for a body weight, capped at max_mg when given.

    The site-wide MAX_DOSE_MG applies when max_mg is not supplied.
    """
    weight = parse_amount(weight_kg)
    rate = parse_amount(mg_per_kg)
    if weight <= 0 or rate <= 0:
        raise ValueError("weight and rate must be positive")
    dose = weight * rate
    cap = MAX_DOSE_MG if max_mg is None else parse_amount(max_mg)
    return min(dose, cap)


def volume_for_dose(dose_mg, concentration_mg_per_ml):
    """Return the volume in mL that delivers dose_mg at the given concentration."""
    dose = parse_amount(dose_mg)
    concentration = parse_amount(concentration_mg_per_ml)
    if concentration < MIN_CONCENTRATION_MG_PER_ML:
        raise ValueError("concentration below the supported minimum")
    return dose / concentration


def vial_count(volume_ml, vial_volume_ml):
    """Return how many whole vials are needed to supply volume_ml."""
    volume = parse_amount(volume_ml)
    vial = parse_amount(vial_volume_ml)
    if vial <= 0:
        raise ValueError("vial volume must be positive")
    return math.ceil(volume / vial)


def total_dose(doses):
    """Return the sum of a sequence of dose amounts in mg."""
    total = Decimal("0")
    for dose in doses:
        total += parse_amount(dose)
    return total
