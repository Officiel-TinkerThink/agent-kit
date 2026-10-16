"""Command line entry point for the release gate."""

import argparse
import sys
from typing import List, Optional

from manifest import ManifestError, load_manifest
from release_check import ReleaseCheckError, describe_change, latest_entry
from versions import VersionError, compare_versions


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the latest, compare and report commands."""
    parser = argparse.ArgumentParser(prog="release-check")
    commands = parser.add_subparsers(dest="command", required=True)
    latest = commands.add_parser("latest", help="print the highest published version")
    latest.add_argument("manifest")
    compare = commands.add_parser("compare", help="compare two versions")
    compare.add_argument("left")
    compare.add_argument("right")
    report = commands.add_parser("report", help="write a change report")
    report.add_argument("manifest")
    report.add_argument("output")
    return parser


def _write_report(path: str, lines: List[str]) -> None:
    """Write the report lines, one per change, to the output path."""
    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


def _report_lines(entries) -> List[str]:
    """Describe each step between consecutive entries in precedence order."""
    lines = []
    for previous, current in zip(entries, entries[1:]):
        change = describe_change(previous.version, current.version)
        lines.append(f"{current.component} {previous.version} -> {current.version}: {change}")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    """Run the requested command and return a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "compare":
            print(compare_versions(args.left, args.right))
            return 0
        entries = load_manifest(args.manifest)
        if args.command == "latest":
            top = latest_entry(entries)
            print(top.version if top else "none")
            return 0
        _write_report(args.output, _report_lines(entries))
        return 0
    except (ManifestError, VersionError, ReleaseCheckError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
