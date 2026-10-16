"""Row and result models for the plan store, the applier and the cleaner.

A plan row is one stored record of a submitted plan version. The applied
state of a plan id is tracked separately by the plan store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

STATUS_PENDING = "pending"
STATUS_APPLIED = "applied"
VALID_STATUSES = frozenset({STATUS_PENDING, STATUS_APPLIED})

APPLY_APPLIED = "applied"
APPLY_STALE = "stale"
APPLY_NOTHING_PENDING = "nothing_pending"
APPLY_STATUSES = frozenset({APPLY_APPLIED, APPLY_STALE, APPLY_NOTHING_PENDING})


@dataclass
class PlanRow:
    """One stored plan version.

    seq is a store-wide insertion counter. version is numbered per plan id.
    """

    seq: int
    plan_id: str
    version: int
    status: str
    payload: Dict[str, Any]

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"unknown status: {self.status!r}")
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")
        if not self.plan_id:
            raise ValueError("plan_id is required")

    def is_pending(self) -> bool:
        """True while the row has not been applied."""
        return self.status == STATUS_PENDING

    def is_applied(self) -> bool:
        """True for rows written by a successful apply."""
        return self.status == STATUS_APPLIED


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of one apply request."""

    status: str
    plan_id: str
    version: Optional[int] = None

    def __post_init__(self) -> None:
        if self.status not in APPLY_STATUSES:
            raise ValueError(f"unknown apply status: {self.status!r}")

    def succeeded(self) -> bool:
        """True only when the applied state changed."""
        return self.status == APPLY_APPLIED


@dataclass
class PlanRequest:
    """Input accepted from the planning API before it is stored."""

    plan_id: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Reject empty ids and non-mapping payloads with a clear message."""
        if not self.plan_id or not self.plan_id.strip():
            raise ValueError("plan_id is required")
        if not isinstance(self.payload, dict):
            raise TypeError(f"payload must be a mapping, got {type(self.payload).__name__}")


def summarize(row: PlanRow) -> str:
    """Short human-readable label used in log lines."""
    return f"{row.plan_id}@v{row.version}#{row.seq}[{row.status}]"
