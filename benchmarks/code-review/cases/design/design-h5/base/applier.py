"""Applies stored plan versions to the applied state of each plan id.

Lock contract (see locks.py): the plan lock is taken before the store lock.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from locks import LockSet
from models import APPLY_APPLIED, APPLY_NOTHING_PENDING, APPLY_STALE, ApplyResult
from plan_store import PlanStore

LOG = logging.getLogger("plan_applier")
MAX_PATCH_KEYS = 500


class PlanApplier:
    """Moves a pending plan version into the applied state."""

    def __init__(self, store: PlanStore, locks: LockSet) -> None:
        self._store = store
        self._locks = locks

    def apply_next(self, plan_id: str) -> ApplyResult:
        """Apply the newest pending version of plan_id, if there is one."""
        with self._locks.plan:
            row = self._store.pending_row(plan_id)
        if row is None:
            LOG.info("no pending plan for %s", plan_id)
            return ApplyResult(APPLY_NOTHING_PENDING, plan_id)
        return self.apply(plan_id, row.version, row.payload)

    def apply(self, plan_id: str, version: int, payload: Mapping[str, Any]) -> ApplyResult:
        """Check the version and write the patch, all under the plan lock."""
        with self._locks.plan:
            current = self._store.applied_version(plan_id)
            if version <= current:
                LOG.info("stale %s v%d (applied v%d)", plan_id, version, current)
                return ApplyResult(APPLY_STALE, plan_id, version)
            patch = self._build_patch(payload)
            with self._locks.store:
                self._store.write_applied(plan_id, version, patch)
        LOG.info("applied %s v%d", plan_id, version)
        return ApplyResult(APPLY_APPLIED, plan_id, version)

    def _build_patch(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a sorted copy of payload; oversized payloads are refused."""
        if len(payload) > MAX_PATCH_KEYS:
            raise ValueError(f"payload has {len(payload)} keys, limit is {MAX_PATCH_KEYS}")
        return {key: payload[key] for key in sorted(payload)}

    def current_payload(self, plan_id: str) -> Dict[str, Any]:
        """Read the applied payload for plan_id under the store lock."""
        with self._locks.store:
            return self._store.applied_payload(plan_id)

    def apply_all(self, plan_ids) -> Dict[str, int]:
        """Apply the next pending version for each id and count the outcomes."""
        counts = {APPLY_APPLIED: 0, APPLY_STALE: 0, APPLY_NOTHING_PENDING: 0}
        for plan_id in plan_ids:
            result = self.apply_next(plan_id)
            counts[result.status] += 1
        LOG.info("apply_all: %s", counts)
        return counts
