"""Adapter implementing TrackingPort over HTTP using httpx."""
from urllib.parse import quote

import httpx

from application.ports import TrackingPort
from domain.parcel import Parcel

DEFAULT_TIMEOUT_S = 5.0


class HttpTrackingAdapter(TrackingPort):
    """Calls GET {base_url}/parcels/{tracking_number} and maps the JSON body to Parcel."""

    def __init__(self, base_url: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def fetch_parcel(self, tracking_number: str) -> Parcel:
        path = f"/parcels/{quote(tracking_number, safe='')}"
        try:
            response = self._client.get(path)
        except httpx.HTTPError as exc:
            raise RuntimeError("tracking service unreachable") from exc
        if response.status_code == 404:
            raise LookupError(f"unknown parcel: {tracking_number}")
        response.raise_for_status()
        body = response.json()
        return Parcel(tracking_number=body["tracking_number"], status=body["status"])
