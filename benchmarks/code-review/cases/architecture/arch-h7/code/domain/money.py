"""Monetary amount in integer minor units."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValueError("amount must not be negative")
        if len(self.currency) != 3:
            raise ValueError("currency must be an ISO 4217 code")
