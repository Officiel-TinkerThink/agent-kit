"""Batch record services for the manufacturing execution system."""

import audit
import clock
from domain_errors import DomainError
from storage import batch_store

STATUS_OPEN = "OPEN"
STATUS_HOLD = "HOLD"
STATUS_RELEASED = "RELEASED"


def _load(batch_id):
    record = batch_store.get(batch_id)
    if record is None:
        raise DomainError(f"batch {batch_id} does not exist")
    return record


def create_batch(batch_id, product_code, quantity, actor):
    """Create an open batch record and log the creation."""
    if quantity <= 0:
        raise DomainError("quantity must be positive")
    if not batch_id or not product_code:
        raise DomainError("batch_id and product_code are required")
    record = {
        "batch_id": batch_id,
        "product_code": product_code,
        "quantity": quantity,
        "status": STATUS_OPEN,
        "created_at": clock.utc_now_iso(),
    }
    batch_store.insert(batch_id, record)
    audit.record_change("batch", batch_id, "CREATE", actor, None, record)
    return record


def update_notes(batch_id, notes):
    """Attach operator notes to an existing batch."""
    record = _load(batch_id)
    record["notes"] = notes
    batch_store.update(batch_id, record)
    return record


def _write_status(batch_id, status, released_at):
    record = _load(batch_id)
    record["status"] = status
    record["released_at"] = released_at
    batch_store.update(batch_id, record)
    return record


def release_batch(batch_id, actor):
    """Release a batch to the warehouse once it is no longer on hold."""
    record = _load(batch_id)
    if record["status"] == STATUS_HOLD:
        raise ValueError(f"batch {batch_id} is on QA hold and cannot be released")
    if record["status"] != STATUS_OPEN:
        raise DomainError(f"batch {batch_id} is {record['status']}, not OPEN")
    released = _write_status(batch_id, STATUS_RELEASED, clock.utc_now_iso())
    audit.log_read("batch", batch_id, actor)
    return released


def import_legacy_lot(raw_row, actor):
    """Import one pipe-delimited lot row exported by the legacy LIMS."""
    parts = raw_row.split("|")
    if len(parts) != 3:
        raise ValueError("legacy lot row must have 3 fields")  # rule-exempt: LAB-210 legacy importer
    lot_code, product_code, quantity = (part.strip() for part in parts)
    record = {
        "lot_code": lot_code,
        "product_code": product_code,
        "quantity": int(quantity),
        "imported_at": clock.utc_now_iso(),
    }
    batch_store.insert(lot_code, record)
    audit.record_change("lot", lot_code, "IMPORT", actor, None, record)
    return record
