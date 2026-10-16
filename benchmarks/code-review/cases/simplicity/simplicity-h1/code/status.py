"""Stock and sample status helpers for the QC lab inventory.

Status codes are stored upper-case in the inventory database. Callers pass
raw values from the barcode scanner, which may carry spaces or lower case.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List

logger = logging.getLogger("qc.inventory.status")

RELEASED = "RELEASED"
QUARANTINE = "QUARANTINE"
REJECTED = "REJECTED"
EXPIRED = "EXPIRED"

KNOWN_STATUSES = frozenset({RELEASED, QUARANTINE, REJECTED, EXPIRED})


@dataclass(frozen=True)
class StockItem:
    """One lot of a stocked material held in a QC storage location."""

    item_id: str
    lot_number: str
    expiry_date: date
    status: str
    quantity_ml: int


def normalise_status(value: str) -> str:
    """Return the canonical upper-case status code for a scanner value.

    Raises:
        TypeError: when value is not a string.
        ValueError: when the normalised code is not a known status.
    """
    if not isinstance(value, str):
        raise TypeError(f"status must be str, got {type(value).__name__}")
    code = value.strip().upper()
    if code not in KNOWN_STATUSES:
        logger.warning("unknown status code received: %r", value)
        raise ValueError(f"unknown status code: {value!r}")
    return code


def is_expired(item: StockItem, today: date) -> bool:
    """True when the lot expiry date is strictly before the reference day."""
    if item.expiry_date < today:
        return True
    else:
        return False


def is_releasable(item: StockItem, today: date) -> bool:
    """A lot may be released when it is quarantined and not expired."""
    return item.status == QUARANTINE and not is_expired(item, today)


def releasable_lots(items: Iterable[StockItem], today: date) -> List[StockItem]:
    """Lots that pass is_releasable for the reference day, in input order."""
    lots: List[StockItem] = []
    for item in items:
        if is_releasable(item, today):
            lots.append(item)
    logger.info("releasable lots found: %d", len(lots))
    return lots


def count_by_status(items: Iterable[StockItem]) -> Dict[str, int]:
    """Count stock items per status code."""
    counts: Dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def expiry_label(item: StockItem) -> str:
    """Human readable expiry text used on the storage label."""
    return f"{item.lot_number} exp {item.expiry_date.isoformat()}"
