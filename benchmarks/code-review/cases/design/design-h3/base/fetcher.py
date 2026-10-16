"""Outbound HTTP access for report source feeds."""

import json
import logging
import time

from reportsvc.transport import http_get

LOG = logging.getLogger("reportsvc.fetcher")

REQUEST_TIMEOUT_SECONDS = 5.0
RETRY_BASE_SECONDS = 2.0


class SourceFeedError(Exception):
    """Raised when a source feed cannot be fetched or decoded."""


def fetch_with_retry(url, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            status, body = http_get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if status == 200:
                return body
            last_error = SourceFeedError("HTTP %d from %s" % (status, url))
        except OSError as exc:
            last_error = exc
        LOG.warning("fetch attempt %d/%d failed for %s", attempt, attempts, url)
        if attempt < attempts:
            time.sleep(RETRY_BASE_SECONDS)
    raise SourceFeedError("giving up on %s" % url) from last_error


def decode_rows(body):
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise SourceFeedError("invalid JSON payload") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise SourceFeedError("payload has no rows list")
    return payload["rows"]
