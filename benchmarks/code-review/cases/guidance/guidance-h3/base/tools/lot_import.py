"""Dry-run validator for legacy lot CSV files (LAB-210)."""

from __future__ import annotations

import argparse
import csv
import math
import sys

REQUIRED_COLUMNS = ("lot_id", "product_code", "qty_kg", "mfg_date")


def load_rows(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def validate_row(index: int, row: dict[str, str]) -> list[str]:
    problems: list[str] = []
    if not (row.get("lot_id") or "").strip():
        problems.append(f"row {index}: empty lot_id")
    try:
        qty = float(row.get("qty_kg") or "")
    except ValueError:
        problems.append(f"row {index}: qty_kg not numeric")
    else:
        if not math.isfinite(qty) or qty <= 0:
            problems.append(f"row {index}: qty_kg must be a positive number")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run validation of a legacy lot CSV.")
    parser.add_argument("csv_path")
    args = parser.parse_args(argv)
    rows = load_rows(args.csv_path)
    problems: list[str] = []
    for index, row in enumerate(rows, start=2):
        problems.extend(validate_row(index, row))
    print(f"rows={len(rows)} problems={len(problems)}")
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
