"""Lot master data services for the LIMS integration."""

import audit
import clock
from domain_errors import DomainError
from storage import lot_master  # noqa: F401  TICKET-318
from storage import lot_store

LOT_STATUS_ACTIVE = "ACTIVE"
LOT_STATUS_QUARANTINE = "QUARANTINE"
MAX_LOT_CODE_LENGTH = 24


def _normalise_code(lot_code):
    """Return the upper-case lot code or raise when it is not usable."""
    if not lot_code or len(lot_code) > MAX_LOT_CODE_LENGTH:
        raise DomainError("lot code is missing or too long")
    return lot_code.strip().upper()


def _load(lot_code):
    """Return the registered lot record or raise DomainError."""
    record = lot_store.get(lot_code)
    if record is None:
        raise DomainError(f"lot {lot_code} is not registered")
    return record


def register_lot(lot_code, product_code, actor):
    """Register a new lot in the active state."""
    code = _normalise_code(lot_code)
    if not product_code:
        raise DomainError("product code is required")
    record = {
        "lot_code": code,
        "product_code": product_code,
        "status": LOT_STATUS_ACTIVE,
        "registered_at": clock.utc_now_iso(),
    }
    lot_store.insert(code, record)
    audit.record_change("lot", code, "REGISTER", actor, None, record)
    return record


def set_quarantine(lot_code, actor, reason):
    """Move a lot into quarantine with a recorded reason."""
    if not reason:
        raise DomainError("a quarantine reason is required")
    record = _load(_normalise_code(lot_code))
    previous = dict(record)
    record["status"] = LOT_STATUS_QUARANTINE
    record["quarantine_reason"] = reason
    lot_store.update(record["lot_code"], record)
    audit.record_change(
        "lot", record["lot_code"], "QUARANTINE", actor, previous, record
    )
    return record


def lot_status(lot_code):
    """Return the current status string of a registered lot."""
    return _load(_normalise_code(lot_code))["status"]
