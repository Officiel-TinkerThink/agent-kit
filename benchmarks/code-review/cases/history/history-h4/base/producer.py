"""Writes peak feature files for one chromatography run, split into loader-sized batches."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from feature_model import Feature

log = logging.getLogger(__name__)

FEATURES_PER_FILE = 60
FORMAT_VERSION = 2
FILE_SUFFIX = ".features.json"


def _batch_name(run_id: str, index: int) -> str:
    """Return the file name of batch index for a run."""
    return f"{run_id}-{index:03d}{FILE_SUFFIX}"


def _document(run_id: str, batch: Sequence[Feature], index: int) -> dict:
    """Build the JSON document for one batch."""
    return {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "batch_index": index,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(batch),
        "features": [feature.to_mapping() for feature in batch],
    }


def chunk_features(features: Sequence[Feature], size: int) -> list[Sequence[Feature]]:
    """Split features into consecutive slices of at most size entries."""
    if size <= 0:
        raise ValueError("size must be positive")
    return [features[start:start + size] for start in range(0, len(features), size)]


def write_feature_files(run_id: str, features: Sequence[Feature], out_dir: Path) -> list[Path]:
    """Write the features of one run as one or more batch files.

    Returns the written paths in batch order. Each file is written under a
    temporary name and renamed, so a reader never sees a partial file.
    """
    if not run_id:
        raise ValueError("run_id is required")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, batch in enumerate(chunk_features(features, FEATURES_PER_FILE)):
        target = out_dir / _batch_name(run_id, index)
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(_document(run_id, batch, index), indent=2), encoding="utf-8")
        temp.replace(target)
        written.append(target)
    log.info("wrote %d batch files for run %s", len(written), run_id)
    return written


def summarise_run(features: Iterable[Feature]) -> dict:
    """Return count and retention range for the run summary."""
    items = list(features)
    if not items:
        return {"count": 0, "min_rt": None, "max_rt": None}
    times = [feature.retention_time for feature in items]
    return {"count": len(items), "min_rt": min(times), "max_rt": max(times)}
