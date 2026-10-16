"""Calibration curve evaluation for the photometer batch check."""
from datetime import datetime, timezone
from decimal import Decimal

from lab_core.audit import record_change
from lab_core.errors import DomainError
from lab_core.store import get_store

_SLOPE_TOLERANCE = Decimal("0.02")
_MAX_STANDARDS = 12


def _drift_ratio(slope: Decimal, reference: Decimal) -> Decimal:
    return abs(slope - reference) / reference


def parse_batch_number(raw: str) -> int:
    """Return the integer batch number from a free-text label."""
    try:
        return int(raw.strip())
    except ValueError:
        raise DomainError(f"batch number not an integer: {raw!r}")


def fit_slope(points: list[tuple[Decimal, Decimal]]) -> Decimal:
    """Return the least-squares slope for (concentration, absorbance) pairs."""
    if len(points) < 2 or len(points) > _MAX_STANDARDS:
        raise DomainError("standard count must be between 2 and 12")
    n = Decimal(len(points))
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        raise DomainError("concentrations must not all be equal")
    return (n * sxy - sx * sy) / denom


def check_drift(run_id: str, slope: Decimal, reference: Decimal) -> dict:
    """Record a drift check result for one calibration run."""
    drift = _drift_ratio(slope, reference)
    passed = drift <= _SLOPE_TOLERANCE
    checked_at = datetime.now(timezone.utc).isoformat()
    result = {"run_id": run_id, "drift": drift, "passed": passed, "checked_at": checked_at}
    record_change(get_store(), "calibration", run_id, result)
    return result
