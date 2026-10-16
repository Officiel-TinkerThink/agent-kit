"""Append-only audit trail for GxP record changes."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_DEFAULT_PATH = Path("audit") / "changes.jsonl"
_REQUIRED_FIELDS = ("entity", "entity_id", "action", "actor")


class AuditError(RuntimeError):
    """Raised when an audit entry cannot be validated or persisted."""


def _validate(entry: dict[str, Any]) -> None:
    missing = [name for name in _REQUIRED_FIELDS if not entry.get(name)]
    if missing:
        raise AuditError(f"audit entry missing fields: {', '.join(missing)}")


def record_change(
    entity: str,
    entity_id: str,
    action: str,
    actor: str,
    detail: dict[str, Any] | None = None,
    path: Path = _DEFAULT_PATH,
) -> dict[str, Any]:
    entry = {
        "entity": entity,
        "entity_id": entity_id,
        "action": action,
        "actor": actor,
        "detail": detail or {},
        "at": datetime.now(timezone.utc).isoformat(),
    }
    _validate(entry)
    line = json.dumps(entry, sort_keys=True)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return entry


def read_entries(path: Path = _DEFAULT_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def entries_for(
    entity: str, entity_id: str, path: Path = _DEFAULT_PATH
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in read_entries(path)
        if entry.get("entity") == entity and entry.get("entity_id") == entity_id
    ]
