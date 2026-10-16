"""Regulated record persistence for the batch and lab modules."""

import itertools
import logging
from typing import Any, Dict

from models import RegulatedRecord, RecordNotFound, ValidationError

log = logging.getLogger("record_store")


class RecordStore:
    """In-memory store for regulated records."""

    def __init__(self) -> None:
        self._records: Dict[str, RegulatedRecord] = {}
        self._ids = itertools.count(1)

    def create(self, kind: str, payload: Dict[str, Any], actor: str) -> RegulatedRecord:
        """Store a new record created by actor."""
        if not kind:
            raise ValidationError("kind is required")
        record_id = f"REC-{next(self._ids):05d}"
        record = RegulatedRecord(
            record_id=record_id,
            kind=kind,
            payload=dict(payload),
            created_by=actor,
        )
        self._records[record_id] = record
        log.info("created %s kind=%s", record_id, kind)
        return record

    def get(self, record_id: str) -> RegulatedRecord:
        """Return the stored record or raise RecordNotFound."""
        return self._require(record_id)

    def update(self, record_id: str, changes: Dict[str, Any], actor: str) -> RegulatedRecord:
        """Merge changes into the record and bump its version."""
        if not changes:
            raise ValidationError("no changes supplied")
        record = self._require(record_id)
        record.payload.update(changes)
        record.version += 1
        log.info("updated %s to version %d by %s", record_id, record.version, actor)
        return record

    def purge(self, record_id: str) -> None:
        """Drop a record during retention maintenance."""
        self._require(record_id)
        del self._records[record_id]
        log.info("purged %s", record_id)

    def _require(self, record_id: str) -> RegulatedRecord:
        """Look up a record or raise RecordNotFound."""
        try:
            return self._records[record_id]
        except KeyError:
            raise RecordNotFound(record_id) from None
