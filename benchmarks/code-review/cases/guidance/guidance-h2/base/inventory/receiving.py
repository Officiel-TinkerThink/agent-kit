"""Receiving workflow for inbound pallets."""

from dataclasses import dataclass
from typing import List

from common.errors import DomainError
from inventory.lot_registry import LotRecord, register_lots
from inventory.store import LotStore


@dataclass(frozen=True)
class PalletScan:
    pallet_id: str
    lot_code: str
    gross_kg: float


def validate_scan(scan: PalletScan) -> None:
    if not scan.pallet_id.strip():
        raise DomainError("pallet_id is required")
    if scan.gross_kg <= 0:
        raise DomainError(f"gross weight must be positive: {scan.pallet_id}")


def receive_batch(
    store: LotStore, scans: List[PalletScan], lots: List[LotRecord]
) -> List[LotRecord]:
    if len(scans) == 0:
        raise DomainError("batch contains no pallets")
    for scan in scans:
        validate_scan(scan)
    registered = register_lots(store, lots)
    store.log_receipt(len(scans), registered)
    return registered


def pallet_weight_total(scans: List[PalletScan]) -> float:
    return round(sum(s.gross_kg for s in scans), 3)
