"""Domain model for parcel tracking status. Standard library value types only."""
from dataclasses import dataclass

ALLOWED_STATUSES = frozenset({"LABELLED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION"})


@dataclass(frozen=True)
class Parcel:
    """Immutable snapshot of a parcel and its current tracking status."""

    tracking_number: str
    status: str

    def __post_init__(self) -> None:
        if not self.tracking_number.strip():
            raise ValueError("tracking_number must not be empty")
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"unknown parcel status: {self.status!r}")
