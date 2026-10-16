"""Lot disposition helpers for QC-approved batch lots."""

import logging
from dataclasses import dataclass, field

import audit_log
import legacy_log

log = logging.getLogger(__name__)

RELEASABLE_STATUSES = ("QC_APPROVED",)
TERMINAL_STATUSES = ("RELEASED", "REJECTED")


class ReleaseError(Exception):
    """Raised when a lot cannot be released in its current state."""


@dataclass
class Lot:
    lot_id: str
    product_code: str
    status: str = "QUARANTINE"
    released_by: str = ""
    history: list = field(default_factory=list)


def is_releasable(lot):
    """Return True when the lot has passed QC and has not been released."""
    return lot.status in RELEASABLE_STATUSES and not lot.released_by


def describe_lot(lot):
    """Return a one-line summary of the lot for operator screens."""
    owner = lot.released_by or "-"
    return f"{lot.lot_id} [{lot.product_code}] {lot.status} released_by={owner}"


def transition_history(lot):
    """Return the lot's transition history as a list of (event, actor) tuples."""
    return list(lot.history)


def find_lot(lots, lot_id):
    """Return the lot with the given ID or raise ReleaseError."""
    lot = lots.get(lot_id)
    if lot is None:
        raise ReleaseError(f"unknown lot {lot_id}")
    return lot


def _check_releasable(lot, approver):
    if not approver or not approver.strip():
        raise ReleaseError("approver is required")
    if not is_releasable(lot):
        raise ReleaseError(f"lot {lot.lot_id} is {lot.status}, not releasable")


def _apply_release(lot, approver):
    lot.status = "RELEASED"
    lot.released_by = approver.strip()
    lot.history.append(("RELEASED", lot.released_by))
    return lot


def release_lot(lots, lot_id, approver):
    """Release a QC-approved lot and record the release in the audit trail.

    Returns the updated Lot. Raises ReleaseError when the lot is unknown,
    has not passed QC, or has already been released.
    """
    lot = find_lot(lots, lot_id)
    _check_releasable(lot, approver)
    _apply_release(lot, approver)
    audit_log.record_event(
        "lot.released",
        lot_id=lot.lot_id,
        approver=lot.released_by,
        product=lot.product_code,
    )
    legacy_log.write("LOT_RELEASE", lot_id)
    log.info("lot %s released by %s", lot.lot_id, lot.released_by)
    return lot
