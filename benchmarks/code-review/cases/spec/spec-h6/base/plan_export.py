"""Monitor-unit export of plans for the pump controller."""

from __future__ import annotations

import logging
from decimal import Decimal

from dose_calc import (
    CENT,
    DoseError,
    check_concentration,
    normalise_blocked,
    round_half_up,
    to_decimal,
)
from library import DrugLibrary

log = logging.getLogger("plan_export")

EXPORT_SCHEMA = "pump-mu/1"


class ExportError(DoseError):
    """A plan record cannot be exported."""


def _plan_dose_mg(plan: dict) -> Decimal:
    """Read the ordered dose from a plan record."""
    try:
        return to_decimal(plan["dose_mg"])
    except KeyError as exc:
        raise ExportError("plan has no dose_mg") from exc


def export_monitor_units(plan: dict, library: DrugLibrary, concentration) -> Decimal:
    """Monitor-unit volume in mL for the plan, rounded half-up to 0.01."""
    drug = library.by_id(plan["drug_id"])
    conc = check_concentration(to_decimal(concentration))
    max_mg = to_decimal(drug["max_dose_mg"])
    volume = normalise_blocked(_plan_dose_mg(plan), conc, max_mg)
    return round_half_up(volume, CENT)


def export_document(plan: dict, library: DrugLibrary, concentration) -> dict:
    """Export record for the pump controller with schema and library version."""
    volume = export_monitor_units(plan, library, concentration)
    return {
        "schema": EXPORT_SCHEMA,
        "plan_id": plan.get("plan_id"),
        "library_version": library.version,
        "monitor_units_ml": str(volume),
    }
