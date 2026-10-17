"""Composition root: the only module that wires adapters to ports and use cases."""
import logging
import os
import sys

from adapters.http_tracking import HttpTrackingAdapter
from application.track import TrackParcel

DEFAULT_BASE_URL = "https://tracking.example.test"


def load_base_url() -> str:
    base_url = os.environ.get("TRACKING_BASE_URL", DEFAULT_BASE_URL).strip()
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("TRACKING_BASE_URL must start with http:// or https://")
    return base_url


def build_track_parcel(base_url: str) -> TrackParcel:
    return TrackParcel(HttpTrackingAdapter(base_url=base_url))


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if len(argv) != 2:
        print("usage: main.py <tracking_number>", file=sys.stderr)
        return 2
    use_case = build_track_parcel(load_base_url())
    try:
        parcel = use_case.execute(argv[1])
    except (LookupError, RuntimeError, ValueError) as exc:
        logging.getLogger(__name__).error("lookup failed: %s", exc)
        return 1
    print(f"{parcel.tracking_number}: {parcel.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
