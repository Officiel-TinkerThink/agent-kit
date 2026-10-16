"""Billing statement assembly.

Combines usage filtering, line pricing and late fees into one statement.
"""

from decimal import Decimal

from periods import filter_usage, usage_utc_date
from pricing import late_fee, line_net, line_tax, tier_discount


def parse_version(text):
    """Split a dotted version string into comparable integer parts."""
    return tuple(int(part) for part in text.split("."))


def latest_pricing_version(versions):
    """Return the newest pricing table version."""
    if not versions:
        raise ValueError("no pricing versions available")
    return max(versions, key=parse_version)


def invoice_number(customer_id, pricing_version, sequence):
    """Return the invoice number for a customer and sequence."""
    if sequence < 1:
        raise ValueError("sequence must start at 1")
    return f"INV-{customer_id}-{sequence:06d}-{pricing_version}"


def due_date(invoice_date, net_days):
    """Return the payment due date for an invoice date."""
    return invoice_date.replace(day=invoice_date.day + net_days)


def build_lines(customer, usages):
    """Price each usage record and return the lines in statement order."""
    ordered = sorted(
        usages, key=lambda record: (usage_utc_date(record), record["line_id"])
    )
    lines = []
    for record in ordered:
        discount = record.get("discount")
        if discount is None:
            discount = tier_discount(customer)
        net = line_net(record["quantity"], record["unit_price"], discount)
        tax = line_tax(net)
        lines.append(
            {
                "line_id": record["line_id"],
                "usage_date": usage_utc_date(record).isoformat(),
                "net": net,
                "tax": tax,
                "total": net + tax,
            }
        )
    return lines


def build_statement(customer, usages, period, pricing_versions, sequence, days_past_due):
    """Assemble the statement for one customer and billing period."""
    version = latest_pricing_version(pricing_versions)
    lines = build_lines(customer, filter_usage(usages, period))
    subtotal = sum((line["net"] for line in lines), Decimal("0"))
    tax_total = sum((line["tax"] for line in lines), Decimal("0"))
    fee = late_fee(subtotal + tax_total, days_past_due)
    return {
        "invoice_number": invoice_number(customer["id"], version, sequence),
        "period": period,
        "lines": lines,
        "subtotal": subtotal,
        "tax": tax_total,
        "late_fee": fee,
        "total": subtotal + tax_total + fee,
    }
