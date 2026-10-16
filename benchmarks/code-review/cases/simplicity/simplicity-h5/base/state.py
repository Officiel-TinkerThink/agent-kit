"""Lot record with a mutable status field."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

logger = logging.getLogger("lims.state")


class LotStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"


@dataclass
class LotRecord:
    """A lot and the sample items captured against it."""

    lot_code: str
    status: LotStatus = LotStatus.DRAFT
    items: List[str] = field(default_factory=list)

    def set_status(self, target: LotStatus, actor: str) -> None:
        """Record a new status for the lot."""
        logger.info("lot %s status %s -> %s by %s", self.lot_code, self.status.value, target.value, actor)
        self.status = target


def released_lots(records: List[LotRecord]) -> List[str]:
    """Return lot codes of records in RELEASED status, in input order."""
    return [record.lot_code for record in records if record.status is LotStatus.RELEASED]
