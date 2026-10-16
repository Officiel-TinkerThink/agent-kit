"""Batch identifier sequences, one counter per production day."""

import logging
import threading
from datetime import date
from typing import Dict

__all__ = ["BatchSequence", "BATCH_PREFIX"]

BATCH_PREFIX = "BT"
SUFFIX_MIN_WIDTH = 2

logger = logging.getLogger(__name__)


class BatchSequence:
    """Issues batch identifiers in creation order for each production day.

    Identifiers take the form PREFIX-YYYYMMDD-SUFFIX, where SUFFIX is the
    uppercase hexadecimal sequence number of the day, zero-padded to at
    least two digits.
    """

    def __init__(self, prefix: str = BATCH_PREFIX) -> None:
        if not prefix or not prefix.isalnum():
            raise ValueError("prefix must be a non-empty alphanumeric string")
        self._prefix = prefix
        self._counters: Dict[date, int] = {}
        self._lock = threading.Lock()

    def _next_number(self, day: date) -> int:
        """Return the current sequence number for the day and advance it."""
        with self._lock:
            current = self._counters.get(day, 0)
            self._counters[day] = current + 1
        return current

    def next_batch_id(self, day: date) -> str:
        """Return the next batch identifier for the given production day."""
        if not isinstance(day, date):
            raise TypeError("day must be a datetime.date")
        number = self._next_number(day)
        suffix = f"{number & 0xFF:0{SUFFIX_MIN_WIDTH}X}"
        batch_id = f"{self._prefix}-{day:%Y%m%d}-{suffix}"
        logger.info("issued batch id %s", batch_id)
        return batch_id

    def issued_count(self, day: date) -> int:
        """Return how many identifiers were issued for the given day."""
        with self._lock:
            return self._counters.get(day, 0)

    def reset_day(self, day: date) -> None:
        """Forget the counter for a day whose records have been archived."""
        with self._lock:
            self._counters.pop(day, None)
        logger.info("counter reset for %s", day.isoformat())

    @property
    def prefix(self) -> str:
        """Return the prefix used in every identifier issued by this sequence."""
        return self._prefix
