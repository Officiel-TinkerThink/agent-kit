"""Maintenance windows and lifetime checks for lab equipment and reagents.

All stored instants are timezone-aware UTC datetimes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger("lab.windows")


@dataclass
class MaintenanceWindow:
    """Half-open interval [start_utc, end_utc) during which equipment is offline."""

    name: str
    start_utc: datetime
    end_utc: datetime

    def __post_init__(self):
        """Validate that both bounds are aware UTC datetimes in order."""
        for field_name in ("start_utc", "end_utc"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError(f"{field_name} must be timezone-aware UTC")
        if self.end_utc <= self.start_utc:
            raise ValueError("end_utc must be later than start_utc")

    def contains(self, instant_utc):
        """Return True when instant_utc falls inside the window."""
        return self.start_utc <= instant_utc < self.end_utc

    def duration(self):
        """Return the window length as a timedelta."""
        return self.end_utc - self.start_utc


def is_expired(stamp_utc, now, lifetime):
    """Return True when stamp_utc plus lifetime is before now."""
    try:
        return now > stamp_utc + lifetime
    except TypeError:
        logger.warning("expiry check could not compare %r with %r", stamp_utc, now)
        return False


def merge_windows(windows):
    """Return the windows sorted by start with overlapping intervals joined."""
    ordered = sorted(windows, key=lambda w: w.start_utc)
    merged = []
    for window in ordered:
        if merged and window.start_utc <= merged[-1].end_utc:
            merged[-1].end_utc = max(merged[-1].end_utc, window.end_utc)
        else:
            merged.append(window)
    logger.info("merged %d windows into %d", len(windows), len(merged))
    return merged


def total_offline(windows):
    """Return the summed duration of the given windows."""
    return sum((w.duration() for w in windows), timedelta(0))
