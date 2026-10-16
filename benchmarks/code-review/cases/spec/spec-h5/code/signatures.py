"""Electronic signature entries bound to a record and a stated meaning."""

from typing import Optional

from audit import AuditLog
from models import AuditEntry
from record_store import RecordStore

SIGNATURE_MEANINGS = ("approved", "reviewed", "rejected")


class SignatureService:
    """Writes signature entries to the audit trail."""

    def __init__(self, audit: AuditLog, store: RecordStore) -> None:
        self._audit = audit
        self._store = store

    def sign_approval(
        self,
        record_id: str,
        actor: str,
        meaning: str = "approved",
        comment: Optional[str] = None,
    ) -> AuditEntry:
        """Record an approval or rejection together with its stated meaning."""
        if meaning not in SIGNATURE_MEANINGS:
            raise ValueError(f"unknown signature meaning: {meaning!r}")
        self._store.get(record_id)
        return self._audit.record(
            actor,
            "sign",
            record_id,
            old_value=None,
            new_value={"meaning": meaning, "comment": comment},
            meaning=meaning,
        )

    def sign_review(
        self,
        record_id: str,
        actor: str,
        comment: Optional[str] = None,
    ) -> AuditEntry:
        """Record that the reviewer has checked the record."""
        self._store.get(record_id)
        return self._audit.record(
            actor,
            "sign",
            record_id,
            old_value=None,
            new_value={"reviewed_by": actor, "comment": comment},
        )

    def meaning_label(self, meaning: str) -> str:
        """Return the label printed beside a signature in review reports."""
        labels = {"approved": "Approved", "reviewed": "Reviewed", "rejected": "Rejected"}
        return labels.get(meaning, meaning)

    def verify_signer(self, entry: AuditEntry, expected_actor: str) -> bool:
        """Return True when the entry was written by the expected actor."""
        return entry.actor == expected_actor
