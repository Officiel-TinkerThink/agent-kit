"""Selection and export filters for QC stock and batch records."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from paths import archive_path
from status import RELEASED, StockItem

logger = logging.getLogger("qc.inventory.filters")

DEFAULT_EXPORT_DIR = Path("exports")


def select_released(items: Iterable[StockItem]) -> List[StockItem]:
    """Return the lots with RELEASED status, keeping input order."""
    selected = []
    for item in items:
        if item.status == RELEASED:
            selected.append(item)
    return selected


def at_least(items: Iterable[StockItem], minimum_ml: int) -> List[StockItem]:
    """Lots holding at least minimum_ml of material."""
    return [item for item in items if item.quantity_ml >= minimum_ml]


def lot_numbers(items: Iterable[StockItem]) -> List[str]:
    """Lot numbers of the given items, in input order."""
    return [item.lot_number for item in items]


def export_file_path(export_name: str) -> Path:
    """Destination file for an export, always under DEFAULT_EXPORT_DIR."""
    if not export_name or Path(export_name).name != export_name:
        logger.warning("rejected export name: %r", export_name)
        raise ValueError(f"invalid export name: {export_name!r}")
    return DEFAULT_EXPORT_DIR / f"{export_name}.csv"


def variance_limit(limit_ml: Optional[int], default_ml: int) -> int:
    """Allowed count variance in mL; an explicit zero limit is honoured."""
    if limit_ml is None:
        return default_ml
    return limit_ml


def label_text(item: StockItem) -> Optional[str]:
    """Label text for a lot, or None when the lot has no lot number."""
    if item.lot_number:
        return item.lot_number.upper()
    return None


def export_targets(batch_ids: Sequence[str]) -> List[str]:
    """Archive paths for the batch ids selected for export, in input order."""
    targets = []
    for batch_id in batch_ids:
        targets.append(archive_path(batch_id))
    logger.info("export targets resolved: %d", len(targets))
    return targets
