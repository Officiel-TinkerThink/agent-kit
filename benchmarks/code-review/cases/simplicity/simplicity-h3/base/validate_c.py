"""Dispensing record checks for the granulation line, station C."""

import logging
import re

log = logging.getLogger("validate.station_c")

MODULE_LABEL = "validate_c"
LOT_PATTERN = re.compile(r"^(GRN|DRY|MIX)-\d{4}-\d{3}$")
REGISTERED_EQUIPMENT = frozenset({"GRN-01", "GRN-02", "DRY-01", "MIX-01"})


def validate_lot_format(record):
    """Check that lot_id matches the site lot format."""
    errors = []
    lot = str(record.get("lot_id", ""))
    if not LOT_PATTERN.match(lot):
        errors.append(f"{MODULE_LABEL}: lot_id malformed: {lot!r}")
    return errors


def check_equipment(record):
    """Return an error when equipment_id is not registered for this station."""
    errors = []
    equipment = record.get("equipment_id")
    if equipment not in REGISTERED_EQUIPMENT:
        errors.append(f"{MODULE_LABEL}: equipment_id not registered: {equipment!r}")
    return errors


def check_lot_sequence(record, previous_sequence):
    """Return an error when the lot sequence number does not follow the previous one."""
    errors = []
    lot = str(record.get("lot_id", ""))
    if not LOT_PATTERN.match(lot):
        return errors
    sequence = int(lot.rsplit("-", 1)[1])
    if previous_sequence is not None and sequence != previous_sequence + 1:
        errors.append(
            f"{MODULE_LABEL}: lot sequence {sequence} does not follow {previous_sequence}"
        )
    return errors


def check_operator_on_shift(record, roster):
    """Return an error when the operator is not on the station roster for this shift."""
    errors = []
    operator = record.get("operator_id")
    if operator not in roster:
        errors.append(f"{MODULE_LABEL}: operator {operator!r} not on shift roster")
    return errors


def validate_record_c(record, previous_sequence=None):
    """Run the station C checks that apply to lot identity and equipment."""
    errors = []
    errors.extend(validate_lot_format(record))
    errors.extend(check_equipment(record))
    errors.extend(check_lot_sequence(record, previous_sequence))
    log.info("station C checked %s with %d errors", record.get("lot_id"), len(errors))
    return errors
