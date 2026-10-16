"""Batch release record serialization for the lab export tool."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Mapping, TextIO

LOGGER = logging.getLogger("labops.exporter")

JSON_INDENT = 2
YIELD_PRECISION = 2
RELEASABLE_STATUSES = frozenset({"RELEASED", "CONDITIONAL"})


def flatten_batch(batch: Mapping[str, Any]) -> Dict[str, Any]:
    """Project one batch record onto the export columns."""
    return {
        "batch_id": str(batch["batch_id"]),
        "product_code": str(batch["product_code"]),
        "yield_pct": round(float(batch["yield_pct"]), YIELD_PRECISION),
        "status": str(batch["status"]),
        "released_on": str(batch["released_on"]),
    }


def is_releasable(batch: Mapping[str, Any]) -> bool:
    """Return True when the batch status allows release to the warehouse."""
    return str(batch.get("status", "")).upper() in RELEASABLE_STATUSES


def average_yield(batches: Iterable[Mapping[str, Any]]) -> float:
    """Return the mean yield percentage, or 0.0 for an empty input."""
    values = [float(batch["yield_pct"]) for batch in batches]
    if not values:
        return 0.0
    return round(sum(values) / len(values), YIELD_PRECISION)


def summarize_statuses(batches: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    """Count batches per status for the run summary log line."""
    counts: Dict[str, int] = {}
    for batch in batches:
        status = str(batch.get("status", "UNKNOWN")).upper()
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def export_batches_json(
    batches: Iterable[Mapping[str, Any]],
    stream: TextIO,
    *,
    indent: int = JSON_INDENT,
) -> int:
    """Write the batches as a JSON array and return the record count."""
    rows = [flatten_batch(batch) for batch in batches]
    json.dump(rows, stream, indent=indent, sort_keys=True)
    stream.write("\n")
    LOGGER.info("wrote %d JSON records", len(rows))
    return len(rows)
