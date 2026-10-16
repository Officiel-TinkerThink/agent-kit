"""Request handlers for regulated record endpoints."""

import logging
from typing import Any, Dict, Tuple

from models import RecordNotFound, ValidationError
from record_store import RecordStore

log = logging.getLogger("api")


def error_status(exc: Exception) -> int:
    """Map a domain exception to an HTTP status code."""
    if isinstance(exc, RecordNotFound):
        return 404
    if isinstance(exc, ValidationError):
        return 422
    return 500


def error_body(exc: Exception) -> Dict[str, Any]:
    """Return the JSON error body for a domain exception."""
    return {"error": type(exc).__name__, "detail": str(exc)}


class RecordApi:
    """Maps request bodies to store operations and builds response tuples."""

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def create_record(self, body: Dict[str, Any], actor: str) -> Tuple[int, Dict[str, Any]]:
        """POST: create a record from the kind and payload fields."""
        payload = body.get("payload")
        if not isinstance(payload, dict):
            raise ValidationError("payload must be an object")
        record = self._store.create(body.get("kind"), payload, actor)
        log.info("create request by %s", actor)
        return 201, {"record_id": record.record_id, "version": record.version}

    def get_record(self, record_id: str) -> Tuple[int, Dict[str, Any]]:
        """GET: return the current payload of a record."""
        record = self._store.get(record_id)
        return 200, {
            "record_id": record.record_id,
            "payload": record.snapshot(),
            "version": record.version,
        }

    def update_record(
        self,
        record_id: str,
        body: Dict[str, Any],
        actor: str,
    ) -> Tuple[int, Dict[str, Any]]:
        """PATCH: merge the changes object into the record."""
        changes = body.get("changes")
        if not isinstance(changes, dict):
            raise ValidationError("changes must be an object")
        record = self._store.update(record_id, changes, actor)
        log.info("update request by %s", actor)
        return 200, {"record_id": record.record_id, "version": record.version}
