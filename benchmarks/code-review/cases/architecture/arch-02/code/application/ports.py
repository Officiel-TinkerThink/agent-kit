"""Ports used by the application layer."""

from __future__ import annotations

from typing import Protocol


class EventPublisher(Protocol):
    """Outbound port: publishes one domain event to a messaging channel."""

    def publish(self, topic: str, key: str, payload: bytes) -> None:
        """Publish one event. Raises an exception when delivery fails."""
        ...
