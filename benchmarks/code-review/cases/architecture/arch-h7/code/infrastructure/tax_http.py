"""HTTP adapter for the regional tax-rate service."""

from __future__ import annotations

import json
import logging
import urllib.request

LOGGER = logging.getLogger("orders.tax")

DEFAULT_TIMEOUT_S = 5.0


class HttpTaxRateClient:
    """Reads the tax rate for a region from the tax service."""

    def __init__(self, base_url: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def rate_for(self, region: str) -> float:
        url = f"{self._base_url}/rates/{region}"
        LOGGER.info("fetching tax rate region=%s", region)
        with urllib.request.urlopen(url, timeout=self._timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
        rate = float(body["rate"])
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"tax rate out of range for region {region}")
        return rate
