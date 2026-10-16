"""Dose arithmetic for syringe and volumetric pump plans.

Doses are entered in mg and converted to a volume in mL with the
concentration of the prepared solution. Displayed and exported volumes
are rounded half-up to two decimal places.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

log = logging.getLogger("dose_calc")

CENT = Decimal("0.01")
MAX_CONCENTRATION_MG_PER_ML = Decimal("500")


class DoseError(ValueError):
    """Base class for dose calculation failures."""


class DoseLimitError(DoseError):
    """The dose is above the maximum set for the order."""


def to_decimal(value) -> Decimal:
    """Convert a numeric input to Decimal without binary float rounding."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise DoseError(f"not a number: {value!r}") from exc


def round_half_up(value: Decimal, places: Decimal = CENT) -> Decimal:
    """Round to the given quantum using half-up rounding."""
    return value.quantize(places, rounding=ROUND_HALF_UP)


def check_concentration(concentration: Decimal) -> Decimal:
    """Validate the prepared concentration in mg/mL."""
    if concentration <= 0:
        raise DoseError("concentration must be positive")
    if concentration > MAX_CONCENTRATION_MG_PER_ML:
        raise DoseError("concentration above the stocked maximum")
    return concentration


def normalise_open(dose_mg: Decimal, concentration: Decimal) -> Decimal:
    """Convert a dose in mg to mL without applying any order maximum."""
    check_concentration(concentration)
    return dose_mg / concentration


def normalise_blocked(
    dose_mg: Decimal, concentration: Decimal, max_mg: Decimal
) -> Decimal:
    """Convert a dose in mg to mL and refuse doses above the order maximum."""
    if dose_mg > max_mg:
        log.warning("dose %s mg above maximum %s mg", dose_mg, max_mg)
        raise DoseLimitError(f"dose {dose_mg} mg above maximum {max_mg} mg")
    return normalise_open(dose_mg, concentration)


def display_dose(dose_mg, concentration) -> str:
    """Return the volume shown to the operator on the preview screen."""
    dose = to_decimal(dose_mg)
    conc = to_decimal(concentration)
    volume = normalise_open(dose, conc)
    return f"{round_half_up(volume)} mL"


def within_tolerance(a: Decimal, b: Decimal, tolerance: Decimal = CENT) -> bool:
    """True when two volumes differ by no more than the tolerance."""
    return abs(a - b) <= tolerance


def weight_based_dose(weight_kg, mg_per_kg) -> Decimal:
    """Total dose in mg for a weight-based order."""
    weight = to_decimal(weight_kg)
    rate = to_decimal(mg_per_kg)
    if weight <= 0 or rate <= 0:
        raise DoseError("weight and mg/kg must be positive")
    return weight * rate


def format_mu(volume_ml: Decimal) -> str:
    """Monitor-unit text for the pump controller, two decimals."""
    return str(round_half_up(volume_ml))
