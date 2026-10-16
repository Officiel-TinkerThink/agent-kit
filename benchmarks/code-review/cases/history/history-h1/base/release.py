"""Lot release workflow for QC-approved batches."""

import logging
from datetime import datetime, timezone

log = logging.getLogger("lims.release")

RELEASABLE_STATUSES = ("QC_PASSED", "QA_REVIEW")


class ReleaseError(Exception):
    """Raised when a lot cannot be released or rejected."""


def _append_release_entry(store, lot_id, operator, comment):
    entry = {
        "lot_id": lot_id,
        "action": "RELEASE",
        "operator": operator,
        "comment": comment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    store.append_audit(entry)
    return entry


def release_lot(lot_id, operator, comment="", store=None):
    if store is None:
        raise ReleaseError("store is required")
    lot = store.get_lot(lot_id)
    if lot is None:
        raise ReleaseError(f"unknown lot {lot_id}")
    if lot["status"] not in RELEASABLE_STATUSES:
        raise ReleaseError(f"lot {lot_id} status {lot['status']} is not releasable")
    if not operator:
        raise ReleaseError("operator is required")
    if not comment:
        log.warning("LOT_RELEASE_NO_COMMENT lot=%s operator=%s", lot_id, operator)
    entry = _append_release_entry(store, lot_id, operator, comment)
    store.set_status(lot_id, "RELEASED")
    log.info("lot released lot=%s operator=%s", lot_id, operator)
    return entry


def reject_lot(lot_id, operator, reason, store=None):
    if store is None:
        raise ReleaseError("store is required")
    if not reason:
        raise ReleaseError("reason is required for rejection")
    entry = {
        "lot_id": lot_id,
        "action": "REJECT",
        "operator": operator,
        "comment": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    store.append_audit(entry)
    store.set_status(lot_id, "REJECTED")
    log.info("lot rejected lot=%s operator=%s", lot_id, operator)
    return entry
