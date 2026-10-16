"""Lot hold and release decisions for batch records."""

from __future__ import annotations

from dataclasses import dataclass

from clock import utc_now_iso
from errors import DomainError
from services import audit, ops_feed
from services.lot_store import LotStore

REASON_CODES = frozenset({"QC_PASS", "DEVIATION_WAIVED", "SUPERVISOR_OVERRIDE"})


@dataclass(frozen=True)
class LotHold:
    lot_id: str
    reason: str
    held_by: str
    held_at: str


@dataclass(frozen=True)
class LotRelease:
    lot_id: str
    reason_code: str
    released_by: str
    released_at: str


class LotHoldService:
    """Places lots on QA hold, releases them, and keeps the lot status consistent."""

    def __init__(self, store: LotStore) -> None:
        self._store = store

    def hold_lot(self, lot_id: str, reason: str, held_by: str) -> LotHold:
        if not reason.strip():
            raise DomainError("hold reason is required")
        lot = self._store.get(lot_id)
        if lot is None:
            raise DomainError(f"lot not found: {lot_id}")
        if lot.status != "IN_PROCESS":
            raise DomainError(f"lot {lot_id} is {lot.status}, cannot hold")
        hold = LotHold(lot_id, reason, held_by, utc_now_iso())
        self._store.update_status(lot_id, "QA_HOLD", held_at=hold.held_at)
        audit.record_change(
            entity="lot",
            entity_id=lot_id,
            action="HOLD",
            actor=held_by,
            detail={"reason": reason},
        )
        return hold

    def release_lot(self, lot_id: str, reason_code: str, released_by: str) -> LotRelease:
        if reason_code not in REASON_CODES:
            raise DomainError(f"unknown reason code: {reason_code}")
        lot = self._store.get(lot_id)
        if lot is None:
            raise DomainError(f"lot not found: {lot_id}")
        if lot.status != "QA_HOLD":
            ops_feed.push("LOT_RELEASE_REJECTED", lot_id=lot_id, status=lot.status)
            raise DomainError(f"lot {lot_id} is {lot.status}, not QA_HOLD")
        release = LotRelease(lot_id, reason_code, released_by, utc_now_iso())
        self._persist_release(release)
        audit.record_change(
            entity="lot",
            entity_id=lot_id,
            action="RELEASE",
            actor=released_by,
            detail={"reason_code": reason_code},
        )
        return release

    def _persist_release(self, release: LotRelease) -> None:
        self._store.update_status(
            release.lot_id, "RELEASED", released_at=release.released_at
        )

    def get_hold_reason(self, lot_id: str) -> str | None:
        lot = self._store.get(lot_id)
        if lot is None:
            raise DomainError(f"lot not found: {lot_id}")
        return lot.hold_reason
