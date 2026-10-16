"""Append-only audit trail for GxP-relevant events.

Each event is written as one JSON line with a UTC timestamp, the event name
and the supplied fields. Existing lines are never rewritten.
"""

import json
import os
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_DEFAULT_PATH = os.environ.get("AUDIT_LOG_PATH", "audit_events.jsonl")


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(path):
    return path or _DEFAULT_PATH


def _serialisable(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def record_event(event, **fields):
    """Append one audit event and return the stored record.

    Raises ValueError when the event name is empty. Field values that are
    not JSON-serialisable are stored as their str() form.
    """
    name = (event or "").strip()
    if not name:
        raise ValueError("audit event name must not be empty")
    record = {"ts": _utc_now_iso(), "event": name}
    for key, value in fields.items():
        record[key] = _serialisable(value)
    line = json.dumps(record, sort_keys=True)
    with _LOCK:
        with open(_resolve_path(None), "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return record


def read_events(event=None, path=None):
    """Return stored audit records, optionally filtered by event name."""
    target = _resolve_path(path)
    if not os.path.exists(target):
        return []
    records = []
    with open(target, encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if event is None or item.get("event") == event:
                records.append(item)
    return records


def count_events(path=None):
    target = _resolve_path(path)
    if not os.path.exists(target):
        return 0
    with open(target, encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())
