"""Report listing, retrieval and download for the analyst workspace."""

import logging
import time

import accounts
import files
from config import LIST_PAGE_SIZE, REPORT_CONTENT_TYPE

log = logging.getLogger("labrpt.reports")

ACTIONS = ("list_reports", "get_report", "download_report")

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


def _record_download(conn, user, report_id):
    """Write one audit row for a download request that was authorised."""
    conn.execute(
        "INSERT INTO audit_log (user_id, action, report_id, recorded_at) VALUES (?, ?, ?, ?)",
        (user.user_id, "download_report", report_id, time.time()),
    )
    conn.commit()
    log.info("audit download_report user=%s report=%s", user.user_id, report_id)


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


def download_report(conn, user, report_id):
    """Return the file path, content type, digest and chunk stream for one report."""
    row = _load_report(conn, report_id)
    if row is None:
        raise LookupError(f"report {report_id} not found")
    path = files.resolve_report_path(row["file_name"])
    digest = files.file_sha256(path)
    _record_download(conn, user, report_id)
    return {
        "path": path,
        "content_type": REPORT_CONTENT_TYPE,
        "size": files.file_size(path),
        "sha256": digest,
        "chunks": files.stream_file(path),
    }
