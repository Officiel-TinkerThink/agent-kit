"""Order reservations against available stock, with carrier holds."""

from ledger import load_level


class ReservationError(Exception):
    pass


def reserve_stock(conn, order_id, sku, warehouse, qty):
    if qty <= 0:
        raise ReservationError("quantity must be positive")
    level = load_level(conn, sku, warehouse)
    if level.available < qty:
        raise ReservationError(f"insufficient stock for {sku}@{warehouse}")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reservations (order_id, sku, warehouse, qty, hold_ref) "
        "VALUES (?, ?, ?, ?, NULL)",
        (order_id, sku, warehouse, qty),
    )
    reservation_id = cur.lastrowid
    cur.execute(
        "UPDATE stock_levels SET reserved = reserved + ? WHERE sku = ? AND warehouse = ?",
        (qty, sku, warehouse),
    )
    conn.commit()
    return reservation_id


def attach_carrier_hold(conn, leases, order_id, sku, qty, confirm_hold):
    if qty <= 0:
        raise ReservationError("quantity must be positive")
    lease = leases.acquire(sku)
    try:
        hold_ref = confirm_hold(sku, qty)
        cur = conn.cursor()
        cur.execute(
            "UPDATE reservations SET hold_ref = ? WHERE order_id = ? AND sku = ?",
            (hold_ref, order_id, sku),
        )
        conn.commit()
        return hold_ref
    finally:
        leases.release(lease)
