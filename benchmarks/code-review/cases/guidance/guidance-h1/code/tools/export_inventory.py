"""Export inventory rows to CSV or TSV with a manifest for the receiving system."""

import csv
import json
import os
import sys

from datetime import datetime

FORMATS = ("csv", "tsv")

COLUMNS = ("sku", "location", "quantity", "unit")


def parse_format(name):
    """Map a format name to its field delimiter."""
    if name not in FORMATS:
        raise ValueError(f"unsupported export format: {name}")
    return "," if name == "csv" else "\t"


def export_rows(rows, out_path, fmt="csv"):
    """Write inventory rows to out_path using the requested format."""
    delimiter = parse_format(fmt)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=COLUMNS, delimiter=delimiter, extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path


def build_manifest(rows, out_path):
    """Describe an export for the receiving system."""
    return {
        "file": os.path.basename(out_path),
        "row_count": len(rows),
        "columns": list(COLUMNS),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def main(argv):
    """Read inventory rows from stdin and write the export and its manifest."""
    if len(argv) < 2:
        print("usage: export_inventory.py <out> [csv|tsv]", file=sys.stderr)
        return 2
    out_path = argv[1]
    fmt = argv[2] if len(argv) > 2 else "csv"
    rows = list(csv.DictReader(sys.stdin))
    export_rows(rows, out_path, fmt)
    print(json.dumps(build_manifest(rows, out_path), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
