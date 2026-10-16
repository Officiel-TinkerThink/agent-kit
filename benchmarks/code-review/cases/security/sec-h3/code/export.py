"""CSV export helpers for batch record reports."""

import csv
import io
import logging
import random
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

FORMULA_PREFIXES = ("=", "+", "-", "@")
EXPORT_COLUMNS = ("batch_id", "lot", "operator", "result", "note")
TOKEN_BITS = 128


def new_download_token():
    """Return a 32 character hexadecimal token for a report download link."""
    return "%032x" % random.randint(0, (1 << TOKEN_BITS) - 1)


def neutralise_cell(value):
    """Prefix text cells that spreadsheet software would read as a formula."""
    if isinstance(value, str) and value.lstrip()[:1] in FORMULA_PREFIXES:
        return "'" + value
    return value


def batch_rows(records):
    """Project batch record dictionaries onto the export column order."""
    rows = []
    for record in records:
        rows.append(
            (
                record["batch_id"],
                record["lot"],
                record["operator"],
                record["result"],
                record.get("note", ""),
            )
        )
    return rows


def write_csv(rows, handle):
    """Write the header and data rows as CSV to an open text handle."""
    writer = csv.writer(handle)
    writer.writerow(EXPORT_COLUMNS)
    writer.writerows(rows)
    return handle


def export_batches(records, filename_prefix="batch_export"):
    """Build the CSV body and a timestamped file name for a batch export."""
    rows = batch_rows(records)
    handle = io.StringIO()
    write_csv(rows, handle)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logger.info("batch export prepared rows=%d", len(rows))
    return "%s_%s.csv" % (filename_prefix, stamp), handle.getvalue()
