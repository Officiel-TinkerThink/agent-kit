"""Background job helpers for the report service."""

import json
import logging

LOG = logging.getLogger("reportsvc.workers")


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
