"""Named locks shared by the plan store, the applier and the cleaner.

Acquisition order (contract for every caller):
    1. plan   serialises version checks and applies for plan ids
    2. store  serialises writes to the row table and the applied index

A thread that holds the store lock must not request the plan lock.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

LOG = logging.getLogger("plan_locks")

LOCK_ORDER: Tuple[str, ...] = ("plan", "store")
WAIT_WARN_MS = 250.0


@dataclass
class LockSet:
    """The two locks used by the plan subsystem."""

    plan: threading.Lock = field(default_factory=threading.Lock)
    store: threading.Lock = field(default_factory=threading.Lock)

    def by_name(self, name: str) -> threading.Lock:
        """Return the lock registered under name; unknown names are refused."""
        if name not in LOCK_ORDER:
            raise KeyError(f"unknown lock name: {name!r}")
        return getattr(self, name)

    def describe(self) -> Dict[str, str]:
        """Snapshot of lock state for diagnostics; values are 'held' or 'free'."""
        return {
            name: ("held" if self.by_name(name).locked() else "free")
            for name in LOCK_ORDER
        }


def ordered(names) -> Tuple[str, ...]:
    """Return the given lock names sorted into the documented acquisition order."""
    rank = {name: index for index, name in enumerate(LOCK_ORDER)}
    unknown = [name for name in names if name not in rank]
    if unknown:
        raise KeyError(f"unknown lock names: {unknown}")
    return tuple(sorted(set(names), key=rank.__getitem__))


def log_wait(name: str, started: float) -> None:
    """Log lock acquisitions that waited longer than WAIT_WARN_MS."""
    waited_ms = (time.monotonic() - started) * 1000.0
    if waited_ms > WAIT_WARN_MS:
        LOG.info("lock %s waited %.1f ms", name, waited_ms)


def lock_names() -> Tuple[str, ...]:
    """Return the lock names in acquisition order."""
    return LOCK_ORDER
