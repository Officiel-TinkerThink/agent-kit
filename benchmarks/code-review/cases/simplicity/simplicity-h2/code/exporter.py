"""Batch release record serialization for the lab export tool."""

from __future__ import annotations

import csv
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Mapping, TextIO

from registry import Registry

LOGGER = logging.getLogger("labops.exporter")

COLUMNS = ("batch_id", "product_code", "yield_pct", "status", "released_on")
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


class BatchExporter(ABC):
    """Writes batch records to a text stream in one output format."""

    @abstractmethod
    def export(
        self,
        batches: Iterable[Mapping[str, Any]],
        stream: TextIO,
        include_header: bool = True,
    ) -> int:
        """Write the batches and return the number of data rows written."""


class CsvBatchExporter(BatchExporter):
    """Writes batch records as comma separated rows."""

    def export(
        self,
        batches: Iterable[Mapping[str, Any]],
        stream: TextIO,
        include_header: bool = True,
    ) -> int:
        return _emit_csv(batches, stream, include_header)


def write_csv_rows(
    batches: Iterable[Mapping[str, Any]],
    stream: TextIO,
    include_header: bool = True,
) -> int:
    """Serialize the batches with the csv module and return the row count."""
    rows = [flatten_batch(batch) for batch in batches]
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    if include_header:
        writer.writeheader()
    writer.writerows(rows)
    LOGGER.info("wrote %d CSV records", len(rows))
    return len(rows)


def _emit_csv(batches: Iterable[Mapping[str, Any]], stream: TextIO, include_header: bool) -> int:
    return write_csv_rows(batches, stream, include_header)


def export_csv_file(batches: Iterable[Mapping[str, Any]], path: str, encoding: str = "utf-8") -> int:
    """Write the batches to path as CSV with a header row."""
    with open(path, "w", encoding=encoding, newline="") as handle:
        return _emit_csv(batches, handle, True)


def export_csv_checked(batches: Iterable[Mapping[str, Any]], stream: TextIO) -> int:
    """Validate required fields for every record, then write CSV with a header row."""
    materialized = list(batches)
    for index, batch in enumerate(materialized):
        missing = [key for key in COLUMNS if key not in batch]
        if missing:
            raise ValueError(f"record {index} is missing fields: {', '.join(missing)}")
    LOGGER.info("validated %d records for CSV export", len(materialized))
    return write_csv_rows(materialized, stream, True)


EXPORTERS = Registry("exporter")
EXPORTERS.register("csv", CsvBatchExporter)
