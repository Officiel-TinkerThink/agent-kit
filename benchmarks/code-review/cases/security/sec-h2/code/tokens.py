"""Compact HS256 session tokens for the lab portal."""

import base64
import hashlib
import hmac
import json
import secrets
import time

TOKEN_TTL_SECONDS = 3600
_DIGESTS = {"HS256": hashlib.sha256}


class TokenError(Exception):
    """Raised when a session token is malformed, unsigned, forged or expired."""


def _b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment):
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (ValueError, TypeError) as exc:
        raise TokenError("invalid base64url segment") from exc


def _load_json_segment(segment):
    try:
        value = json.loads(_b64url_decode(segment))
    except ValueError as exc:
        raise TokenError("segment is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TokenError("segment must be a JSON object")
    return value


def issue_token(subject, secret, now=None):
    issued_at = int(now if now is not None else time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + TOKEN_TTL_SECONDS,
        "jti": secrets.token_urlsafe(16),
    }
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = "{}.{}".format(header_segment, payload_segment).encode("ascii")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return "{}.{}".format(header_segment, payload_segment) + "." + _b64url_encode(signature)


def verify_token(token, secret, now=None):
    if not isinstance(token, str):
        raise TokenError("token must be a string")
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("token must have three segments")
    header_segment, payload_segment, signature_segment = parts

    header = _load_json_segment(header_segment)
    digest = _DIGESTS.get(header.get("alg"))
    if digest is not None:
        signing_input = "{}.{}".format(header_segment, payload_segment).encode("ascii")
        expected = hmac.new(secret, signing_input, digest).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_segment)):
            raise TokenError("signature mismatch")

    payload = _load_json_segment(payload_segment)
    current = now if now is not None else time.time()
    if payload.get("exp", 0) <= current:
        raise TokenError("token expired")
    return payload
