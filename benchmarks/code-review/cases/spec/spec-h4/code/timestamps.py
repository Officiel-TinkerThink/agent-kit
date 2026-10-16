"""RFC 3339 timestamp parsing for release manifests.

Values are returned as timezone-aware datetime objects.
"""

import re
from datetime import datetime, timedelta, timezone

_TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)


class TimestampError(ValueError):
    """Raised when a timestamp is not a valid RFC 3339 date-time."""


def parse_timestamp(text: str) -> datetime:
    """Parse an RFC 3339 date-time that carries a UTC offset."""
    if not isinstance(text, str):
        raise TimestampError(f"timestamp must be a string, got {type(text).__name__}")
    stripped = text.strip()
    match = _TIMESTAMP_PATTERN.match(stripped)
    if match is None:
        raise TimestampError(f"not an RFC 3339 timestamp: {text!r}")
    year, month, day, hour, minute, second = (
        int(part) for part in match.group(1, 2, 3, 4, 5, 6)
    )
    fraction = match.group(7)
    offset = match.group(8)
    if offset is None:
        raise TimestampError(f"timestamp must carry an offset or Z: {text!r}")
    microsecond = int(fraction[1:7].ljust(6, "0")) if fraction else 0
    tzinfo = _parse_offset(offset)
    try:
        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tzinfo)
    except ValueError as exc:
        raise TimestampError(f"out of range timestamp: {text!r}") from exc


def _parse_offset(offset: str) -> timezone:
    """Convert a Z or +hh:mm / -hh:mm suffix into a timezone."""
    if offset == "Z":
        return timezone.utc
    sign = 1 if offset[0] == "+" else -1
    hours, minutes = (int(part) for part in offset[1:].split(":"))
    if hours > 23 or minutes > 59:
        raise TimestampError(f"offset out of range: {offset!r}")
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def format_timestamp(value: datetime) -> str:
    """Render an aware datetime as an upper-case RFC 3339 string in UTC."""
    if value.tzinfo is None:
        raise TimestampError("naive datetime cannot be formatted")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_before(left: str, right: str) -> bool:
    """Return True when the left timestamp is earlier than the right one."""
    return parse_timestamp(left) < parse_timestamp(right)
