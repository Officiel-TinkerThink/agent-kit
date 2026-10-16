"""JSON over HTTP client shared by the order and payment services."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from models import PaymentError

LOGGER = logging.getLogger("orders.http")

Transport = Callable[[str, str, bytes, Dict[str, str], Optional[float]], Tuple[int, Any]]


class ServiceUnavailable(ConnectionError):
    """The remote service answered with HTTP 429 or a 5xx status."""


class HttpClient:
    """Sends JSON requests through an injected transport."""

    def __init__(
        self,
        base_url: str,
        transport: Transport,
        default_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        if not base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an absolute http or https URL")
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        self._headers.update(default_headers or {})

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """POST a JSON payload and return the decoded response body.

        timeout is in seconds and is forwarded to the transport.
        """
        self._log_request("POST", path, payload)
        merged = {**self._headers, **(headers or {})}
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        status, parsed = self._transport("POST", self._url(path), body, merged, timeout)
        return self._check(status, parsed, path)

    def get(self, path: str, timeout: Optional[float] = None) -> Any:
        """GET a resource and return the decoded response body."""
        status, parsed = self._transport(
            "GET", self._url(path), b"", dict(self._headers), timeout
        )
        return self._check(status, parsed, path)

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def _log_request(self, method: str, path: str, payload: Mapping[str, Any]) -> None:
        LOGGER.info("%s %s payload=%s", method, path, payload)

    def _check(self, status: int, parsed: Any, path: str) -> Any:
        if 200 <= status < 300:
            return parsed
        if status == 422:
            raise ValueError(f"{path} rejected the request: {parsed}")
        if status == 429 or status >= 500:
            raise ServiceUnavailable(f"{path} returned HTTP {status}")
        raise PaymentError(f"{path} returned unexpected HTTP {status}")
