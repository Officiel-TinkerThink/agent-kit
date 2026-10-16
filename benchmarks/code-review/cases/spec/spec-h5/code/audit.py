"""Append-only audit trail for regulated record changes."""

import itertools
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from models import AuditEntry

log = logging.getLogger("audit")

ALLOWED_ACTIONS = ("create", "update", "delete", "sign")


def _server_clock() -> datetime:
    """Return the current UTC time from the host clock."""
    return datetime.now(timezone.utc)


class AuditLog:
    """Holds audit entries in insertion order. Offers no update or delete operation."""

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._clock = clock or _server_clock
        self._entries: List[AuditEntry] = []
        self._ids = itertools.count(1)

    def record(
        self,
        actor: str,
        action: str,
        record_id: str,
        old_value: Optional[Dict[str, Any]],
        new_value: Optional[Dict[str, Any]],
        meaning: Optional[str] = None,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Append one entry for a change to a regulated record.

        The client context may carry the time the operator saw on screen; it is
        kept for the operator trail and does not replace the server time.
        """
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"unknown audit action: {action!r}")
        if not actor:
            raise ValueError("audit entry requires an actor")
        when = (client_context or {}).get("timestamp") or self._clock()
        entry = AuditEntry(
            entry_id=f"AE-{next(self._ids):06d}",
            record_id=record_id,
            action=action,
            actor=actor,
            server_time=when,
            old_value=old_value,
            new_value=new_value,
            meaning=meaning,
            client_context=client_context,
        )
        self._entries.append(entry)
        log.info("audit %s", entry.describe())
        return entry

    def entries_for(self, record_id: str) -> Tuple[AuditEntry, ...]:
        """Return the entries of one record as an immutable tuple."""
        return tuple(e for e in self._entries if e.record_id == record_id)

    def __len__(self) -> int:
        """Return the number of audit entries written so far."""
        return len(self._entries)
