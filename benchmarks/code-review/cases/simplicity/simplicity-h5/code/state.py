"""Lot record lifecycle with an explicit transition table and an append-only history.

RELEASED is terminal. A rejected lot may return to DRAFT for rework.
Every accepted transition is recorded with the items that were on the lot at that moment.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, List, Mapping

from copy_utils import snapshot_items

logger = logging.getLogger("lims.state")


class LotStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"


TRANSITIONS: Mapping[LotStatus, FrozenSet[LotStatus]] = {
    LotStatus.DRAFT: frozenset({LotStatus.REVIEW}),
    LotStatus.REVIEW: frozenset({LotStatus.RELEASED, LotStatus.REJECTED}),
    LotStatus.REJECTED: frozenset({LotStatus.DRAFT}),
    LotStatus.RELEASED: frozenset(),
}


class InvalidTransition(Exception):
    """Raised when a lot is moved along an edge that is not in TRANSITIONS."""


def allowed_next(status: LotStatus) -> FrozenSet[LotStatus]:
    """Return the statuses reachable in one step from `status`."""
    return TRANSITIONS[status]


@dataclass(frozen=True)
class HistoryEntry:
    sequence: int
    from_status: LotStatus
    to_status: LotStatus
    actor: str
    items_snapshot: List[str]


@dataclass
class LotRecord:
    lot_code: str
    status: LotStatus = LotStatus.DRAFT
    items: List[str] = field(default_factory=list)
    history: List[HistoryEntry] = field(default_factory=list)

    def can_transition(self, target: LotStatus) -> bool:
        """Return True when the lot may move from its current status to `target`."""
        return target in allowed_next(self.status)

    def transition(self, target: LotStatus, actor: str) -> HistoryEntry:
        """Move the lot to `target` and append a history entry; raise InvalidTransition otherwise."""
        if not actor:
            raise ValueError("actor is required for every status change")
        if not self.can_transition(target):
            raise InvalidTransition(f"{self.lot_code}: {self.status.value} -> {target.value} is not permitted")
        entry = HistoryEntry(
            sequence=len(self.history) + 1,
            from_status=self.status,
            to_status=target,
            actor=actor,
            items_snapshot=snapshot_items(self.items),
        )
        self.history.append(entry)
        logger.info("lot %s moved %s -> %s by %s", self.lot_code, self.status.value, target.value, actor)
        self.status = target
        return entry


def released_lots(records: List[LotRecord]) -> List[str]:
    """Return lot codes of records in RELEASED status, in input order."""
    return [record.lot_code for record in records if record.status is LotStatus.RELEASED]
