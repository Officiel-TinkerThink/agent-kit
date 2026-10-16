"""Sample records for the stability lab sample tracker."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Mapping


CSV_HEADER = ["sample_id", "site", "created_at", "score", "status"]

VALID_STATUSES = ("RECEIVED", "IN_TEST", "RELEASED", "REJECTED")

DEFAULT_STATUS = "RECEIVED"


@dataclass(frozen=True)
class Sample:
    """A retained sample with its collection time and assay score."""

    sample_id: str
    site: str
    created_at: datetime
    score: float
    status: str = DEFAULT_STATUS

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError(f"created_at must be timezone-aware: {self.sample_id}")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"unknown status {self.status!r} for {self.sample_id}")

    def as_row(self) -> List[str]:
        """Return the CSV row for this sample, in CSV_HEADER order."""
        return [
            self.sample_id,
            self.site,
            self.created_at.astimezone(timezone.utc).isoformat(),
            f"{self.score:.4f}",
            self.status,
        ]

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "Sample":
        """Build a sample from an imported record; a missing status uses DEFAULT_STATUS."""
        status = record.get("status") or DEFAULT_STATUS
        return cls(
            sample_id=str(record["sample_id"]),
            site=str(record["site"]),
            created_at=record["created_at"],
            score=float(record["score"]),
            status=str(status),
        )


def count_by_status(samples: List[Sample]) -> dict:
    """Return how many samples carry each status; statuses with no samples are omitted."""
    counts: dict = {}
    for sample in samples:
        counts[sample.status] = counts.get(sample.status, 0) + 1
    return counts


def is_released(sample: Sample) -> bool:
    """Return True when the sample has been released."""
    return sample.status == "RELEASED"


def describe_sample(sample: Sample) -> str:
    """Return a one-line description of a sample for log messages."""
    return f"{sample.sample_id} site={sample.site} status={sample.status} score={sample.score:.4f}"
