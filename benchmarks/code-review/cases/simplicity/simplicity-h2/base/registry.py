"""Named component registry shared by the lab tooling."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("labops.registry")


class DuplicateKeyError(KeyError):
    """A key was registered twice."""


class UnknownComponentError(LookupError):
    """A requested key has no registered component."""


class Registry:
    """Maps a stable string key to a component class or callable."""

    def __init__(self, label: str) -> None:
        if not label:
            raise ValueError("label must not be empty")
        self._label = label
        self._items: Dict[str, Any] = {}

    @property
    def label(self) -> str:
        """Human readable name used in log and error messages."""
        return self._label

    def register(self, key: str, item: Any) -> None:
        """Add an item under key; keys are unique within one registry."""
        if not key:
            raise ValueError("key must not be empty")
        if key in self._items:
            raise DuplicateKeyError(f"{self._label} '{key}' is already registered")
        self._items[key] = item
        LOGGER.info("registered %s '%s'", self._label, key)

    def get(self, key: str) -> Any:
        """Return the item for key or raise UnknownComponentError."""
        try:
            return self._items[key]
        except KeyError:
            known = ", ".join(self.keys())
            raise UnknownComponentError(
                f"unknown {self._label} '{key}'; known: {known or 'none'}"
            ) from None

    def find(self, key: str) -> Optional[Any]:
        """Return the item for key, or None when it is not registered."""
        if key in self._items:
            return self._items[key]
        return None

    def keys(self) -> List[str]:
        """Return registered keys in sorted order."""
        return sorted(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._items
