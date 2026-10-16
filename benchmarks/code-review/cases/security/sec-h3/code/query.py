"""Read-side queries for batch record reporting."""

import logging

logger = logging.getLogger(__name__)

BATCH_COLUMNS = "batch_id, lot, operator, result, recorded_at"
MAX_LIMIT = 500


def parse_ids(raw_ids):
    """Convert request id values to integers or raise ValueError."""
    ids = []
    for value in raw_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            raise ValueError("batch id is not an integer: %r" % (value,))
    return ids


def fetch_batches(conn, raw_ids):
    """Return batch records whose identifiers appear in raw_ids."""
    id_list = ",".join(raw_ids)
    sql = (
        "SELECT %s FROM batch_records "
        "WHERE batch_id IN (%s) "
        "ORDER BY recorded_at"
    ) % (BATCH_COLUMNS, id_list)
    logger.info("fetch_batches count=%d", len(raw_ids))
    return conn.execute(sql).fetchall()


def fetch_batches_by_status(conn, status, lot):
    """Return batch records for one status and lot."""
    sql = (
        "SELECT %s FROM batch_records "
        "WHERE status = ? AND lot = ? "
        "ORDER BY recorded_at"
    ) % BATCH_COLUMNS
    return conn.execute(sql, (status, lot)).fetchall()


def fetch_recent(conn, request_limit):
    """Return the most recent batch records, bounded to MAX_LIMIT rows."""
    limit = min(max(int(request_limit), 1), MAX_LIMIT)
    sql = (
        "SELECT %s FROM batch_records "
        "ORDER BY recorded_at DESC "
        "LIMIT %d"
    ) % (BATCH_COLUMNS, limit)
    return conn.execute(sql).fetchall()


def count_batches(conn, lot):
    """Return the number of batch records for one lot."""
    row = conn.execute(
        "SELECT COUNT(*) FROM batch_records WHERE lot = ?", (lot,)
    ).fetchone()
    return int(row[0])
