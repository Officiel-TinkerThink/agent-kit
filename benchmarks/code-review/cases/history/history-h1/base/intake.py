"""Sample and manifest intake for the QC laboratory LIMS bridge."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("lims.intake")

MAX_BATCH_ID_LEN = 32
VALID_SOURCES = ("manual", "import")


class IntakeError(Exception):
    """Raised when an intake request violates a validation rule."""


@dataclass
class SampleRecord:
    batch_id: str
    source: str
    quantity: int
    operator: str
    received_at: str
    flags: list = field(default_factory=list)


def _check_quantity(quantity):
    if not isinstance(quantity, int) or quantity <= 0:
        raise IntakeError("quantity must be a positive integer")


def receive_sample(batch_id, source, quantity, operator):
    if source not in VALID_SOURCES:
        raise IntakeError(f"unknown source: {source}")
    if batch_id is None:
        raise IntakeError("batch_id required")
    if len(batch_id) > MAX_BATCH_ID_LEN:
        raise IntakeError("batch_id too long")
    _check_quantity(quantity)
    if source == "manual":
        flags = []
    else:
        flags = ["IMPORTED"]
    record = SampleRecord(
        batch_id=batch_id,
        source=source,
        quantity=quantity,
        operator=operator,
        received_at=datetime.now(timezone.utc).isoformat(),
        flags=flags,
    )
    log.info("sample received batch=%s source=%s", batch_id, source)
    return record


def register_manifest_row(row):
    batch_id = row.get("batch_id")
    if batch_id is None:
        raise IntakeError("batch_id required")
    if len(batch_id) > MAX_BATCH_ID_LEN:
        raise IntakeError("batch_id too long")
    quantity = row.get("quantity")
    _check_quantity(quantity)
    record = SampleRecord(
        batch_id=batch_id,
        source="import",
        quantity=quantity,
        operator=row.get("operator", ""),
        received_at=datetime.now(timezone.utc).isoformat(),
        flags=["IMPORTED", "MANIFEST"],
    )
    log.info("manifest row registered batch=%s", batch_id)
    return record
