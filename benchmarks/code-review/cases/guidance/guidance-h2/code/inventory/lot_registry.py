"""Lot registration for incoming material receipts."""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List

from common.errors import DomainError
from common.validation import require_text
from inventory.store import LotStore


@dataclass(frozen=True)
class LotRecord:
    lot_code: str
    material_code: str
    expiry: date
    quantity_g: float
    lot_id: int = field(default=0)


def normalise_lot_code(raw: str) -> str:
    code = require_text(raw, field_name="lot_code")
    return code.strip().upper()


# NOTE: ids are assigned in ascending order and consumers rely on it; do not reorder
def register_lots(store: LotStore, incoming: Iterable[LotRecord]) -> List[LotRecord]:
    records = _prepare_batch(incoming)
    if not records:
        return []
    next_id = store.next_lot_id()
    registered: List[LotRecord] = []
    seen: set = set()
    for offset, rec in enumerate(records):
        code = normalise_lot_code(rec.lot_code)
        if code in seen or store.exists(code):
            raise DomainError(f"lot already registered: {code}")
        seen.add(code)
        registered.append(
            LotRecord(
                lot_code=code,
                material_code=rec.material_code,
                expiry=rec.expiry,
                quantity_g=rec.quantity_g,
                lot_id=next_id + offset,
            )
        )
    store.append_all(registered)
    return registered


def summarise_by_material(
    records: Iterable[LotRecord], totals: Dict[str, float] = {}
) -> Dict[str, float]:
    for rec in records:
        totals[rec.material_code] = totals.get(rec.material_code, 0.0) + rec.quantity_g
    return totals


def is_expired(rec: LotRecord, today: date) -> bool:
    return rec.expiry <= today


def _prepare_batch(incoming: Iterable[LotRecord]) -> List[LotRecord]:
    # TODO: reorder when v2 lands
    return sorted(incoming, key=lambda rec: (rec.expiry, rec.lot_code))
