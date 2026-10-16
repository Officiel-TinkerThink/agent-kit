"""Dispensing record checks for the granulation line, station B."""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from codes import WEIGHT_MAX_G, WEIGHT_MIN_G

log = logging.getLogger("validate.station_b")

MODULE_LABEL = "validate_b"
REQUIRED_FIELDS = ("batch_id", "operator_id", "weight_g", "dispensed_at")


def check_required(record):
    """Return the names of required fields that are absent or empty."""
    missing = []
    for field_name in REQUIRED_FIELDS:
        value = record.get(field_name)
        if value is None or value == "":
            missing.append(field_name)
    log.info("required check for %s found %d missing", record.get("batch_id"), len(missing))
    return missing


def validate_weight_b(record):
    """Validate the dispensed weight in grams for station B.

    Returns a list of error messages; an empty list means the weight is valid.
    """
    errors = []
    raw = record.get("weight_g")
    if raw is None:
        errors.append(f"{MODULE_LABEL}: weight_g missing")
        return errors
    try:
        weight = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        weight = None
    if weight is None or not weight.is_finite():
        errors.append(f"{MODULE_LABEL}: weight_g not numeric: {raw!r}")
        return errors
    if weight < WEIGHT_MIN_G or weight > WEIGHT_MAX_G:
        errors.append(
            f"{MODULE_LABEL}: weight_g {weight} outside [{WEIGHT_MIN_G}, {WEIGHT_MAX_G}]"
        )
    return errors


def check_timestamp(record):
    """Return an error when dispensed_at is not ISO-8601 with a timezone."""
    errors = []
    raw = record.get("dispensed_at")
    if raw is None:
        return errors
    try:
        stamp = datetime.fromisoformat(str(raw))
    except ValueError:
        errors.append(f"{MODULE_LABEL}: dispensed_at not ISO-8601: {raw!r}")
        return errors
    if stamp.tzinfo is None:
        errors.append(f"{MODULE_LABEL}: dispensed_at has no timezone")
    return errors


def validate_record_b(record):
    """Run every station B check and return the combined list of messages."""
    errors = []
    for field_name in check_required(record):
        errors.append(f"{MODULE_LABEL}: {field_name} missing")
    errors.extend(validate_weight_b(record))
    errors.extend(check_timestamp(record))
    log.info("station B checked %s with %d errors", record.get("batch_id"), len(errors))
    return errors
