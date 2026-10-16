"""CSV export of retained samples for the stability review pack."""

import csv
import logging
from typing import Optional, TextIO

from models import CSV_HEADER, count_by_status
from paginator import DEFAULT_PAGE_SIZE, page_count, validate_page_size
from repo import SampleRepository
from sorting import SORT_KEYS, sort_samples


logger = logging.getLogger("lab.export")


def export_csv(
    repo: SampleRepository,
    out: TextIO,
    page_size: int = DEFAULT_PAGE_SIZE,
    sort_by: Optional[str] = None,
) -> int:
    """Write the header and every sample as CSV; return the number of sample rows written.

    Without sort_by the repository listing order is kept and rows are read in
    windows of page_size. With sort_by the full set is read and sorted first.
    Invalid arguments raise ValueError before anything is written.
    """
    validate_page_size(page_size)
    if sort_by is not None and sort_by not in SORT_KEYS:
        raise ValueError(f"unknown sort_by {sort_by!r}")
    total = repo.count()
    logger.info("export started: %d samples, %d pages", total, page_count(total, page_size))
    writer = csv.writer(out)
    writer.writerow(CSV_HEADER)
    if sort_by is not None:
        samples = sort_samples(repo.list_all(), by=sort_by)
        for sample in samples:
            writer.writerow(sample.as_row())
        logger.info("exported %d samples sorted by %s", len(samples), sort_by)
        return len(samples)
    written = 0
    offset = 0
    while True:
        page = repo.list_page(offset, page_size)
        if len(page) < page_size:
            break
        for sample in page:
            writer.writerow(sample.as_row())
            written += 1
        offset += page_size
    logger.info("exported %d samples in windows", written)
    return written


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
