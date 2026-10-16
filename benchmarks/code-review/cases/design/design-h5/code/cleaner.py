"""Removes history rows that no longer need to be kept.

All cleanup work goes through sweep_once. Each sweep keeps the rows at or
above the latest applied seq. The cleaner runs on its own thread; requests
are queued and consumed by that single thread.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Dict, Optional

from locks import LockSet
from plan_store import PlanStore

LOG = logging.getLogger("plan_cleaner")
SWEEP_REQUEST = "sweep"
STOP_REQUEST = "stop"


class PlanCleaner:
    """Periodic and on-demand removal of old history rows."""

    def __init__(self, store: PlanStore, locks: LockSet, interval_s: float = 60.0) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self._store = store
        self._locks = locks
        self.interval_s = interval_s
        self._requests: "queue.Queue[str]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
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
        with self._locks.store:
            horizon = self._store.latest_applied_seq()
            with self._locks.plan:
                removed = self._store.delete_older_than(horizon)
        self._sweeps += 1
        LOG.info("sweep %d removed %d rows (horizon %d)", self._sweeps, removed, horizon)
        return removed

    def start(self) -> None:
        """Start the background thread; refuses to start twice."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("cleaner already running")
        self._thread = threading.Thread(target=self._run, name="plan-cleaner", daemon=True)
        self._thread.start()

    def request_sweep(self) -> None:
        """Ask the background thread for a sweep without waiting for the interval."""
        self._requests.put(SWEEP_REQUEST)

    def stop(self, timeout_s: float = 5.0) -> None:
        """Ask the background thread to exit and wait up to timeout_s."""
        self._requests.put(STOP_REQUEST)
        if self._thread is not None:
            self._thread.join(timeout_s)
            if self._thread.is_alive():
                LOG.info("cleaner did not stop within %.1f s", timeout_s)

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

    def _run(self) -> None:
        while True:
            try:
                request = self._requests.get(timeout=self.interval_s)
            except queue.Empty:
                request = SWEEP_REQUEST
            if request == STOP_REQUEST:
                break
            try:
                self.sweep_once()
            except Exception:
                LOG.exception("sweep failed; will retry on next request")
        LOG.info("cleaner stopped")
