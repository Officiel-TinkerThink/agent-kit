"""Invoice aggregate and due-date checks."""

from dataclasses import dataclass
from datetime import date


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
