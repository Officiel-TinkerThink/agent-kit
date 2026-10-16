"""Tax rules for billing.

Rates are expressed in basis points (1/100 of one percent).
"""

from domain_errors import DomainError

STANDARD_RATE_BP = 2000
REDUCED_RATE_BP = 500
MAX_RATE_BP = 3000
EXEMPT_CUSTOMERS = frozenset({"CUST-0007", "CUST-0112"})


def is_exempt(customer_id):
    """Return True when the customer is exempt from tax."""
    return customer_id in EXEMPT_CUSTOMERS


def rate_for_customer(customer_id):
    """Return the applicable tax rate in basis points for a customer."""
    if customer_id in EXEMPT_CUSTOMERS:
        return 0
    return STANDARD_RATE_BP


def reduced_rate_for_product(product_group):
    """Return the reduced rate for product groups that qualify."""
    if product_group in {"DIAG", "PATH"}:
        return REDUCED_RATE_BP
    return STANDARD_RATE_BP


def describe_rate(rate_bp):
    """Return a human readable percentage for a rate in basis points."""
    if rate_bp < 0 or rate_bp > MAX_RATE_BP:
        raise DomainError(f"tax rate {rate_bp} bp is outside the allowed range")
    return f"{rate_bp / 100:.2f}%"


def line_tax_cents(amount_cents, rate_bp):
    """Return the tax in cents for an amount in cents, rounded half up."""
    if rate_bp < 0 or rate_bp > MAX_RATE_BP:
        raise DomainError(f"tax rate {rate_bp} bp is outside the allowed range")
    return (amount_cents * rate_bp + 5000) // 10000


def tax_breakdown(lines):
    """Return a dict of tax in cents per product group."""
    totals = {}
    for group, amount_cents in lines:
        rate_bp = reduced_rate_for_product(group)
        totals[group] = totals.get(group, 0) + line_tax_cents(amount_cents, rate_bp)
    return totals
