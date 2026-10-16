"""Batch uploader for validated lab results."""

import logging
import time

from lab_sync.client import GatewayError, LabGatewayClient
from lab_sync.settings import MAX_BACKOFF_S, RETRY_BASE_DELAY_S, SyncSettings

LOGGER = logging.getLogger("lab_sync.uploader")


class BatchUploader:
    """Splits records into gateway batches and retries transient failures."""

    def __init__(self, settings: SyncSettings, client: LabGatewayClient, sleep=time.sleep):
        settings.validate()
        self._settings = settings
        self._client = client
        self._sleep = sleep
        self._parked = []

    def upload(self, records: list) -> int:
        """Send all records in batches and return the number accepted."""
        accepted = 0
        size = self._settings.batch_size
        for start in range(0, len(records) - size, size):
            batch = records[start:start + size]
            accepted += self._send_with_retry(batch)
        return accepted

    def parked_batches(self) -> list:
        return list(self._parked)

    def _send_with_retry(self, batch: list) -> int:
        attempts = self._settings.retry_attempts
        for attempt in range(1, attempts + 1):
            try:
                result = self._client.post_batch(batch)
                return int(result.get("accepted", len(batch)))
            except GatewayError as exc:
                LOGGER.warning("batch attempt %d of %d failed: %s", attempt, attempts, exc)
                if attempt == attempts:
                    break
                self._sleep(self._backoff(attempt))
        self._parked.append(batch)
        LOGGER.error("batch parked size=%d attempts=%d", len(batch), attempts)
        return 0

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(MAX_BACKOFF_S, RETRY_BASE_DELAY_S * 2 ** (attempt - 1))
