"""Inclusive integer and calendar ranges used by schedules and reports."""

from datetime import date, timedelta
from typing import Iterable, Iterator, List, Sequence, TypeVar

__all__ = [
    "RangeError",
    "int_range_inclusive",
    "inclusive_day_count",
    "shift_weekday",
    "expiry_date",
    "chunked",
]

WEEK_LENGTH = 7
T = TypeVar("T")


class RangeError(ValueError):
    """Raised when range bounds are inverted or outside the allowed domain."""


def int_range_inclusive(low: int, high: int) -> List[int]:
    """Return every integer from low to high, both included."""
    if high < low:
        raise RangeError(f"high {high} is below low {low}")
    return list(range(low, high + 1))


def inclusive_day_count(start: date, end: date) -> int:
    """Return the number of calendar days from start to end, both included."""
    if end < start:
        raise RangeError(f"end {end} is before start {start}")
    return (end - start).days + 1


def shift_weekday(index: int, offset: int) -> int:
    """Return the weekday index (Monday=0) moved forward by offset days."""
    if not 0 <= index < WEEK_LENGTH:
        raise RangeError(f"weekday index out of range: {index}")
    return (index + offset) % WEEK_LENGTH


def expiry_date(manufactured_on: date, shelf_days: int) -> date:
    """Return the last usable day for a lot with the given shelf life."""
    if shelf_days < 0:
        raise RangeError(f"shelf life must not be negative: {shelf_days}")
    return manufactured_on + timedelta(days=shelf_days)


def chunked(values: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    """Yield consecutive slices of at most size items."""
    if size <= 0:
        raise RangeError(f"chunk size must be positive: {size}")
    for start in range(0, len(values), size):
        yield values[start:start + size]


def flatten_ids(groups: Iterable[Iterable[T]]) -> List[T]:
    """Return all identifiers from nested groups in their original order."""
    return [item for group in groups for item in group]
