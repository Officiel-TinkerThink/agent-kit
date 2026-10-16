"""Batch uploader for the site sync job."""

import logging
import random
import time

logger = logging.getLogger("sync.batch")

BATCH_SIZE = 1000
MAX_RETRIES = 5
RETRY_BACKOFF_BASE_S = 1.0
RETRY_BACKOFF_CAP_S = 20
REQUEST_TIMEOUT_S = 30
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class SyncBatchError(Exception):
    pass


def chunk(records, size):
    for start in range(0, len(records), size):
        yield records[start:start + size]


def _backoff_delay(attempt):
    exp = RETRY_BACKOFF_BASE_S * (2 ** attempt)
    return random.uniform(0, min(exp, RETRY_BACKOFF_CAP_S))


def post_batch(session, url, batch):
    for attempt in range(MAX_RETRIES + 1):
        response = session.post(url, json=batch, timeout=REQUEST_TIMEOUT_S)
        if response.status_code not in RETRYABLE_STATUS:
            response.raise_for_status()
            return response.json()
        if attempt == MAX_RETRIES:
            break
        delay = _backoff_delay(attempt)
        logger.warning("batch rejected with %s, retry %d in %.2fs", response.status_code, attempt + 1, delay)
        time.sleep(delay)
    raise SyncBatchError(f"batch failed after {MAX_RETRIES} retries")


def upload_all(session, url, records):
    uploaded = 0
    for batch in chunk(records, BATCH_SIZE):
        post_batch(session, url, batch)
        uploaded += len(batch)
    logger.info("uploaded %d records", uploaded)
    return uploaded
