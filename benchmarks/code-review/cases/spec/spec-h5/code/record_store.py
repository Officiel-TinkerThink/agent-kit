"""Regulated record persistence for the batch and lab modules."""

import itertools
import logging
from typing import Any, Dict, Optional

from audit import AuditLog
from models import RegulatedRecord, RecordNotFound, ValidationError

log = logging.getLogger("record_store")


class RecordStore:
    """In-memory store. Each create, update and delete writes one audit entry."""

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit
        self._records: Dict[str, RegulatedRecord] = {}
        self._ids = itertools.count(1)

    def create(
        self,
        kind: str,
        payload: Dict[str, Any],
        actor: str,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> RegulatedRecord:
        """Store a new record created by actor and audit the creation."""
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
        self._audit.record(
            actor,
            "create",
            record_id,
            old_value=None,
            new_value=record.snapshot(),
            client_context=client_context,
        )
        log.info("created %s kind=%s", record_id, kind)
        return record

    def get(self, record_id: str) -> RegulatedRecord:
        """Return the stored record or raise RecordNotFound."""
        return self._require(record_id)

    def update(
        self,
        record_id: str,
        changes: Dict[str, Any],
        actor: str,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> RegulatedRecord:
        """Merge changes into the record, bump its version and audit both values."""
        if not changes:
            raise ValidationError("no changes supplied")
        record = self._require(record_id)
        previous = record.payload
        record.payload.update(changes)
        record.version += 1
        self._audit.record(
            actor,
            "update",
            record_id,
            old_value=previous,
            new_value=record.snapshot(),
            client_context=client_context,
        )
        log.info("updated %s to version %d by %s", record_id, record.version, actor)
        return record

    def delete(
        self,
        record_id: str,
        actor: str,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Remove the record and audit the removed value."""
        record = self._require(record_id)
        before = record.snapshot()
        del self._records[record_id]
        self._audit.record(
            actor,
            "delete",
            record_id,
            old_value=before,
            new_value=None,
            client_context=client_context,
        )
        log.info("deleted %s by %s", record_id, actor)

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
