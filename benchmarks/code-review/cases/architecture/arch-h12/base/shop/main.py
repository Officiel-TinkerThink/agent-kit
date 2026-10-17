"""Composition root: builds adapters from settings and wires them together."""

from __future__ import annotations

from .config.settings import TAX_SERVICE_HOST, TAX_SERVICE_PORT
from .infrastructure.tax_client import TaxRateClient


def build_tax_client() -> TaxRateClient:
    """Create the tax rate client from environment-driven settings."""
    return TaxRateClient(host=TAX_SERVICE_HOST, port=TAX_SERVICE_PORT)
