"""Delivery port definitions owned by the infrastructure layer."""

from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    """Delivers a text message to a recipient."""

    def send(self, recipient: str, message: str) -> None:
        ...
