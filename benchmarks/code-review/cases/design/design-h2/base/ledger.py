"""Stock ledger: on-hand and reserved quantities per SKU and warehouse."""

from dataclasses import dataclass

_WAREHOUSE_SEED = (
    ("SKU-1001", "WH-JKT"),
    ("SKU-1001", "WH-SBY"),
    ("SKU-2007", "WH-JKT"),
)

_WAREHOUSE_INDEX = {}
for _sku, _wh in _WAREHOUSE_SEED:
    _WAREHOUSE_INDEX.setdefault(_sku, []).append(_wh)


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class StockLevel:
    sku: str
    warehouse: str
    on_hand: int
    reserved: int

    @property
    def available(self):
        return self.on_hand - self.reserved


def warehouses_for(sku):
    return _WAREHOUSE_INDEX.get(sku, [])


def load_level(conn, sku, warehouse):
    cur = conn.cursor()
    cur.execute(
        "SELECT sku, warehouse, on_hand, reserved FROM stock_levels "
        "WHERE sku = ? AND warehouse = ?",
        (sku, warehouse),
    )
    row = cur.fetchone()
    if row is None:
        raise LedgerError(f"no stock row for {sku}@{warehouse}")
    return StockLevel(*row)


def adjust_on_hand(conn, sku, warehouse, delta):
    cur = conn.cursor()
    cur.execute(
        "UPDATE stock_levels SET on_hand = on_hand + ? "
        "WHERE sku = ? AND warehouse = ? AND on_hand + ? >= 0",
        (delta, sku, warehouse, delta),
    )
    if cur.rowcount != 1:
        conn.rollback()
        raise LedgerError(f"on_hand adjustment rejected for {sku}@{warehouse}")
    conn.commit()
    return load_level(conn, sku, warehouse).on_hand
