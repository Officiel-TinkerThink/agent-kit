"""Environment-driven settings for the shop."""

from __future__ import annotations

import os

TAX_SERVICE_HOST: str = os.environ.get("TAX_SERVICE_HOST", "localhost")
TAX_SERVICE_PORT: int = int(os.environ.get("TAX_SERVICE_PORT", "8080"))
