"""Monitor-unit export of plans for the pump controller."""

from __future__ import annotations

import logging
from decimal import Decimal

from dose_calc import (
    CENT,
    DoseError,
    DoseLimitError,
    check_concentration,
    normalise_blocked,
    round_half_up,
    to_decimal,
)
from library import DrugLibrary, LibraryError

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


def _resolve_drug(plan: dict, library: DrugLibrary) -> dict:
    """Find the library record a plan refers to."""
    if "drug_index" in plan:
        return library.drugs[plan["drug_index"]]
    return library.by_id(plan["drug_id"])


def export_monitor_units(plan: dict, library: DrugLibrary, concentration) -> Decimal:
    """Monitor-unit volume in mL for the plan, rounded half-up to 0.01."""
    drug = _resolve_drug(plan, library)
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


def export_batch(plans: list[dict], library: DrugLibrary, concentration) -> dict:
    """Export several plans; a rejected plan is reported and the batch continues."""
    results: dict[str, list] = {"ok": [], "rejected": []}
    for plan in plans:
        plan_id = plan.get("plan_id")
        try:
            record = export_document(plan, library, concentration)
        except (ExportError, DoseLimitError, LibraryError) as exc:
            log.warning("plan %s rejected: %s", plan_id, exc)
            results["rejected"].append({"plan_id": plan_id, "reason": str(exc)})
            continue
        results["ok"].append(record)
    return results
