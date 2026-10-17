"""Invoice aggregate, due-date checks and late-fee calculation."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from domain.util_io import load_late_fee_rate

CENT = Decimal("0.01")


@dataclass
class Invoice:
    invoice_id: str
    customer_id: str
    principal_cents: int
    due_date: date
    paid: bool = False

    def is_overdue(self, today: date) -> bool:
        return not self.paid and today > self.due_date

    def months_overdue(self, today: date) -> int:
        if not self.is_overdue(today):
            return 0
        months = (today.year - self.due_date.year) * 12 + (today.month - self.due_date.month)
        if today.day < self.due_date.day:
            months -= 1
        return max(months, 0)

    def late_fee(self, today: date) -> Decimal:
        months = self.months_overdue(today)
        if months == 0:
            return Decimal("0.00")
        rate = load_late_fee_rate(self.customer_id)
        principal = Decimal(self.principal_cents) / Decimal(100)
        return (principal * rate * months).quantize(CENT, rounding=ROUND_HALF_UP)
