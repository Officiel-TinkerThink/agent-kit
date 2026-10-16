"""In-memory plan store: an append-only row history and the applied index.

PlanStore methods do not acquire locks. Callers hold the named locks from
locks.LockSet in the order documented in locks.py.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple

from models import STATUS_APPLIED, STATUS_PENDING, PlanRow

LOG = logging.getLogger("plan_store")


class VersionCounter:
    """Hands out increasing version numbers per plan id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Dict[str, int] = {}

    def next(self, plan_id: str) -> int:
        """Return the next version for plan_id; safe across threads."""
        with self._lock:
            value = self._last.get(plan_id, 0) + 1
            self._last[plan_id] = value
            return value


class PlanStore:
    """Row history plus the current applied state per plan id."""

    def __init__(self) -> None:
        self._rows: Dict[int, PlanRow] = {}
        self._seq = 0
        self._current: Dict[str, Tuple[int, Dict[str, Any]]] = {}
        self._versions = VersionCounter()

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def new_version(self, plan_id: str) -> int:
        """Allocate the next version number for plan_id."""
        return self._versions.next(plan_id)

    def put_pending(self, plan_id: str, version: int, payload: Dict[str, Any]) -> PlanRow:
        """Store a submitted plan version as pending and return its row."""
        row = PlanRow(self._next_seq(), plan_id, version, STATUS_PENDING, payload)
        self._rows[row.seq] = row
        LOG.info("pending %s v%d seq=%d", plan_id, version, row.seq)
        return row

    def pending_row(self, plan_id: str) -> Optional[PlanRow]:
        """Return the newest pending row for plan_id, or None."""
        candidates = [
            row
            for row in self._rows.values()
            if row.plan_id == plan_id and row.is_pending()
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: row.seq)

    def applied_version(self, plan_id: str) -> int:
        """Return the version currently applied for plan_id, 0 if none."""
        return self._current.get(plan_id, (0, {}))[0]

    def applied_payload(self, plan_id: str) -> Dict[str, Any]:
        """Return a copy of the applied payload for plan_id, empty if none."""
        return dict(self._current.get(plan_id, (0, {}))[1])

    def write_applied(self, plan_id: str, version: int, patch: Dict[str, Any]) -> PlanRow:
        """Replace the applied state for plan_id and append a history row."""
        self._current[plan_id] = (version, patch)
        row = PlanRow(self._next_seq(), plan_id, version, STATUS_APPLIED, patch)
        self._rows[row.seq] = row
        return row

    def latest_applied_seq(self) -> int:
        """Return the highest seq among applied history rows, 0 if none."""
        seqs = [row.seq for row in self._rows.values() if row.status == STATUS_APPLIED]
        return max(seqs, default=0)

    def delete_older_than(self, horizon: int) -> int:
        """Delete rows with seq below horizon and return how many were removed."""
        doomed = [seq for seq in self._rows if seq < horizon]
        for seq in doomed:
            del self._rows[seq]
        LOG.info("deleted %d rows below seq %d", len(doomed), horizon)
        return len(doomed)

    def row_count(self) -> int:
        """Number of rows currently held, pending and applied."""
        return len(self._rows)

    def save_snapshot(self, path: str) -> int:
        """Write all rows to path atomically (temp file, fsync, os.replace)."""
        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".snap-", suffix=".tmp")
        try:
            rows = [asdict(row) for row in self._rows.values()]
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(rows, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        LOG.info("snapshot %d rows to %s", len(rows), path)
        return len(rows)
