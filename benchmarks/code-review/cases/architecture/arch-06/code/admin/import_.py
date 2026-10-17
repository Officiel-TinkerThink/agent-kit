"""Admin bulk import of account rows from CSV exports."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol

from validation.email import valid_email

logger = logging.getLogger(__name__)


class AccountStore(Protocol):
    def create(self, email: str, display_name: str) -> str: ...


@dataclass
class ImportResult:
    created: list[str] = field(default_factory=list)
    rejected: list[int] = field(default_factory=list)


def import_rows(rows: Iterable[Mapping[str, str]], store: AccountStore) -> ImportResult:
    """Create one account per valid row and record the line numbers of rejected rows."""
    result = ImportResult()
    for line_number, row in enumerate(rows, start=2):
        email = row.get("email", "")
        if not valid_email(email):
            result.rejected.append(line_number)
            continue
        result.created.append(store.create(email, row.get("display_name", "").strip()))
    logger.info("import finished created=%d rejected=%d", len(result.created), len(result.rejected))
    return result
