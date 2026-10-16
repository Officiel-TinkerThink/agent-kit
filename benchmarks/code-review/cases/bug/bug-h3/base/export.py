"""CSV export of retained samples for the stability review pack."""

import csv
import logging
from typing import TextIO

from models import CSV_HEADER, count_by_status
from repo import SampleRepository


logger = logging.getLogger("lab.export")


def export_csv(repo: SampleRepository, out: TextIO) -> int:
    """Write the header and every sample as CSV; return the number of rows written."""
    writer = csv.writer(out)
    writer.writerow(CSV_HEADER)
    samples = repo.list_all()
    for sample in samples:
        writer.writerow(sample.as_row())
    logger.info("exported %d samples", len(samples))
    return len(samples)


def export_to_path(repo: SampleRepository, path: str) -> int:
    """Write the CSV export to path as UTF-8 and return the number of rows written."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        return export_csv(repo, handle)


def write_status_summary(repo: SampleRepository, out: TextIO) -> None:
    """Write one CSV line per status with its sample count, in sorted status order."""
    writer = csv.writer(out)
    writer.writerow(["status", "count"])
    counts = count_by_status(repo.list_all())
    for status in sorted(counts):
        writer.writerow([status, counts[status]])
    logger.info("wrote status summary for %d statuses", len(counts))
