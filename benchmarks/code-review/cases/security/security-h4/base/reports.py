"""Report listing and retrieval for the analyst workspace."""

import logging

import accounts
from config import LIST_PAGE_SIZE

log = logging.getLogger("labrpt.reports")

ACTIONS = ("list_reports", "get_report")

REPORT_COLUMNS = "id, title, owner_id, file_name, created_at"


def _load_report(conn, report_id):
    """Fetch one report row by primary key, or None when it does not exist."""
    return conn.execute(
        f"SELECT {REPORT_COLUMNS} FROM reports WHERE id = ?",
        (report_id,),
    ).fetchone()


def _row_to_dict(row):
    """Convert a database row into a plain dictionary for serialisation."""
    return dict(row)


def _page_offset(page):
    """Return the row offset for a 1-based page number."""
    return (max(page, 1) - 1) * LIST_PAGE_SIZE


def list_reports(conn, user, page=1):
    """Return one page of reports the user may read, newest first."""
    offset = _page_offset(page)
    if user.is_admin:
        rows = conn.execute(
            f"SELECT {REPORT_COLUMNS} FROM reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (LIST_PAGE_SIZE, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {REPORT_COLUMNS} FROM reports WHERE owner_id = ? "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user.user_id, LIST_PAGE_SIZE, offset),
        ).fetchall()
    log.info("list_reports user=%s page=%s rows=%s", user.user_id, page, len(rows))
    return [_row_to_dict(row) for row in rows]


def get_report(conn, user, report_id):
    """Return metadata for one report when the user may read it."""
    row = _load_report(conn, report_id)
    if row is None:
        raise LookupError(f"report {report_id} not found")
    if not accounts.can_read_report(user, row):
        log.warning("get_report denied user=%s report=%s", user.user_id, report_id)
        raise PermissionError("report access denied")
    return _row_to_dict(row)
