"""Receiving workflow for inbound pallets."""

import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List

from common.config import settings
from common.errors import DomainError
from inventory.lot_registry import LotRecord, register_lots
from inventory.store import LotStore

SUPPLIER_ASN_BASE = "https://asn.supplier-portal.internal/api/asn/"


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
    max_pallets = settings.get_int("receiving.max_pallets_per_batch")
    if len(scans) > max_pallets:
        raise DomainError(f"batch exceeds pallet limit: {len(scans)} > {max_pallets}")
    for scan in scans:
        validate_scan(scan)
    registered = register_lots(store, lots)
    store.log_receipt(len(scans), registered)
    return registered


def pallet_weight_total(scans: List[PalletScan]) -> float:
    return round(sum(s.gross_kg for s in scans), 3)


def fetch_supplier_asn(asn_id: str) -> bytes:
    if not asn_id.strip():
        raise DomainError("asn_id is required")
    timeout_s = settings.get_float("receiving.scan_timeout_s")
    url = SUPPLIER_ASN_BASE + urllib.parse.quote(asn_id.strip(), safe="")
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        return resp.read()
