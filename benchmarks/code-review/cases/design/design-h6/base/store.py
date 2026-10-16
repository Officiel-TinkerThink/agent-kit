"""Append-only audit store for accepted instrument events."""

import json
import logging
import os

import settings

log = logging.getLogger("intake.store")


class AuditStore:
    """Writes accepted events as JSON lines, one line per event."""

    def __init__(self, path=None):
        self.path = path or settings.STORE_PATH

    def is_writable(self):
        """Return False when the store file cannot be opened for append."""
        try:
            with open(self.path, "a", encoding="utf-8"):
                pass
        except OSError as exc:
            log.error("audit store not writable at %s: %s", self.path, exc)
            return False
        return True

    def write_batch(self, events):
        """Append every event in the batch and flush the file to disk.

        Returns the number of lines written. An OSError is logged and re-raised.
        """
        lines = [self._serialize(event) for event in events]
        try:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write("".join(lines))
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            log.error("audit write failed for %d events: %s", len(lines), exc)
            raise
        return len(lines)

    def _serialize(self, event):
        record = {
            "event_id": event.event_id,
            "site_id": event.site_id,
            "instrument_id": event.instrument_id,
            "recorded_at": event.recorded_at,
            "payload": event.payload,
        }
        return json.dumps(record, sort_keys=True) + "\n"

    def exists(self):
        """Return True when the store file is already present on disk."""
        return os.path.exists(self.path)

    def count_lines(self):
        """Return the number of stored records."""
        if not os.path.exists(self.path):
            return 0
        with open(self.path, encoding="utf-8") as handle:
            return sum(1 for _ in handle)
