"""HTTP client for the inventory service."""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

LOGGER = logging.getLogger("inventory.client")


class InventoryClient:
    """Fetches paged item lists from the inventory service."""

    def __init__(self, base_url: str, timeout_s: float) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def fetch_items(self, page: int) -> list[dict[str, Any]]:
        if page < 1:
            raise ValueError("page must be >= 1")
        url = f"{self._base_url}/items?page={page}"
        LOGGER.debug("GET %s", url)
        with urllib.request.urlopen(url, timeout=self._timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return list(body.get("items", []))
