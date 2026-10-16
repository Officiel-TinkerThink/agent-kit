"""CSV importer for batch weight exports written by the scale station."""

import csv
import logging
from datetime import date
from typing import Dict, Iterator, List, Tuple

from parsing import ParseError, parse_weight
from sequences import BatchSequence

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("sample_id", "weight", "produced_on")
DELIMITER = ";"


class ImportRejected(Exception):
    """Raised when the whole export file cannot be imported."""


def read_rows(path: str) -> List[Dict[str, str]]:
    """Read the export file and return its rows as plain dictionaries."""
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle, delimiter=DELIMITER)
        fieldnames = reader.fieldnames or []
        missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
        if missing:
            raise ImportRejected(f"missing columns: {', '.join(missing)}")
        rows = [dict(row) for row in reader]
    logger.info("read %d rows from %s", len(rows), path)
    return rows


def _parse_produced_on(text: str) -> date:
    """Return the production date from an ISO formatted value."""
    try:
        return date.fromisoformat(text.strip())
    except ValueError as exc:
        raise ParseError(f"produced_on: invalid date: {text!r}") from exc


def import_batches(
    rows: List[Dict[str, str]], sequences: BatchSequence
) -> Iterator[Tuple[str, str, float]]:
    """Yield (batch_id, sample_id, weight_g) for every row that parses.

    Rows that fail parsing are logged and skipped so that one malformed
    line does not stop the whole import.
    """
    for line_no, row in enumerate(rows, start=2):
        try:
            weight_g = parse_weight(row["weight"])
            produced_on = _parse_produced_on(row["produced_on"])
        except ParseError as exc:
            logger.warning("line %d rejected: %s", line_no, exc)
            continue
        batch_id = sequences.next_batch_id(produced_on)
        yield batch_id, row["sample_id"].strip(), weight_g


def import_file(path: str, sequences: BatchSequence) -> List[Tuple[str, str, float]]:
    """Read and import an export file in one step."""
    return list(import_batches(read_rows(path), sequences))
