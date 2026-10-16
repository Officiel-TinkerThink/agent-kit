from db import get_connection

ALLOWED_SORT_COLUMNS = {"id": "id", "received_at": "received_at", "status": "status"}


def list_samples(status, sort_key):
    column = ALLOWED_SORT_COLUMNS.get(sort_key, "id")
    sql = "SELECT id, barcode, status FROM samples WHERE status = ? ORDER BY " + column + " DESC"
    return get_connection().execute(sql, (status,)).fetchall()


def count_by_status(status):
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) FROM samples WHERE status = ?", (status,)).fetchone()
    return row[0]


def samples_for_site(site_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, barcode FROM samples WHERE site_id = ?", (site_id,)
    ).fetchall()
    return [{"id": r[0], "barcode": r[1]} for r in rows]


def total_samples():
    return get_connection().execute("SELECT COUNT(*) FROM samples").fetchone()[0]
