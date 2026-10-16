"""Nightly job runner: inventory snapshot, retention pruning and ops notice."""

import logging
from datetime import datetime, timezone

from backup_store import prune_snapshots, snapshot_inventory
from config import BackupSettings

log = logging.getLogger("lims_bridge.scheduler")


def _send(channel: str, message: str) -> None:
    """Deliver a message to the ops channel adapter."""
    log.info("ops channel=%s message=%s", channel, message)


def notify_ops(channel: str, message: str) -> None:
    """Send an operations notice; a failed notice must not stop the nightly run."""
    try:
        _send(channel, message)
    except Exception as exc:
        log.warning("ops notice not delivered channel=%s error=%s", channel, exc)


def _utc_stamp() -> str:
    """Return the current UTC time as a compact sortable stamp."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_due(last_run_hours: float, interval_hours: float) -> bool:
    """Return True when at least interval_hours have passed since the last run."""
    if interval_hours <= 0:
        raise ValueError("interval_hours must be positive")
    return last_run_hours >= interval_hours


def next_sequence(previous: int | None) -> int:
    """Return the next snapshot sequence number, starting at 1."""
    if previous is None:
        return 1
    if previous < 0:
        raise ValueError("previous sequence must not be negative")
    return previous + 1


def describe_schedule(interval_hours: float, last_run_hours: float) -> str:
    """Return a one-line schedule status for the ops channel."""
    due = is_due(last_run_hours, interval_hours)
    state = "due" if due else "waiting"
    return f"schedule state={state} interval_hours={interval_hours:g} since_last={last_run_hours:g}"


def run_nightly(settings: BackupSettings, payload: bytes, sequence: int) -> dict:
    """Run the nightly snapshot, prune retention and report the job outcome."""
    label = str(sequence)
    started = _utc_stamp()
    ok = snapshot_inventory(settings, payload, label)
    status = "complete" if ok else "failed"
    pruned = prune_snapshots(settings)
    notify_ops("ops-nightly", f"inventory snapshot {label} status={status}")
    log.info("nightly run finished started=%s status=%s pruned=%d", started, status, pruned)
    return {"sequence": sequence, "status": status, "pruned": pruned, "started": started}
