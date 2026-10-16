"""Command line entry point that exports released batch records."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional, Sequence
from zoneinfo import ZoneInfo

from config import ExportSettings, SettingsError, load_settings
from exporter import (
    EXPORTERS,
    average_yield,
    export_batches_json,
    is_releasable,
    summarize_statuses,
)
from factory import build

LOGGER = logging.getLogger("labops.cli")

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_INPUT = 3


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Parse the command line into a namespace."""
    parser = argparse.ArgumentParser(
        prog="labops-export",
        description="Export released batch records.",
    )
    parser.add_argument("--input", required=True, help="JSON file with an array of batch records")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--limit", type=int, default=None, help="maximum rows to export")
    return parser.parse_args(argv)


def load_batches(path: str) -> List[dict]:
    """Read the input file and return its batch records."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return payload


def row_limit(settings: ExportSettings, requested: Optional[int]) -> int:
    """Return the number of rows allowed; --limit 0 is a valid request."""
    if requested is None:
        return settings.max_rows
    return min(requested, settings.max_rows)


def output_path(settings: ExportSettings, extension: str, now: datetime) -> str:
    """Build the timestamped output file path inside the output directory."""
    stamp = now.strftime("%Y%m%dT%H%M%S")
    return os.path.join(settings.output_dir, f"{settings.file_prefix}_{stamp}.{extension}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one export and return a process exit code."""
    args = parse_args(argv)
    try:
        settings = load_settings(os.environ)
    except SettingsError as exc:
        LOGGER.error("invalid configuration: %s", exc)
        return EXIT_CONFIG
    try:
        batches = load_batches(args.input)
    except (OSError, ValueError) as exc:
        LOGGER.error("cannot read input: %s", exc)
        return EXIT_INPUT

    batches = batches[: row_limit(settings, args.limit)]
    now = datetime.now(ZoneInfo(settings.timezone))
    path = output_path(settings, args.format, now)
    with open(path, "w", encoding=settings.encoding, newline="") as out:
        if args.format == "csv":
            exporter = build("csv", EXPORTERS)
            count = exporter.export(batches, out, include_header=True)
        else:
            count = export_batches_json(batches, out)

    releasable = sum(1 for batch in batches if is_releasable(batch))
    LOGGER.info("status counts %s", summarize_statuses(batches))
    LOGGER.info("exported %d records (%d releasable) to %s", count, releasable, path)
    print(f"exported {count} records, mean yield {average_yield(batches)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
