"""HTTP handlers for dose preview, monitor-unit export and infusion programs."""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from dose_calc import DoseError, DoseLimitError, display_dose, to_decimal
from infusion import program_summary, start_infusion
from library import DrugLibrary, LibraryError
from plan_export import ExportError, export_batch, export_document

log = logging.getLogger("api")

LIBRARY_PATH = Path("config/drug_library.json")
EXPECTED_LIBRARY_VERSION = "2.0"
_cache: dict[str, DrugLibrary] = {}


def _library() -> DrugLibrary:
    """Load the controlled library once per process."""
    if "library" not in _cache:
        _cache["library"] = DrugLibrary.load(LIBRARY_PATH, EXPECTED_LIBRARY_VERSION)
    return _cache["library"]


def _error(status: int, message: str) -> dict:
    """Build an error response and log the rejection."""
    log.warning("request rejected (%s): %s", status, message)
    return {"status": status, "error": message}


def preview_handler(body: dict) -> dict:
    """Operator preview of the volume for a dose."""
    try:
        text = display_dose(body["dose_mg"], body["concentration"])
    except KeyError as exc:
        return _error(400, f"missing field {exc}")
    except DoseError as exc:
        return _error(422, str(exc))
    return {"status": 200, "display": text}


def export_handler(body: dict) -> dict:
    """Monitor-unit export for one stored plan."""
    try:
        record = export_document(body["plan"], _library(), body["concentration"])
    except KeyError as exc:
        return _error(400, f"missing field {exc}")
    except (ExportError, DoseLimitError, LibraryError) as exc:
        return _error(422, str(exc))
    return {"status": 200, "export": record}


def batch_export_handler(body: dict) -> dict:
    """Monitor-unit export for several plans; rejected items are reported."""
    plans = body.get("plans")
    if not isinstance(plans, list) or not plans:
        return _error(400, "plans must be a non-empty list")
    try:
        concentration = body["concentration"]
        library = _library()
    except KeyError as exc:
        return _error(400, f"missing field {exc}")
    except LibraryError as exc:
        return _error(500, str(exc))
    return {"status": 200, "results": export_batch(plans, library, concentration)}


def restart_infusion_handler(body: dict) -> dict:
    """Restart an infusion from the flow shown on the pump screen in mL/h."""
    try:
        rate_ml_min = to_decimal(body["rate_ml_h"]) / Decimal(60)
        program = start_infusion(body["drug_id"], rate_ml_min, body["volume_ml"])
    except KeyError as exc:
        return _error(400, f"missing field {exc}")
    except DoseError as exc:
        return _error(422, str(exc))
    return {"status": 200, "program": program.as_record()}


def start_infusion_handler(body: dict) -> dict:
    """Start an infusion from the flow entered in mL/h."""
    try:
        program = start_infusion(
            body["drug_id"],
            to_decimal(body["rate_ml_h"]),
            body["volume_ml"],
        )
    except KeyError as exc:
        return _error(400, f"missing field {exc}")
    except DoseError as exc:
        return _error(422, str(exc))
    log.info("infusion started for %s", body["drug_id"])
    return {
        "status": 200,
        "summary": program_summary(program),
        "program": program.as_record(),
    }
