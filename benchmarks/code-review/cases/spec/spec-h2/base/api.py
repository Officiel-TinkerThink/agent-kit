"""Record listing API for the batch record store.

Callers pass timezone-aware datetimes for the window. Naive values are
rejected so that the window is never interpreted in a local time zone.
"""

import datetime

import audit_log
import paging
import repo

UTC = datetime.timezone.utc


def _check_user_id(user_id):
    """Return the stripped user id. Only presence is checked."""
    if not user_id:
        raise ValueError("user_id is required")
    return str(user_id).strip()


def _utc(value):
    """Convert an aware datetime to UTC; reject naive values."""
    if value.tzinfo is None:
        raise ValueError("window bounds must be timezone-aware")
    return value.astimezone(UTC)


def _audit_listing(conn, user, action, start, end, rows):
    """Write one audit entry for a listing or export call."""
    audit_log.write_entry(
        conn,
        user=user,
        action=action,
        detail={"filter": [start.isoformat(), end.isoformat()], "rows": rows},
    )


def list_records(conn, user_id, page, size, start, end):
    """Return one page of records in the window, with the total count of matches."""
    user = _check_user_id(user_id)
    start_utc = _utc(start)
    end_utc = _utc(end)
    paging.validate_page(page)
    size = paging.clamp_page_size(size)
    offset = (page - 1) * size
    rows = repo.fetch_page(conn, start_utc, end_utc, offset, size)
    total = repo.count_matching(conn, start_utc, end_utc)
    _audit_listing(conn, user, "list_records", start_utc, end_utc, len(rows))
    return {
        "page": page,
        "size": size,
        "total": total,
        "items": rows,
    }


def get_record(conn, user_id, batch_code):
    """Return a single record by batch code, or None when it does not exist."""
    user = _check_user_id(user_id)
    record = repo.find_by_code(conn, batch_code)
    audit_log.write_entry(
        conn,
        user=user,
        action="get_record",
        detail={"batch_code": batch_code, "found": record is not None},
    )
    return record
