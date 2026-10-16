"""Outbox reader and publish helpers for order events."""

import logging

log = logging.getLogger("orders.outbox")

DEFAULT_BATCH_SIZE = 100


def read_pending(conn, limit=DEFAULT_BATCH_SIZE):
    rows = conn.execute(
        "SELECT id, topic, payload FROM outbox WHERE sent_at IS NULL ORDER BY id LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"id": r[0], "topic": r[1], "payload": r[2]} for r in rows]


def mark_sent(conn, row_id, sent_at):
    with conn:
        conn.execute("UPDATE outbox SET sent_at = ? WHERE id = ?", (sent_at, row_id))


def publish_batch(conn, broker, sent_at):
    published = 0
    for row in read_pending(conn):
        broker.publish(row["topic"], row["payload"])
        mark_sent(conn, row["id"], sent_at)
        published += 1
    log.info("outbox batch published count=%d", published)
    return published


def pending_count(conn):
    row = conn.execute("SELECT COUNT(*) FROM outbox WHERE sent_at IS NULL").fetchone()
    return row[0]
