"""Invoice assembly for laboratory testing services.

Amounts in this module are integer cents.
"""

import audit
import clock  # noqa
from billing import tax
from domain_errors import DomainError
from storage import invoice_store

INVOICE_OPEN = "OPEN"
INVOICE_PAID = "PAID"
INVOICE_VOID = "VOID"

ALLOWED_TRANSITIONS = {
    INVOICE_OPEN: {INVOICE_PAID, INVOICE_VOID},
    INVOICE_PAID: set(),
    INVOICE_VOID: set(),
}


def _load(invoice_id):
    """Return the stored invoice or raise DomainError when it is unknown."""
    record = invoice_store.get(invoice_id)
    if record is None:
        raise DomainError(f"invoice {invoice_id} does not exist")
    return record


def _check_transition(current, target):
    """Raise DomainError when the status change is not permitted."""
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise DomainError(f"cannot move invoice from {current} to {target}")


def create_invoice(invoice_id, customer_id, lines, actor):
    """Create an open invoice from priced test lines.

    Each line is a dict with keys test_code, quantity and unit_price_cents.
    """
    if not lines:
        raise DomainError("an invoice needs at least one line")
    priced = []
    for line in lines:
        if line["quantity"] <= 0:
            raise DomainError(f"quantity for {line['test_code']} must be positive")
        priced.append(
            {
                "test_code": line["test_code"],
                "quantity": line["quantity"],
                "line_cents": line["quantity"] * line["unit_price_cents"],
            }
        )
    subtotal = sum(item["line_cents"] for item in priced)
    record = {
        "invoice_id": invoice_id,
        "customer_id": customer_id,
        "lines": priced,
        "subtotal_cents": subtotal,
        "status": INVOICE_OPEN,
        "created_at": clock.utc_now_iso(),
    }
    invoice_store.insert(invoice_id, record)
    audit.record_change("invoice", invoice_id, "CREATE", actor, None, record)
    return record


def invoice_total_cents(invoice_id):
    """Return the subtotal plus tax in integer cents."""
    record = _load(invoice_id)
    rate_bp = tax.rate_for_customer(record["customer_id"])
    subtotal = record["subtotal_cents"]
    return subtotal + tax.line_tax_cents(subtotal, rate_bp)


def mark_paid(invoice_id, actor, paid_cents):
    """Record a payment; the invoice moves to PAID when fully covered."""
    record = _load(invoice_id)
    _check_transition(record["status"], INVOICE_PAID)
    if paid_cents < invoice_total_cents(invoice_id):
        raise DomainError("payment does not cover the invoice total")
    previous = dict(record)
    record["status"] = INVOICE_PAID
    record["paid_cents"] = paid_cents
    record["paid_at"] = clock.utc_now_iso()
    invoice_store.update(invoice_id, record)
    audit.record_change("invoice", invoice_id, "PAY", actor, previous, record)
    return record


def void_invoice(invoice_id, actor, reason):
    """Void an open invoice. Paid invoices cannot be voided."""
    if not reason:
        raise DomainError("a reason is required to void an invoice")
    record = _load(invoice_id)
    _check_transition(record["status"], INVOICE_VOID)
    previous = dict(record)
    record["status"] = INVOICE_VOID
    record["void_reason"] = reason
    invoice_store.update(invoice_id, record)
    audit.record_change("invoice", invoice_id, "VOID", actor, previous, record)
    return record


def outstanding_cents(invoice_id):
    """Return the amount still owed on an invoice in integer cents."""
    record = _load(invoice_id)
    if record["status"] != INVOICE_OPEN:
        return 0
    return invoice_total_cents(invoice_id) - record.get("paid_cents", 0)
