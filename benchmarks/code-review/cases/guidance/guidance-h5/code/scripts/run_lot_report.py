"""Print a status report for lots in a JSON export.

Run with PYTHONPATH pointing at src/. Output is one line per lot followed
by a releasable-count summary.
"""

import argparse
import json
import sys

from lot_release import Lot, describe_lot, is_releasable


def build_parser():
    """Return the argument parser for the report command."""
    parser = argparse.ArgumentParser(description="Print lot status report")
    parser.add_argument("path", help="JSON export of lots")
    parser.add_argument("--product", default=None, help="only report this product code")
    return parser


def filter_by_product(lots, product_code):
    """Return the lots for one product code, or all lots when no code is given."""
    if not product_code:
        return dict(lots)
    return {lot_id: lot for lot_id, lot in lots.items() if lot.product_code == product_code}


def summarise(lots):
    """Return the number of releasable lots and the total number of lots."""
    releasable = sum(1 for lot in lots.values() if is_releasable(lot))
    return releasable, len(lots)


def load_lots(path):
    """Load lots from a JSON export keyed by lot ID."""
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    lots = {}
    for item in raw:
        lots[item["lot_id"]] = Lot(
            lot_id=item["lot_id"],
            product_code=item["product_code"],
            status=item.get("status", "QUARANTINE"),
        )
    return lots


def main(argv=None):
    args = build_parser().parse_args(argv)
    lots = filter_by_product(load_lots(args.path), args.product)
    for lot_id in sorted(lots):
        print(describe_lot(lots[lot_id]))
    releasable, total = summarise(lots)
    print(f"{releasable} of {total} lots releasable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
