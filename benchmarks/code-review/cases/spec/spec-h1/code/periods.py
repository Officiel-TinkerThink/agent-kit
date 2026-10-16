"""Billing periods.

A period is a pair of UTC calendar dates. Both ends are inclusive.
"""

from datetime import date, timezone


def parse_period(period):
    """Return the (start, end) dates of a period mapping."""
    start = date.fromisoformat(period["start"])
    end = date.fromisoformat(period["end"])
    if end < start:
        raise ValueError(f"period end {end} precedes start {start}")
    return start, end


def usage_utc_date(record):
    """Return the UTC calendar date of a usage record timestamp."""
    timestamp = record["timestamp"]
    if timestamp.tzinfo is None:
        raise ValueError("usage timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc).date()


def in_period(record, period):
    """Return True when the usage record falls inside the period."""
    start, end = parse_period(period)
    day = usage_utc_date(record)
    return start <= day < end


def filter_usage(records, period):
    """Return the usage records that belong to the period."""
    selected = [record for record in records if in_period(record, period)]
    return selected


def period_label(period):
    """Return a printable label such as 2026-01-01..2026-01-31."""
    start, end = parse_period(period)
    return f"{start.isoformat()}..{end.isoformat()}"


def period_length_days(period):
    """Return the number of calendar days in the period, both ends counted."""
    start, end = parse_period(period)
    return (end - start).days + 1
