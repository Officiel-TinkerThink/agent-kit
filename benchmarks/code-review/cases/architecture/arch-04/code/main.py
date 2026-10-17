"""Composition root: the only place that builds adapters from settings."""
from __future__ import annotations

import logging
import sys

from config import DEFAULT_TIMEOUT_S, Settings
from inventory.client import InventoryClient
from inventory.sync import InventorySync


def build_sync(settings: Settings) -> InventorySync:
    client = InventoryClient(base_url=settings.inventory_url, timeout_s=DEFAULT_TIMEOUT_S)
    return InventorySync(client)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        logging.error("configuration error: %s", exc)
        return 2
    build_sync(settings).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
