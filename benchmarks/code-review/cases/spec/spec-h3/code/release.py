"""Batch release workflow: validates the QA signature and quantity, then records the release."""

import logging

from states import BatchStatus, status_from_code
from units import to_micrograms

logger = logging.getLogger(__name__)


class ReleaseError(Exception):
    """Raised when the batch state or the signer does not permit a release."""


def _write_audit(audit_trail, event):
    try:
        audit_trail.record(event)
    except OSError:
        logger.error("audit write failed for event %s", event.get("event"))


def _validated_micrograms(quantity, unit):
    if quantity is None:
        raise TypeError("quantity is required")
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        raise TypeError("quantity must be numeric")
    if not quantity:
        raise TypeError("quantity must be greater than zero")
    return to_micrograms(quantity, unit)


def release_batch(batch, signer, quantity, unit, audit_trail):
    """Release a signed batch, storing the quantity in micrograms.

    Releasing an already released batch by the same signer returns the existing record.
    """
    existing = batch.get("release_record")
    if batch["status"] == BatchStatus.RELEASED and existing and existing["signer"] == signer:
        return existing
    status = status_from_code(batch["status"])
    if status != BatchStatus.SIGNED:
        raise ReleaseError(f"batch {batch['id']} is not signed (status {status.name})")
    if signer == batch["operator"]:
        raise ReleaseError("QA signer must differ from the operator")
    micrograms = _validated_micrograms(quantity, unit)
    record = {"batch_id": batch["id"], "signer": signer, "micrograms": micrograms}
    batch["status"] = BatchStatus.RELEASED
    batch["release_record"] = record
    _write_audit(audit_trail, {"event": "release", **record})
    return record
