"""Billing use cases: build invoices and produce reports."""

from __future__ import annotations

from typing import Dict, Optional

from .models import Invoice, LineItem
from .reports import ReportStyle, render_invoice


def build_invoice(
    invoice_id: str,
    customer: str,
    quantities: Dict[str, int],
    unit_prices_cents: Dict[str, int],
) -> Invoice:
    lines = []
    for sku, quantity in quantities.items():
        if quantity <= 0:
            raise ValueError(f"quantity for sku {sku} must be positive")
        if sku not in unit_prices_cents:
            raise LookupError(f"unknown sku {sku}")
        lines.append(
            LineItem(
                description=sku,
                quantity=quantity,
                unit_price_cents=unit_prices_cents[sku],
            )
        )
    return Invoice(invoice_id=invoice_id, customer=customer, lines=lines)


def invoice_report(invoice: Invoice, style: Optional[ReportStyle] = None) -> str:
    return render_invoice(invoice, style)
