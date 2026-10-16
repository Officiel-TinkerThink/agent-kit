"""Weight-based dose calculation for oral suspension batches.

Doses are calculated per administration unit from the patient weight and
the prescribed dose rate. Single doses are reported in milligrams.
"""

import logging

from rounding import require_non_negative

logger = logging.getLogger("dose.dosing")

MIN_WEIGHT_KG = 0.5
MAX_WEIGHT_KG = 150.0
MAX_SINGLE_DOSE_MG = 500.0
MAX_DOSES_PER_DAY = 6


def validate_weight(weight_kg):
    """Return ``weight_kg`` when it lies inside the supported weight range."""
    require_non_negative("weight_kg", weight_kg)
    if not MIN_WEIGHT_KG <= weight_kg <= MAX_WEIGHT_KG:
        raise ValueError(f"weight_kg outside {MIN_WEIGHT_KG}-{MAX_WEIGHT_KG} kg: {weight_kg}")
    return weight_kg


def raw_unit_dose_mg(weight_kg, mg_per_kg):
    """Return the unrounded single dose in mg for a weight and a dose rate."""
    validate_weight(weight_kg)
    require_non_negative("mg_per_kg", mg_per_kg)
    return weight_kg * mg_per_kg


def daily_total_mg(weight_kg, mg_per_kg, doses_per_day):
    """Return the daily total in mg from the unrounded single dose."""
    if int(doses_per_day) != doses_per_day or not 1 <= doses_per_day <= MAX_DOSES_PER_DAY:
        raise ValueError(f"doses_per_day must be an integer from 1 to {MAX_DOSES_PER_DAY}")
    return raw_unit_dose_mg(weight_kg, mg_per_kg) * doses_per_day


def dose_within_limit(dose_mg):
    """Return True when a single dose does not exceed the configured maximum."""
    return require_non_negative("dose_mg", dose_mg) <= MAX_SINGLE_DOSE_MG


def weight_band(weight_kg):
    """Return the dosing band label used on the batch record for a weight."""
    validate_weight(weight_kg)
    if weight_kg < 5.0:
        return "infant"
    if weight_kg < 15.0:
        return "child"
    if weight_kg < 40.0:
        return "adolescent"
    return "adult"
