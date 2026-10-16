"""Domain models for regulated records and their audit entries."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class RecordNotFound(KeyError):
    """Raised when a record id is not present in the store."""


class ValidationError(ValueError):
    """Raised when a request body fails validation."""


def require_fields(payload: Dict[str, Any], names: Tuple[str, ...]) -> None:
    """Raise ValidationError when any named field is missing or None."""
    missing = [name for name in names if payload.get(name) is None]
    if missing:
        raise ValidationError(f"missing fields: {', '.join(missing)}")


@dataclass
class RegulatedRecord:
    """A regulated record such as a batch step or a lab result."""

    record_id: str
    kind: str
    payload: Dict[str, Any]
    version: int = 1
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        """Return a detached copy of the payload for comparison and audit."""
        return dict(self.payload)

    def summary(self) -> Dict[str, Any]:
        """Return the identifying fields used in list views."""
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "version": self.version,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class AuditEntry:
    """One immutable row of the audit trail."""

    entry_id: str
    record_id: str
    action: str
    actor: str
    server_time: datetime
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    meaning: Optional[str] = None
    client_context: Optional[Dict[str, Any]] = None

    def describe(self) -> str:
        """Return a one line description for operator logs."""
        return f"{self.entry_id} {self.action} {self.record_id} by {self.actor}"
