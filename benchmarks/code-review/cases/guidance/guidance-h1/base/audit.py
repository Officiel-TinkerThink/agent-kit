"""Audit trail helpers for record changes and record reads."""

import json
import logging

import clock

logger = logging.getLogger("audit")

_sink = None


def configure_sink(sink):
    """Install the append-only sink that receives audit entries."""
    global _sink
    _sink = sink


def _emit(event):
    if _sink is None:
        raise RuntimeError("audit sink is not configured")
    _sink.append(json.dumps(event, sort_keys=True))


def record_change(entity, entity_id, action, actor, before, after):
    """Write an attributable change entry with before and after images."""
    if not actor:
        raise RuntimeError("audit entries require an attributable actor")
    event = {
        "type": "change",
        "entity": entity,
        "entity_id": entity_id,
        "action": action,
        "actor": actor,
        "before": before,
        "after": after,
        "at": clock.utc_now_iso(),
    }
    _emit(event)
    logger.info("change %s %s %s by %s", entity, entity_id, action, actor)
    return event


def log_read(entity, entity_id, actor):
    """Write an entry recording that a record was viewed. No change is described."""
    if not actor:
        raise RuntimeError("audit entries require an attributable actor")
    event = {
        "type": "read",
        "entity": entity,
        "entity_id": entity_id,
        "actor": actor,
        "at": clock.utc_now_iso(),
    }
    _emit(event)
    logger.info("read %s %s by %s", entity, entity_id, actor)
    return event


def verify_entries(lines):
    """Parse exported audit lines and fail on any entry without a timestamp."""
    entries = []
    for number, line in enumerate(lines, start=1):
        entry = json.loads(line)
        if "at" not in entry:
            raise RuntimeError(f"audit line {number} has no timestamp")
        entries.append(entry)
    return entries
