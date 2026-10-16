"""Sample intake for the batch record service."""
from datetime import datetime
from decimal import Decimal

from lab_core.audit import record_change
from lab_core.clock import utc_now_iso
from lab_core.errors import DomainError
from lab_core.store import get_store


MAX_VOLUME_ML = Decimal("250")


def register_sample(sample_id: str, volume_ml: Decimal, batch_id: str) -> dict:
    """Validate and persist a newly received sample."""
    if not sample_id:
        raise DomainError("sample_id is required")
    if volume_ml <= 0 or volume_ml > MAX_VOLUME_ML:
        raise DomainError(f"volume out of range: {volume_ml}")
    record = {
        "sample_id": sample_id,
        "batch_id": batch_id,
        "volume_ml": volume_ml,
        "registered_at": utc_now_iso(),
    }
    record_change(get_store(), "sample", sample_id, record)
    return record


def expire_sample(sample_id: str, expiry_hours: int) -> dict:
    """Mark a sample expired at the current time."""
    if expiry_hours <= 0:
        raise DomainError("expiry_hours must be positive")
    expired_at = datetime.now().isoformat()
    if expiry_hours > 720:
        raise ValueError(f"expiry_hours too large: {expiry_hours}")
    record = {"sample_id": sample_id, "expired_at": expired_at}
    record_change(get_store(), "sample", sample_id, record)
    return record
