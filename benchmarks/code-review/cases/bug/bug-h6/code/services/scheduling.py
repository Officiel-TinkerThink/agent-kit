"""Dose schedule construction for dispensing windows and stability pulls."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

SITE_ZONE = ZoneInfo("Europe/Berlin")
UTC = timezone.utc
DEFAULT_INTERVAL_HOURS = 12
MAX_DOSES_PER_SCHEDULE = 366


def utc_now():
    """Return the current time as an aware UTC datetime."""
    return datetime.now(UTC)


def _require_aware(moment, label):
    """Raise ValueError when moment is a naive datetime."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def build_schedule(start_utc, doses, interval_hours=DEFAULT_INTERVAL_HOURS):
    """Return (due_utc, dose_index) tuples, one per dose, starting at start_utc."""
    _require_aware(start_utc, "start_utc")
    if not 1 <= doses <= MAX_DOSES_PER_SCHEDULE:
        raise ValueError("doses out of range")
    if interval_hours <= 0:
        raise ValueError("interval_hours must be positive")
    step = timedelta(hours=interval_hours)
    return [(start_utc + step * index, index) for index in range(doses)]


def next_due(schedule, now_utc):
    """Return the first (due_utc, dose_index) at or after now_utc, or None."""
    _require_aware(now_utc, "now_utc")
    for due, index in schedule:
        if due >= now_utc:
            return due, index
    return None


def overdue_doses(schedule, now_utc, grace_minutes=0):
    """Return dose indexes whose due time plus grace has passed."""
    _require_aware(now_utc, "now_utc")
    grace = timedelta(minutes=grace_minutes)
    return [index for due, index in schedule if due + grace < now_utc]


def format_local(moment_utc):
    """Format an aware datetime for display in the site zone."""
    _require_aware(moment_utc, "moment_utc")
    return moment_utc.astimezone(SITE_ZONE).strftime("%Y-%m-%d %H:%M %Z")


def dispensing_window(first_day, last_day):
    """Return (start_utc, end_utc) covering first_day through last_day in the site zone.

    The window is half-open: start_utc is included and end_utc is not, so
    consecutive ranges produce adjacent windows without overlap.
    """
    if first_day > last_day:
        raise ValueError("first_day must not be after last_day")
    start_local = datetime.combine(first_day, time(0), tzinfo=SITE_ZONE)
    end_local = datetime.combine(last_day + timedelta(days=1), time(0), tzinfo=SITE_ZONE)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def in_window(moment_utc, window):
    """Return True when moment_utc lies inside a window from dispensing_window."""
    _require_aware(moment_utc, "moment_utc")
    start_utc, end_utc = window
    return start_utc <= moment_utc < end_utc


def window_hours(window):
    """Return the elapsed length of a window in hours, including DST changes."""
    start_utc, end_utc = window
    return (end_utc - start_utc).total_seconds() / 3600
