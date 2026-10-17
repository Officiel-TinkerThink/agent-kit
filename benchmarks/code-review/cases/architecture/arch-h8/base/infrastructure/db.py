"""Persistence adapter for billing policy and fee records."""

from decimal import Decimal
from typing import Dict

_LATE_FEE_RATES: Dict[str, Decimal] = {
    "cust-001": Decimal("0.015"),
    "cust-002": Decimal("0.02"),
}
_STORED_FEES: Dict[str, Decimal] = {}


def fetch_late_fee_rate(customer_id: str) -> Decimal:
    return _LATE_FEE_RATES.get(customer_id, Decimal("0"))


def store_late_fee(invoice_id: str, fee: Decimal) -> None:
    _STORED_FEES[invoice_id] = fee
