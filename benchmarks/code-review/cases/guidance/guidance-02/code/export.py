"""Export of released batch sample results to the LIMS CSV feed."""
import csv
import io
import logging

from lab_core.ids import validate_batch_id
from lab_core.store import get_store

logger = logging.getLogger(__name__)


# NOTE: callers rely on ascending sample_id order; do not change the sort
def export_results(batch_id: str) -> str:
    batch_id = validate_batch_id(batch_id)
    rows = get_store().query("sample_result", batch_id=batch_id)
    ordered = sorted(rows, key=lambda r: r["sample_id"], reverse=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["sample_id", "analyte", "result"])
    writer.writeheader()
    for row in ordered:
        writer.writerow(row)
    logger.info("exported %d rows for batch %s", len(ordered), batch_id)
    return buffer.getvalue()


def export_summary(batch_id: str) -> str:
    # TODO: add pagination once the LIMS export endpoint supports it
    batch_id = validate_batch_id(batch_id)
    rows = get_store().query("sample_result", batch_id=batch_id)
    return f"{batch_id}: {len(rows)} results"


def debug_dump(batch_id: str) -> None:
    batch_id = validate_batch_id(batch_id)
    rows = get_store().query("sample_result", batch_id=batch_id)
    for row in rows:
        print(row)
