"""Shared domain models for order intake and payment capture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "GBP"})


class PaymentError(Exception):
    """Raised when a payment cannot be captured, refunded or voided."""


class OrderValidationError(ValueError):
    """Raised when an order or request fails intake validation."""


@dataclass(frozen=True)
class LineItem:
    """One priced line of an order; prices are integer minor units."""

    sku: str
    quantity: int
    unit_price_cents: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise OrderValidationError(f"quantity must be positive for sku {self.sku}")
        if self.unit_price_cents < 0:
            raise OrderValidationError(f"unit price must not be negative for sku {self.sku}")

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass
class Order:
    """Customer order with its priced line items."""

    order_id: str
    customer_id: str
    currency: str
    items: List[LineItem] = field(default_factory=list)
    status: str = "NEW"
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.currency not in SUPPORTED_CURRENCIES:
            raise OrderValidationError(f"unsupported currency {self.currency}")
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    @property
    def total_cents(self) -> int:
        return sum(item.total_cents for item in self.items)


@dataclass(frozen=True)
class ChargeRequest:
    """Input for a payment capture."""

    order_id: str
    amount_cents: int
    currency: str
    card_token: str
    card_number: Optional[str] = None


@dataclass(frozen=True)
class ChargeResult:
    """Gateway answer for a capture or refund."""

    charge_id: str
    status: str
    idempotency_key: str


def to_payload(request: ChargeRequest) -> Dict[str, Any]:
    """Build the JSON body sent to the payment gateway."""
    payload: Dict[str, Any] = {
        "order_id": request.order_id,
        "amount_cents": request.amount_cents,
        "currency": request.currency,
        "card_token": request.card_token,
    }
    if request.card_number is not None:
        payload["card_number"] = request.card_number
    return payload
