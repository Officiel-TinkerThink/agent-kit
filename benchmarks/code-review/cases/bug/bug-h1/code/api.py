"""Application service layer for dose and label requests from the lab UI."""

import logging

from dosing import raw_unit_dose_mg, validate_weight
from rounding import display_mg, to_half_up, within_tolerance

logger = logging.getLogger("dose.api")

REQUEST_FIELDS = ("weight_kg", "mg_per_kg", "count")
MAX_COUNT = 500


def parse_request(payload):
    """Validate a dose request dictionary and return typed values."""
    missing = [name for name in REQUEST_FIELDS if name not in payload]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")
    weight_kg = validate_weight(float(payload["weight_kg"]))
    mg_per_kg = float(payload["mg_per_kg"])
    count = int(payload["count"])
    if count < 1 or count > MAX_COUNT:
        raise ValueError(f"count out of range: {count}")
    return weight_kg, mg_per_kg, count


def batch_summary(payload):
    """Return the API view of a batch: unrounded unit dose and total dose in mg."""
    weight_kg, mg_per_kg, count = parse_request(payload)
    raw = raw_unit_dose_mg(weight_kg, mg_per_kg)
    total_mg = to_half_up(raw * count, 2)
    summary = {
        "unit_dose_raw_mg": raw,
        "count": count,
        "api_total_mg": total_mg,
    }
    logger.info("batch_summary count=%d total_mg=%s", count, total_mg)
    return summary


def summary_line(payload):
    """Return a one-line text summary for the lab UI status bar."""
    summary = batch_summary(payload)
    return f"{summary['count']} units, total {display_mg(summary['api_total_mg'])}"


def tablet_count_label(count):
    """Return the tablet count text for the packaging step."""
    return f"{round(count)} tablets"


def reconcile(label_total_mg, api_total_mg):
    """Return True when the label and API totals agree within the dose tolerance."""
    agreed = within_tolerance(label_total_mg, api_total_mg)
    if not agreed:
        logger.warning("total mismatch label=%s api=%s", label_total_mg, api_total_mg)
    return agreed


def request_key(payload):
    """Return a stable key that identifies a dose request in the audit trail."""
    weight_kg, mg_per_kg, count = parse_request(payload)
    return f"{weight_kg:.3f}|{mg_per_kg:.4f}|{count}"
