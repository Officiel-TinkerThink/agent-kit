"""Component construction helpers and record sink implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, List

from registry import Registry

LOGGER = logging.getLogger("labops.factory")


class RecordSink(ABC):
    """Destination that accepts serialized lines."""

    @abstractmethod
    def write_line(self, line: str) -> None:
        """Append one serialized line."""

    @abstractmethod
    def close(self) -> None:
        """Release the destination."""


class FileSink(RecordSink):
    """Writes lines to a text file, one line per record."""

    def __init__(self, path: str, encoding: str = "utf-8") -> None:
        self._path = path
        self._handle = open(path, "w", encoding=encoding, newline="")

    def write_line(self, line: str) -> None:
        self._handle.write(line + "\n")

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()


class MemorySink(RecordSink):
    """Keeps lines in memory, used by tests and dry runs."""

    def __init__(self) -> None:
        self._lines: List[str] = []

    def write_line(self, line: str) -> None:
        self._lines.append(line)

    def close(self) -> None:
        return None

    def lines(self) -> List[str]:
        """Return a copy of the lines written so far."""
        return list(self._lines)


def build(key: str, registry: Registry, *args: Any, **kwargs: Any) -> Any:
    """Look up key in registry and construct the component with the arguments."""
    component_cls = registry.get(key)
    LOGGER.info("building %s '%s'", registry.label, key)
    return component_cls(*args, **kwargs)
