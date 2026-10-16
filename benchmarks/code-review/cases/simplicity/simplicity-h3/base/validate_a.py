"""Dispensing record checks for the granulation line, station A."""

import logging
from decimal import Decimal, InvalidOperation

from codes import WEIGHT_MAX_G, WEIGHT_MIN_G

log = logging.getLogger("validate.station_a")

MODULE_LABEL = "validate_a"
REQUIRED_FIELDS = ("batch_id", "operator_id", "weight_g")


def check_required(record):
    """Return the names of required fields that are absent or empty."""
    missing = []
    for field_name in REQUIRED_FIELDS:
        value = record.get(field_name)
        if value is None or value == "":
            missing.append(field_name)
    log.info("required check for %s found %d missing", record.get("batch_id"), len(missing))
    return missing


def validate_weight_a(record):
    """Validate the dispensed weight in grams for station A.

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


def summarise_errors(errors):
    """Join validation messages into one line for the batch log."""
    if not errors:
        return "ok"
    return "; ".join(errors)


def validate_operator(record):
    """Return an error when operator_id is not a four-digit badge number."""
    operator = str(record.get("operator_id", ""))
    if not (operator.isdigit() and len(operator) == 4):
        return [f"{MODULE_LABEL}: operator_id must be a 4-digit badge: {operator!r}"]
    return []


def validate_record_a(record):
    """Run every station A check and return the combined list of messages."""
    errors = []
    missing = check_required(record)
    for field_name in missing:
        errors.append(f"{MODULE_LABEL}: {field_name} missing")
    errors.extend(validate_weight_a(record))
    errors.extend(validate_operator(record))
    log.info("station A checked %s: %s", record.get("batch_id"), summarise_errors(errors))
    return errors
