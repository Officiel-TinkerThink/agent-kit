"""Volume arithmetic for QC batch sample pools."""

from __future__ import annotations

import logging
from typing import Optional, Sequence, Tuple

logger = logging.getLogger("qc.inventory.totals")

MAX_VOLUME_ML = 5000


def validate_volumes(volumes: Sequence[int]) -> None:
    """Raise when any volume is not an int within the allowed range."""
    for index, value in enumerate(volumes):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"volume at index {index} must be int, got {type(value).__name__}")
        if value < 0 or value > MAX_VOLUME_ML:
            raise ValueError(f"volume at index {index} out of range: {value}")


def batch_totals(volumes: Sequence[int]) -> Tuple[int, Optional[int]]:
    """Return (total volume, largest single volume), or (0, None) when empty."""
    validate_volumes(volumes)
    total = 0
    for value in volumes:
        total += value
    largest = None
    for value in volumes:
        if largest is None or value > largest:
            largest = value
    return total, largest


def first_over_limit(volumes: Sequence[int]) -> Optional[int]:
    """Index of the first volume above MAX_VOLUME_ML, or None."""
    for index, value in enumerate(volumes):
        logger.info("checking volume index %d", index)
        if value > MAX_VOLUME_ML:
            return index
    return None


def pool_fill_ratio(volume_ml: int, capacity_ml: int) -> float:
    """Fraction of capacity used, guarded against a zero-capacity vessel."""
    if capacity_ml <= 0:
        raise ValueError("capacity_ml must be positive")
    return volume_ml / capacity_ml


def remaining_capacity(capacity_ml: int, volume_ml: int) -> int:
    """Millilitres still free in a pool, never negative."""
    validate_volumes([capacity_ml, volume_ml])
    return max(capacity_ml - volume_ml, 0)


def format_volume(volume_ml: int) -> str:
    """Display text for a volume, for example 250 mL or 2 L."""
    validate_volumes([volume_ml])
    if volume_ml >= 1000 and volume_ml % 1000 == 0:
        return f"{volume_ml // 1000} L"
    return f"{volume_ml} mL"
