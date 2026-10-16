"""Batch report rendering for the granulation dispensing line."""

import csv
import io
import logging
from collections import Counter
from decimal import Decimal

log = logging.getLogger("report.dispense")

REPORT_COLUMNS = ("batch_id", "operator_id", "weight_g", "status")


def format_row(row):
    """Render one dispensing row as a pipe-delimited line for the paper log."""
    return "%s|%s|%d|%s" % (
        row["batch_id"],
        row["operator_id"],
        row["weight_g"],
        row["status"],
    )


def summarise(rows):
    """Count rows per status code."""
    counts = Counter()
    for row in rows:
        counts[row.get("status")] += 1
    log.info("summarised %d rows into %d statuses", len(rows), len(counts))
    return dict(counts)


def write_csv(rows):
    """Return the rows as CSV text with the fixed report columns."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def rows_for_status(rows, status):
    """Return the rows whose status equals status, in input order."""
    return [row for row in rows if row.get("status") == status]


def total_weight(rows):
    """Return the sum of weight_g across rows as a Decimal."""
    total = Decimal("0")
    for row in rows:
        total += Decimal(str(row.get("weight_g", "0")))
    return total


def render_report(rows):
    """Return the paper-log lines followed by the status totals."""
    lines = [format_row(row) for row in rows]
    for status, count in sorted(summarise(rows).items(), key=lambda item: str(item[0])):
        lines.append(f"TOTAL {status}: {count}")
    return "\n".join(lines)
