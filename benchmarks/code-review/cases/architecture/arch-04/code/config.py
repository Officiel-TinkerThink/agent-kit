"""Runtime settings read from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass

INVENTORY_URL_ENV = "INVENTORY_URL"
DEFAULT_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class Settings:
    inventory_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.environ.get(INVENTORY_URL_ENV, "").strip()
        if not url:
            raise ValueError(f"{INVENTORY_URL_ENV} must be set")
        return cls(inventory_url=url)
