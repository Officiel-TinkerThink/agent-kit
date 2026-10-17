"""Loyalty tiers and discount rules for the order summary."""

from dataclasses import dataclass

from infrastructure.models import CustomerRow


@dataclass(frozen=True)
class Tier:
    """A loyalty tier with its discount in whole percent."""

    code: str
    label: str
    discount_percent: int


@dataclass(frozen=True)
class Customer:
    """Domain view of a customer used by the loyalty rules."""

    customer_id: int
    name: str
    tier_code: str
    lifetime_spend_cents: int


TIERS = {
    "BRONZE": Tier(code="BRONZE", label="Bronze", discount_percent=0),
    "SILVER": Tier(code="SILVER", label="Silver", discount_percent=5),
    "GOLD": Tier(code="GOLD", label="Gold", discount_percent=10),
}


def tier_discount(customer: CustomerRow) -> int:
    """Return the discount percent for the customer's loyalty tier."""
    tier = TIERS.get(customer.tier_code)
    if tier is None:
        return 0
    return tier.discount_percent
