"""Billing use cases that coordinate invoices with persistence."""

from datetime import date
from decimal import Decimal

from domain.invoices import Invoice
from infrastructure.db import store_late_fee


def describe_invoice(invoice: Invoice, today: date) -> str:
    state = "overdue" if invoice.is_overdue(today) else "current"
    return f"{invoice.invoice_id}: {state}"


def apply_late_fee(invoice: Invoice, today: date) -> Decimal:
    fee = invoice.late_fee(today)
    if fee > 0:
        store_late_fee(invoice.invoice_id, fee)
    return fee
