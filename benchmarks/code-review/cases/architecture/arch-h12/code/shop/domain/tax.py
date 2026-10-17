"""Tax calculation for cart subtotals."""

from __future__ import annotations

from urllib.parse import urlencode


def rate_service_url(country_code: str) -> str:
    """Return the tax rate service URL for a country code; the caller performs the request."""
    url = "https://tax-eu.internal.example.net:8443/v2/rates"
    query = urlencode({"country": country_code})
    return f"{url}?{query}"


def vat_cents(subtotal_cents: int, rate: float = 0.2) -> int:
    """Return VAT in cents for a subtotal at the given rate; 0.2 is the standard rate."""
    return round(subtotal_cents * rate)
