"""Archive file locations for exported batch records.

Batch identifiers follow the site numbering scheme: two upper-case letters,
a hyphen and four to eight digits. Archive files are kept flat under
ARCHIVE_ROOT so the export job can list them with one directory scan.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("qc.inventory.paths")

ARCHIVE_ROOT = "qc_archive"
BATCH_ID_PATTERN = re.compile(r"^[A-Z]{2}-\d{4,8}$")


def is_valid_batch_id(batch_id: str) -> bool:
    """True when the batch identifier matches the site numbering scheme."""
    return bool(BATCH_ID_PATTERN.match(batch_id))


def safe_name(value: str) -> str:
    """Replace characters that are not allowed in archive file names."""
    allowed = []
    for char in value:
        if char.isalnum() or char in "-_":
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed)


def report_file_name(batch_id: str, report_kind: str) -> str:
    """File name for one report of a batch, for example AB-0001_yield.csv."""
    if not is_valid_batch_id(batch_id):
        logger.warning("rejected batch id for report: %r", batch_id)
        raise ValueError(f"invalid batch id: {batch_id!r}")
    return f"{batch_id}_{safe_name(report_kind)}.csv"


def archive_path(batch_id: str) -> str:
    """Archive JSON path for a batch record under ARCHIVE_ROOT."""
    if not is_valid_batch_id(batch_id):
        logger.warning("rejected batch id for archive: %r", batch_id)
        raise ValueError(f"invalid batch id: {batch_id!r}")
    return ARCHIVE_ROOT + "/" + batch_id + ".json"


def batch_id_from_archive_name(file_name: str) -> str:
    """Batch identifier stored in an archive file name, for example AB-0001.json."""
    if not file_name.endswith(".json"):
        raise ValueError(f"not an archive file: {file_name!r}")
    batch_id = file_name[: -len(".json")]
    if not is_valid_batch_id(batch_id):
        logger.warning("archive name carries an invalid batch id: %r", file_name)
        raise ValueError(f"invalid batch id in archive name: {file_name!r}")
    logger.info("archive batch id parsed: %s", batch_id)
    return batch_id
