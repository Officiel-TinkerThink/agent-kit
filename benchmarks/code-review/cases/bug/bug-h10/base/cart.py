"""Shopping cart value objects and pricing."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class CartLine:
    sku: str
    qty: int
    unit_price: Decimal


@dataclass
class Cart:
    cart_id: str
    lines: list = field(default_factory=list)


def cart_total(cart):
    """Return the cart total in currency units, rounded half-up to cents."""
    total = sum((line.unit_price * line.qty for line in cart.lines), Decimal("0"))
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
