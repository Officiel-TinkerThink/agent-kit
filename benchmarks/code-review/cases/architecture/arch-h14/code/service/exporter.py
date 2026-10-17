"""Row exporter: serialises order rows to delimited text."""

from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence


def export_rows(
    rows: Iterable[Mapping[str, object]],
    columns: Sequence[str],
    delimiter: str = ",",
    strategy: str = "csv",
) -> str:
    """Serialise rows to delimited text with a header line."""
    lines: List[str] = [delimiter.join(columns)]
    for row in rows:
        lines.append(delimiter.join(str(row.get(column, "")) for column in columns))
    return "\n".join(lines)
