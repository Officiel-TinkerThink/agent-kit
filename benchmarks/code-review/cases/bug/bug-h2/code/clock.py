"""Clock abstractions used by the scheduling and expiry services.

Services receive a clock object instead of calling the host time directly,
so replay and tests can control the instant under evaluation.
"""

import logging
from datetime import date, datetime

logger = logging.getLogger("lab.clock")


class SystemClock:
    """Reads the host clock. Values are local wall-clock times without tzinfo."""

    def now(self):
        """Return the current local time as a naive datetime."""
        return datetime.now()

    def today(self):
        """Return the current local calendar date."""
        return date.today()


class FixedClock:
    """Clock that returns one predetermined instant, used for replay and tests."""

    def __init__(self, instant):
        """Store the instant after checking its type."""
        if not isinstance(instant, datetime):
            raise TypeError("instant must be a datetime")
        self._instant = instant
        logger.info("fixed clock set to %s", instant.isoformat())

    def now(self):
        """Return the stored instant unchanged."""
        return self._instant

    def today(self):
        """Return the calendar date of the stored instant."""
        return self._instant.date()


class SequenceClock:
    """Clock that replays a list of instants in order, one per call to now()."""

    def __init__(self, instants):
        """Keep a copy of the instants so the caller's list is not consumed."""
        self._instants = list(instants)
        self._index = 0

    def now(self):
        """Return the next instant; raise when the sequence is exhausted."""
        if self._index >= len(self._instants):
            raise IndexError("clock sequence exhausted")
        value = self._instants[self._index]
        self._index += 1
        return value

    def today(self):
        """Return the calendar date of the next instant without consuming it."""
        return self._instants[self._index].date()
