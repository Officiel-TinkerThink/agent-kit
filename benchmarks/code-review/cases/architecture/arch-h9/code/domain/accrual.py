from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.clock import Clock

DAY_COUNT_BASIS = 365
MONEY_QUANTUM = Decimal("0.01")


def resolve_as_of(as_of: date | None, clock: Clock | None) -> date:
    if as_of is not None:
        return as_of
    if clock is not None:
        return clock.today()
    from infrastructure.clock import today_utc
    return today_utc()


def accrue_interest(
    principal: Decimal,
    annual_rate: Decimal,
    start: date,
    as_of: date | None = None,
    clock: Clock | None = None,
) -> Decimal:
    if principal < 0:
        raise ValueError("principal must not be negative")
    if annual_rate < 0:
        raise ValueError("annual_rate must not be negative")
    end = resolve_as_of(as_of, clock)
    days = (end - start).days
    if days < 0:
        raise ValueError("as_of must not be before start")
    interest = principal * annual_rate * Decimal(days) / Decimal(DAY_COUNT_BASIS)
    return interest.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
