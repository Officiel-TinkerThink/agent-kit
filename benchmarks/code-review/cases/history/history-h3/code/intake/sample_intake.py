"""Intake of laboratory samples into a batch record.

Every sample is checked against the lot and capacity rules before it is
appended to the batch. CSV imports reuse the same acceptance path as
interactive intake.
"""

from intake.errors import IntakeError
from intake.limits import MAX_ROWS_PER_IMPORT, MAX_SAMPLES_PER_BATCH

REQUIRED_ROW_FIELDS = ("lot_id", "sample_id", "sample_seq", "count")


def require_lot(record):
    """Return the normalised lot identifier or raise IntakeError."""
    lot_id = record.get("lot_id")
    if lot_id is None or not str(lot_id).strip():
        raise IntakeError("lot_id is required for every sample")
    return str(lot_id).strip()


def normalise_sample(record):
    """Build the stored representation of one sample."""
    try:
        seq = int(record["sample_seq"])
        count = int(record["count"])
        sample_id = str(record["sample_id"]).strip()
    except (KeyError, TypeError, ValueError):
        raise IntakeError("sample_id, sample_seq and count must be present and well formed")
    return {
        "lot_id": require_lot(record),
        "sample_id": sample_id,
        "sample_seq": seq,
        "count": count,
    }


def accept_sample(batch, record):
    """Append one sample to the batch through the staging check."""
    stage_sample(batch, record)
    return batch


def stage_sample(batch, record):
    """Lot and capacity checks, then append; the only path into batch samples."""
    require_lot(record)
    if len(batch["samples"]) >= MAX_SAMPLES_PER_BATCH:
        raise IntakeError("batch sample cap reached")
    batch["samples"].append(normalise_sample(record))
    return batch


def import_rows(batch, rows):
    """Import rows atomically: either every row is staged or none is."""
    if len(rows) > MAX_ROWS_PER_IMPORT:
        raise IntakeError("import exceeds row limit")
    staged = {**batch, "samples": list(batch["samples"])}
    for line_no, row in enumerate(rows, start=1):
        missing = [name for name in REQUIRED_ROW_FIELDS if name not in row]
        if missing:
            raise IntakeError(f"row {line_no} missing fields: {missing}")
        accept_sample(staged, row)
    batch["samples"] = staged["samples"]
    return len(rows)


def check_sequential_ids(samples):
    """Return True when sample_seq values strictly increase in batch order."""
    ids = [sample["sample_seq"] for sample in samples]
    for i in range(len(ids)):
        if ids[i] <= ids[i - 1]:
            return False
    return True


def batch_volume_count(samples):
    """Total of the count field across all staged samples."""
    return sum(sample["count"] for sample in samples)
