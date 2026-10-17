"""Billing data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class LineItem:
    """One priced line of an invoice."""

    description: str
    quantity: int
    unit_price_cents: int

    def amount_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass
class Invoice:
    """An invoice with its priced lines."""

    invoice_id: str
    customer: str
    lines: List[LineItem] = field(default_factory=list)

    def total_cents(self) -> int:
        return sum(line.amount_cents() for line in self.lines)
