"""Removes history rows that no longer need to be kept.

All cleanup work goes through sweep_once. Each sweep keeps the rows at or
above the latest applied seq.
"""

from __future__ import annotations

import logging
from typing import Dict

from locks import LockSet
from plan_store import PlanStore

LOG = logging.getLogger("plan_cleaner")


class PlanCleaner:
    """Periodic removal of old history rows."""

    def __init__(self, store: PlanStore, locks: LockSet, interval_s: float = 60.0) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self._store = store
        self._locks = locks
        self.interval_s = interval_s
        self._sweeps = 0

    @property
    def sweeps(self) -> int:
        """Number of completed sweeps since construction."""
        return self._sweeps

    def __repr__(self) -> str:
        return f"PlanCleaner(interval_s={self.interval_s}, sweeps={self._sweeps})"

    def reset_counters(self) -> None:
        """Forget the sweep count; used by tests and by the periodic report."""
        self._sweeps = 0

    def sweep_once(self) -> int:
        """Delete history below the latest applied seq and return the count."""
        with self._locks.plan:
            horizon = self._store.latest_applied_seq()
            removed = self._store.delete_older_than(horizon)
        self._sweeps += 1
        LOG.info("sweep %d removed %d rows (horizon %d)", self._sweeps, removed, horizon)
        return removed

    def describe(self) -> Dict[str, object]:
        """Diagnostic snapshot of the cleaner and the row count."""
        with self._locks.store:
            rows = self._store.row_count()
        return {
            "interval_s": self.interval_s,
            "sweeps": self._sweeps,
            "rows": rows,
        }

    def due(self, elapsed_s: float) -> bool:
        """True when at least one interval has passed since the last sweep."""
        return elapsed_s >= self.interval_s
