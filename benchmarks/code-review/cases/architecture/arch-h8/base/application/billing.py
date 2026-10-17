"""Billing use cases that coordinate invoices with persistence."""

from datetime import date

from domain.invoices import Invoice


def describe_invoice(invoice: Invoice, today: date) -> str:
    state = "overdue" if invoice.is_overdue(today) else "current"
    return f"{invoice.invoice_id}: {state}"
