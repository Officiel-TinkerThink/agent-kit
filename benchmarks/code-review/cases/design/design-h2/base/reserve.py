"""Order reservations against available stock."""


class ReservationError(Exception):
    pass


def reserve_stock(conn, order_id, sku, warehouse, qty):
    if qty <= 0:
        raise ReservationError("quantity must be positive")
    cur = conn.cursor()
    cur.execute(
        "UPDATE stock_levels SET reserved = reserved + ? "
        "WHERE sku = ? AND warehouse = ? AND on_hand - reserved >= ?",
        (qty, sku, warehouse, qty),
    )
    if cur.rowcount != 1:
        conn.rollback()
        raise ReservationError(f"insufficient stock for {sku}@{warehouse}")
    cur.execute(
        "INSERT INTO reservations (order_id, sku, warehouse, qty, hold_ref) "
        "VALUES (?, ?, ?, ?, NULL)",
        (order_id, sku, warehouse, qty),
    )
    conn.commit()
    return cur.lastrowid
