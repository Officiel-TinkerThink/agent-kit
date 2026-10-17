"""Helper functions for domain calculations that read billing policy values."""

from decimal import Decimal

from infrastructure.db import fetch_late_fee_rate


def load_late_fee_rate(customer_id: str) -> Decimal:
    """Return the monthly late-fee rate for a customer, or zero when none is configured."""
    rate = fetch_late_fee_rate(customer_id)
    return rate if rate >= 0 else Decimal("0")
