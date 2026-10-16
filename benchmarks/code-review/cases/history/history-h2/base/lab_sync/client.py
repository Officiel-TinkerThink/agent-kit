"""HTTP client for the lab results gateway."""

import json
import logging
import urllib.error
import urllib.request

from lab_sync.settings import SyncSettings

LOGGER = logging.getLogger("lab_sync.client")


class GatewayError(Exception):
    """Raised when the gateway rejects a request or cannot be reached."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class LabGatewayClient:
    """Posts validated result batches to the lab gateway."""

    def __init__(self, settings: SyncSettings, opener=None):
        self._settings = settings
        self._opener = opener or urllib.request.build_opener()

    def post_batch(self, records: list) -> dict:
        body = json.dumps({"records": records}).encode("utf-8")
        request = urllib.request.Request(
            self._settings.gateway_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._settings.gateway_token}",
            },
        )
        timeout_s = self._settings.timeout_ms / 1000
        try:
            with self._opener.open(request, timeout=timeout_s) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            LOGGER.warning("gateway rejected batch status=%s", exc.code)
            raise GatewayError(f"gateway returned {exc.code}", status=exc.code) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            LOGGER.warning("gateway unreachable: %s", exc)
            raise GatewayError("gateway unreachable") from exc
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except ValueError as exc:
            raise GatewayError("gateway returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise GatewayError("gateway response is not an object")
        LOGGER.info("batch accepted records=%d", len(records))
        return parsed
