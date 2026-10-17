"""Report export for account rows."""

from __future__ import annotations

import csv
import io
import json
from typing import Mapping, Sequence


def export_report(rows: Sequence[Mapping[str, str]], format="csv", plugin=None) -> str:
    """Serialise rows as CSV or JSON text."""
    if format == "csv":
        buffer = io.StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return buffer.getvalue()
    if format == "json":
        return json.dumps(list(rows), indent=2)
    raise ValueError(f"unsupported report format: {format}")
