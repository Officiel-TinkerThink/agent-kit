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
