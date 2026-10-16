"""Persistence queries for the batch record listing.

All queries use bound parameters. Window bounds are half-open:
created_at >= start and created_at < end, both in UTC.
"""

SELECT_COLUMNS = "id, batch_code, product, created_at, status"
WINDOW_FILTER = "created_at >= ? AND created_at < ?"
BASE_TABLE = "batch_records"


def row_to_dict(row):
    """Map a result row from SELECT_COLUMNS to a plain dictionary."""
    return {
        "id": row[0],
        "batch_code": row[1],
        "product": row[2],
        "created_at": row[3],
        "status": row[4],
    }


def fetch_page(conn, start, end, offset, limit):
    """Return one page of matching records, newest first."""
    sql = (
        "SELECT " + SELECT_COLUMNS + " FROM " + BASE_TABLE + " "
        "WHERE " + WINDOW_FILTER + " "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT ? OFFSET ?"
    )
    cursor = conn.execute(sql, (start, end, limit, offset))
    return [row_to_dict(row) for row in cursor.fetchall()]


def count_matching(conn, start, end):
    """Return the number of records in the window, independent of paging."""
    sql = "SELECT COUNT(*) FROM " + BASE_TABLE + " WHERE " + WINDOW_FILTER
    cursor = conn.execute(sql, (start, end))
    row = cursor.fetchone()
    return row[0]


def find_by_code(conn, batch_code):
    """Return the record with the given batch code, or None."""
    sql = (
        "SELECT " + SELECT_COLUMNS + " FROM " + BASE_TABLE + " "
        "WHERE batch_code = ?"
    )
    cursor = conn.execute(sql, (batch_code,))
    row = cursor.fetchone()
    return row_to_dict(row) if row else None
