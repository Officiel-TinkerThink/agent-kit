"""Versioned drug library loaded from the controlled library file.

The library file carries a version header. Plans reference drugs by the
stable drug_id, which is expected to be unique within one library version.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("library")


class LibraryError(Exception):
    """The library file is unreadable or a drug id is unknown."""


class LibraryVersionError(LibraryError):
    """The loaded library version differs from the required version."""


class DrugLibrary:
    """Read-only view over one version of the drug library."""

    def __init__(self, version: str, drugs: list[dict]) -> None:
        self.version = version
        self.drugs = list(drugs)
        self._by_id = self._build_index(self.drugs)

    @staticmethod
    def _build_index(drugs: list[dict]) -> dict[str, dict]:
        """Index drug records by drug_id."""
        index: dict[str, dict] = {}
        for entry in drugs:
            index[entry["drug_id"]] = entry
        return index

    def by_id(self, drug_id: str) -> dict:
        """Return the drug record for a stable drug_id."""
        try:
            return self._by_id[drug_id]
        except KeyError as exc:
            raise LibraryError(f"unknown drug id {drug_id!r}") from exc

    def ids(self) -> list[str]:
        """Sorted list of drug ids in this version."""
        return sorted(self._by_id)

    def require_version(self, expected: str) -> None:
        """Raise LibraryVersionError unless this library has the expected version."""
        if self.version != expected:
            raise LibraryVersionError(
                f"library {self.version} loaded, {expected} required"
            )

    @classmethod
    def load(cls, path: Path, expected_version: str) -> "DrugLibrary":
        """Load the library file and verify its version header."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.error("library file unreadable: %s", path)
            raise LibraryError(f"cannot read library {path}") from exc
        library = cls(payload.get("version", ""), payload.get("drugs", []))
        library.require_version(expected_version)
        log.info("library %s loaded with %d drugs", library.version, len(library.drugs))
        return library

    def __len__(self) -> int:
        return len(self.drugs)

    def __repr__(self) -> str:
        return f"DrugLibrary(version={self.version!r}, drugs={len(self.drugs)})"
