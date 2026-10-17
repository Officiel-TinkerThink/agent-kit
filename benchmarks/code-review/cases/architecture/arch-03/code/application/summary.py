"""Order summary use case: shows the customer's loyalty tier and discount."""

from domain.loyalty import TIERS, Customer, tier_discount


def build_order_summary(customer: Customer, subtotal_cents: int) -> dict:
    """Return the summary lines for an order, including the loyalty tier."""
    tier = TIERS.get(customer.tier_code)
    discount_percent = tier_discount(customer)
    discount_cents = subtotal_cents * discount_percent // 100
    return {
        "customer": customer.name,
        "tier": tier.label if tier is not None else "None",
        "subtotal_cents": subtotal_cents,
        "discount_percent": discount_percent,
        "discount_cents": discount_cents,
        "total_cents": subtotal_cents - discount_cents,
    }
