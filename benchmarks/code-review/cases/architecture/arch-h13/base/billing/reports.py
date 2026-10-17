"""Renders billing reports from models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Invoice, LineItem


@dataclass(frozen=True)
class ReportStyle:
    """Presentation settings shared by all billing reports."""

    currency: str = "EUR"


def format_cents(amount_cents: int) -> str:
    sign = "-" if amount_cents < 0 else ""
    value = abs(amount_cents)
    return f"{sign}{value // 100}.{value % 100:02d}"


def render_total(amount_cents: int, style: Optional[ReportStyle] = None) -> str:
    currency = style.currency if style is not None else ReportStyle().currency
    return f"{currency} {format_cents(amount_cents)}"


def render_line(line: LineItem) -> str:
    return (
        f"  {line.description} x{line.quantity} "
        f"@ {format_cents(line.unit_price_cents)} = {format_cents(line.amount_cents())}"
    )


def render_invoice(invoice: Invoice, style: Optional[ReportStyle] = None) -> str:
    rows = [f"Invoice {invoice.invoice_id} for {invoice.customer}"]
    rows.extend(render_line(line) for line in invoice.lines)
    rows.append(f"Total: {render_total(invoice.total_cents(), style)}")
    return "\n".join(rows)
