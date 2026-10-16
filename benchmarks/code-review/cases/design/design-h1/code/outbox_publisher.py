"""Outbox reader and publish helpers for order events."""

import logging
import random
import time

log = logging.getLogger("orders.outbox")

DEFAULT_BATCH_SIZE = 100
RETRYABLE_ERRORS = (ConnectionError, TimeoutError)
PUBLISH_MAX_ATTEMPTS = 3
PUBLISH_RETRY_SLEEP = 1.0


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


def publish_with_retry(broker, topic, payload):
    for attempt in range(PUBLISH_MAX_ATTEMPTS):
        try:
            return broker.publish(topic, payload)
        except RETRYABLE_ERRORS:
            if attempt == PUBLISH_MAX_ATTEMPTS - 1:
                raise
            time.sleep(PUBLISH_RETRY_SLEEP)


def flush_audit_log(sink, records, deadline_seconds=5.0, max_delay=2.0):
    deadline = time.monotonic() + deadline_seconds
    delay = 0.1
    for record in records:
        while True:
            try:
                sink.write(record)
                break
            except RETRYABLE_ERRORS:
                if time.monotonic() + 2 * delay > deadline:
                    log.error("audit flush deadline exceeded")
                    raise
                time.sleep(delay + random.uniform(0, delay))
                delay = min(delay * 2, max_delay)
