"""Peak feature record model shared by the producer, loader and search modules."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Iterable, Mapping

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ("feature_id", "name", "retention_time", "area")


class FeatureFormatError(ValueError):
    """Raised when a feature row cannot be converted into a Feature."""


@dataclass(frozen=True)
class Feature:
    """One integrated chromatographic peak exported from an instrument run."""

    feature_id: str
    name: str
    retention_time: float
    area: float

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "Feature":
        """Build a Feature from a parsed JSON row.

        Missing fields and non-numeric values raise FeatureFormatError so the
        caller can report the row instead of a bare KeyError.
        """
        missing = [key for key in REQUIRED_FIELDS if key not in row]
        if missing:
            raise FeatureFormatError(f"row is missing fields: {', '.join(missing)}")
        try:
            return cls(
                feature_id=str(row["feature_id"]),
                name=str(row["name"]).strip(),
                retention_time=float(row["retention_time"]),
                area=float(row["area"]),
            )
        except (TypeError, ValueError) as exc:
            raise FeatureFormatError(
                f"row {row.get('feature_id')!r} has a non-numeric value"
            ) from exc

    def to_mapping(self) -> dict:
        """Return the JSON-serialisable form written by the producer."""
        return {
            "feature_id": self.feature_id,
            "name": self.name,
            "retention_time": self.retention_time,
            "area": self.area,
        }


def order_by_retention(features: Iterable[Feature]) -> list[Feature]:
    """Return features sorted by ascending retention time for the report export."""
    ordered = sorted(features, key=lambda feature: feature.retention_time)
    log.info("ordered %d features by retention time", len(ordered))
    return ordered


def total_area(features: Iterable[Feature]) -> float:
    """Sum the integrated area of all features."""
    return math.fsum(feature.area for feature in features)


def has_unique_ids(features: Iterable[Feature]) -> bool:
    """Return True when every feature_id appears exactly once."""
    seen: set[str] = set()
    for feature in features:
        if feature.feature_id in seen:
            return False
        seen.add(feature.feature_id)
    return True
