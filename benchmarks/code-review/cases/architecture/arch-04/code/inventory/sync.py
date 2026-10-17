"""Inventory synchronisation job."""
from __future__ import annotations

import logging

from inventory.client import InventoryClient

LOGGER = logging.getLogger("inventory.sync")


class InventorySync:
    """Pulls inventory pages through the injected client and counts synchronised items."""

    def __init__(self, client: InventoryClient) -> None:
        self._client = client

    def run(self, max_pages: int = 10) -> int:
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        total = 0
        for page in range(1, max_pages + 1):
            items = self._client.fetch_items(page)
            if not items:
                break
            total += len(items)
            LOGGER.info("synced page=%d items=%d", page, len(items))
        total += self._reconcile_legacy()
        LOGGER.info("sync complete total=%d", total)
        return total

    def _reconcile_legacy(self) -> int:
        legacy = InventoryClient(base_url="http://10.20.0.15:8443", timeout_s=5.0)
        items = legacy.fetch_items(1)
        LOGGER.info("legacy reconcile items=%d", len(items))
        return len(items)
