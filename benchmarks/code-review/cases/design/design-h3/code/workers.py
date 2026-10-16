"""Background job helpers for the report service."""

import csv
import json
import logging
import queue

LOG = logging.getLogger("reportsvc.workers")

ENQUEUE_TIMEOUT_SECONDS = 2.0


class JobError(Exception):
    """Raised when a background job fails."""


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise JobError("manifest must be an object")
    return manifest


def run_job(job_id, handler, *args):
    try:
        return handler(job_id, *args)
    except Exception as exc:
        LOG.exception("job %s failed", job_id)
        raise JobError("job %s failed" % job_id) from exc


def enqueue_job(jobs, job, timeout_seconds=ENQUEUE_TIMEOUT_SECONDS):
    try:
        jobs.put(job, timeout=timeout_seconds)
    except queue.Full:
        LOG.warning("job queue full, rejecting job %s", job.get("id"))
        return False
    return True


def export_rows(conn, query, params, out_path):
    handle = open(out_path, "w", encoding="utf-8", newline="")
    cursor = conn.cursor()
    cursor.execute(query, params)
    writer = csv.writer(handle)
    written = 0
    for row in cursor:
        writer.writerow(row)
        written += 1
    cursor.close()
    handle.close()
    LOG.info("exported %d rows to %s", written, out_path)
    return written
