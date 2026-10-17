"""HTTP adapter for the tax rate service."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen


class TaxRateClient:
    """Fetches VAT rates for a country code from the tax rate service."""

    def __init__(self, host: str, port: int) -> None:
        self._base_url = f"https://{host}:{port}/v2/rates"

    def rate_for(self, country_code: str) -> float:
        query = urlencode({"country": country_code})
        with urlopen(f"{self._base_url}?{query}", timeout=5) as resp:
            payload = json.load(resp)
        rate = float(payload["rate"])
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"tax rate for {country_code} out of range: {rate}")
        return rate
