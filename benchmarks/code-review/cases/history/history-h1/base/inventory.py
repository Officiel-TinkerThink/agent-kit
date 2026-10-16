"""Stock bookkeeping for reagent and sample inventory."""

from dataclasses import dataclass


@dataclass
class StockLot:
    lot_id: str
    on_hand: int
    reorder_point: int
    expiry: str


def reorder_needed(lot: StockLot) -> bool:
    return lot.on_hand < lot.reorder_point


def consume(lot: StockLot, quantity: int) -> int:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    lot.on_hand -= quantity
    return lot.on_hand


def pick_fefo(lots, quantity):
    remaining = quantity
    picks = []
    for lot in sorted(lots, key=lambda item: item.expiry):
        if remaining <= 0:
            break
        take = min(lot.on_hand, remaining)
        if take <= 0:
            continue
        consume(lot, take)
        picks.append((lot.lot_id, take))
        remaining -= take
    if remaining > 0:
        raise ValueError(f"insufficient stock: short by {remaining}")
    return picks


def summarise(lots):
    total = 0
    flagged = []
    for lot in lots:
        total += lot.on_hand
        if reorder_needed(lot):
            flagged.append(lot.lot_id)
    return {"total_on_hand": total, "reorder_flagged": flagged}
