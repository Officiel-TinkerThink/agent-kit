"""Database access helpers for reference data."""

import sqlite3
from decimal import Decimal
from pathlib import Path

DEFAULT_DB_PATH = Path("orders.db")
NO_DISCOUNT = Decimal("0")


def connect(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_discount_rate(customer_id: str, path: Path = DEFAULT_DB_PATH) -> Decimal:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT rate FROM discount_rates WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return NO_DISCOUNT
    return Decimal(str(row["rate"]))
