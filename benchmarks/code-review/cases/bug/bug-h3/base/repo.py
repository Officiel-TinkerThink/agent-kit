"""In-memory sample repository used by the lab sample tracker and its exports."""

import logging
from typing import Dict, Iterable, List, Optional

from models import VALID_STATUSES, Sample


logger = logging.getLogger("lab.repo")


class SampleRepository:
    """Holds samples keyed by sample_id and serves them in listing order."""

    def __init__(self, samples: Optional[Iterable[Sample]] = None) -> None:
        self._by_id: Dict[str, Sample] = {}
        for sample in samples or ():
            self.add(sample)

    def add(self, sample: Sample) -> None:
        """Insert a sample; sample_id must be unique."""
        if sample.sample_id in self._by_id:
            raise KeyError(f"duplicate sample_id {sample.sample_id}")
        self._by_id[sample.sample_id] = sample
        logger.info("sample stored: %s", sample.sample_id)

    def get(self, sample_id: str) -> Optional[Sample]:
        """Return the sample with this id, or None when it is not stored."""
        return self._by_id.get(sample_id)

    def count(self) -> int:
        """Return the number of stored samples."""
        return len(self._by_id)

    def ids(self) -> List[str]:
        """Return stored sample ids in listing order."""
        return [s.sample_id for s in self._ordered()]

    def _ordered(self) -> List[Sample]:
        """Return all samples in listing order."""
        return sorted(self._by_id.values(), key=lambda s: s.created_at)

    def list_all(self) -> List[Sample]:
        """Return every sample in listing order."""
        return self._ordered()

    def list_page(self, offset: int, limit: int) -> List[Sample]:
        """Return up to limit samples starting at offset, in listing order."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        ordered = self._ordered()
        return ordered[offset:offset + limit]

    def find_by_status(self, status: str) -> List[Sample]:
        """Return samples with the given status in listing order."""
        if status not in VALID_STATUSES:
            raise ValueError(f"unknown status {status!r}")
        return [s for s in self._ordered() if s.status == status]

    def sites(self) -> List[str]:
        """Return the distinct site names of stored samples, sorted."""
        return sorted({s.site for s in self._by_id.values()})

    def remove(self, sample_id: str) -> Optional[Sample]:
        """Remove and return the sample with this id, or None when it is not stored."""
        removed = self._by_id.pop(sample_id, None)
        if removed is not None:
            logger.info("sample removed: %s", sample_id)
        return removed
