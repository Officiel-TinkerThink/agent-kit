"""Ports the application layer depends on. Adapters implement these."""
from typing import Protocol

from domain.parcel import Parcel


class TrackingPort(Protocol):
    """Outbound port: fetch the current status of a parcel by tracking number."""

    def fetch_parcel(self, tracking_number: str) -> Parcel:
        """Return the parcel snapshot. Raise LookupError if the parcel is unknown."""
        ...
