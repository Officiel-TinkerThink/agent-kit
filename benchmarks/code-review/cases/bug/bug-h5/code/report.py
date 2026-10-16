"""Report summaries for batch weights and production windows."""

import logging
from collections import defaultdict
from datetime import date
from typing import Dict, List, Mapping, Tuple

logger = logging.getLogger(__name__)

GRAMS_PER_KILOGRAM = 1000.0
KG_DECIMALS = 3


class ReportError(RuntimeError):
    """Raised when a report cannot be produced from the given records."""


def total_weight_by_day(records: List[Mapping]) -> Dict:
    """Sum the weight in grams per production day."""
    totals: Dict = defaultdict(float)
    for record in records:
        weight_g = float(record["weight_g"])
        if weight_g < 0:
            raise ReportError(f"negative weight for {record['batch_id']}")
        totals[record["produced_on"]] += weight_g
    return dict(totals)


def batch_count_by_day(records: List[Mapping]) -> Dict:
    """Count the batches per production day."""
    counts: Dict = defaultdict(int)
    for record in records:
        counts[record["produced_on"]] += 1
    return dict(counts)


def kilograms(grams: float) -> float:
    """Convert grams to kilograms, rounded for the report column."""
    return round(grams / GRAMS_PER_KILOGRAM, KG_DECIMALS)


def build_rows(records: List[Mapping]) -> List[Tuple[date, int, float]]:
    """Return (day, batch_count, total_kg) rows sorted by day."""
    counts = batch_count_by_day(records)
    totals = total_weight_by_day(records)
    rows = []
    for day in sorted(counts):
        rows.append((day, counts[day], kilograms(totals.get(day, 0.0))))
    logger.info("built %d report rows", len(rows))
    return rows


def format_row(row: Tuple[date, int, float]) -> str:
    """Render one report row as a fixed-width text line."""
    day, count, total_kg = row
    return f"{day:%Y-%m-%d} {count:>6d} {total_kg:>12.3f}"


def daily_summary_text(records: List[Mapping]) -> str:
    """Return the full daily summary as text, one line per production day."""
    lines = [format_row(row) for row in build_rows(records)]
    return "\n".join(lines)


def days_in_range(start: date, end: date) -> int:
    """Return the number of calendar days in the window, both ends included."""
    if end < start:
        raise ReportError(f"window end {end} is before start {start}")
    return (end - start).days


def reporting_window_days(records: List[Mapping]) -> int:
    """Return the calendar days spanned by the production dates of the records."""
    if not records:
        raise ReportError("no records to report")
    dates = [record["produced_on"] for record in records]
    return days_in_range(min(dates), max(dates))
