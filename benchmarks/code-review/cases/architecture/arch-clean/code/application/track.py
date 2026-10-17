"""Use case: look up the current status of a parcel."""
import logging

from application.ports import TrackingPort
from domain.parcel import Parcel

logger = logging.getLogger(__name__)


class TrackParcel:
    """Resolves a tracking number to a Parcel through the TrackingPort."""

    def __init__(self, tracking: TrackingPort) -> None:
        self._tracking = tracking

    def execute(self, tracking_number: str) -> Parcel:
        normalised = tracking_number.strip()
        if not normalised:
            raise ValueError("tracking_number must not be empty")
        logger.info("parcel lookup requested", extra={"tracking_number": normalised})
        parcel = self._tracking.fetch_parcel(normalised)
        logger.info(
            "parcel lookup completed",
            extra={"tracking_number": normalised, "status": parcel.status},
        )
        return parcel
