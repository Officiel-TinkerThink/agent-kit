"""Stock position helpers for the monthly inventory report."""

import clock
from domain_errors import DomainError
from storage import stock_store

REPORT_CURRENCY = "EUR"
REORDER_BUFFER_UNITS = 5


def _items(warehouse_id):
    """Return stock items for a warehouse, newest snapshot first."""
    return stock_store.list_items(warehouse_id)


def on_hand_units(item):
    """Return on-hand units, rejecting negative stock positions."""
    units = item["on_hand"]
    if units < 0:
        raise DomainError(f"negative stock for {item['sku']}")
    return units


def needs_reorder(item):
    """Return True when on-hand units fall below the reorder threshold."""
    return on_hand_units(item) < item["reorder_point"] + REORDER_BUFFER_UNITS


def reorder_list(warehouse_id):
    """Return the SKUs that need reordering in a warehouse."""
    return [item["sku"] for item in _items(warehouse_id) if needs_reorder(item)]


def snapshot_header(warehouse_id):
    """Return the header row for a stock snapshot."""
    return {
        "warehouse_id": warehouse_id,
        "currency": REPORT_CURRENCY,
        "generated_at": clock.utc_now_iso(),
        "item_count": len(_items(warehouse_id)),
    }


def total_units(warehouse_id):
    """Return the sum of on-hand units across a warehouse."""
    return sum(on_hand_units(item) for item in _items(warehouse_id))
